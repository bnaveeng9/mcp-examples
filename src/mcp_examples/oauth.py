"""Cognito OAuth authorization and in-memory session management."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient

SESSION_COOKIE = "mcp_examples_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
OAUTH_STATE_TTL_SECONDS = 10 * 60
TOKEN_REFRESH_LEEWAY_SECONDS = 60
_COGNITO_ENV_NAMES = {
    "region": "COGNITO_REGION",
    "user_pool_id": "COGNITO_USER_POOL_ID",
    "client_id": "COGNITO_CLIENT_ID",
    "domain": "COGNITO_DOMAIN",
    "redirect_uri": "COGNITO_REDIRECT_URI",
}
COGNITO_REQUIRED_ENV_VARS = tuple(_COGNITO_ENV_NAMES.values())


class CognitoConfigurationError(RuntimeError):
    """Raised when Cognito configuration is missing or invalid."""


class CognitoUnavailableError(RuntimeError):
    """Raised when the Cognito token or key service cannot be reached."""


class CognitoTokenExchangeError(RuntimeError):
    """Raised when Cognito rejects an authorization or refresh token."""


class OAuthStateError(ValueError):
    """Raised when an OAuth callback has invalid or expired state."""


@dataclass(frozen=True, slots=True)
class CognitoConfig:
    """Configuration needed for Cognito Hosted UI authorization."""

    region: str
    user_pool_id: str
    client_id: str
    domain: str
    redirect_uri: str
    scopes: tuple[str, ...] = ("openid",)

    @property
    def issuer(self) -> str:
        """Return the Cognito user-pool issuer URL."""
        return (
            f"https://cognito-idp.{self.region}.amazonaws.com/"
            f"{self.user_pool_id}"
        )

    @property
    def jwks_uri(self) -> str:
        """Return the Cognito JSON Web Key Set URL."""
        return f"{self.issuer}/.well-known/jwks.json"

    @classmethod
    def from_env(cls) -> CognitoConfig | None:
        """Load Cognito settings, returning None when none are configured."""
        configured = {
            key: os.environ.get(name, "").strip()
            for key, name in _COGNITO_ENV_NAMES.items()
        }
        if not any(configured.values()):
            return None

        missing = [
            _COGNITO_ENV_NAMES[key]
            for key, value in configured.items()
            if not value
        ]
        if missing:
            raise CognitoConfigurationError(
                "Incomplete Cognito configuration. Set: " + ", ".join(missing)
            )

        domain = configured["domain"].rstrip("/")
        try:
            parsed_domain = urlsplit(domain)
            parsed_redirect = urlsplit(configured["redirect_uri"])
            _ = parsed_domain.port, parsed_redirect.port
        except ValueError as exc:
            raise CognitoConfigurationError(
                "Cognito domain or redirect URI is not a valid URL."
            ) from exc
        if (
            parsed_domain.scheme != "https"
            or not parsed_domain.netloc
            or parsed_domain.path
            or parsed_domain.username
            or parsed_domain.password
            or parsed_domain.query
            or parsed_domain.fragment
        ):
            raise CognitoConfigurationError(
                "COGNITO_DOMAIN must be an HTTPS Cognito Hosted UI origin "
                "without a path."
            )
        redirect_uri = configured["redirect_uri"]
        if parsed_redirect.scheme not in {"https", "http"} or not parsed_redirect.netloc:
            raise CognitoConfigurationError(
                "COGNITO_REDIRECT_URI must be an absolute HTTP or HTTPS URL."
            )
        if parsed_redirect.path != "/auth/callback":
            raise CognitoConfigurationError(
                "COGNITO_REDIRECT_URI must use the /auth/callback path."
            )
        if (
            parsed_redirect.username
            or parsed_redirect.password
            or parsed_redirect.fragment
        ):
            raise CognitoConfigurationError(
                "COGNITO_REDIRECT_URI cannot contain credentials or a fragment."
            )
        if parsed_redirect.scheme != "https" and parsed_redirect.hostname not in {
            "localhost",
            "127.0.0.1",
        }:
            raise CognitoConfigurationError(
                "Use HTTPS for COGNITO_REDIRECT_URI except for localhost development."
            )

        scopes = tuple(
            scope
            for scope in os.environ.get(
                "COGNITO_SCOPES", "openid"
            ).split()
            if scope
        )
        if not scopes:
            raise CognitoConfigurationError(
                "COGNITO_SCOPES must include at least one scope."
            )
        if not re.fullmatch(r"[a-z0-9-]+", configured["region"]):
            raise CognitoConfigurationError("COGNITO_REGION has an invalid format.")
        if not re.fullmatch(r"[a-z0-9-]+_[A-Za-z0-9]+", configured["user_pool_id"]):
            raise CognitoConfigurationError(
                "COGNITO_USER_POOL_ID has an invalid format."
            )
        if configured["user_pool_id"].split("_", 1)[0] != configured["region"]:
            raise CognitoConfigurationError(
                "COGNITO_USER_POOL_ID must belong to COGNITO_REGION."
            )

        return cls(
            region=configured["region"],
            user_pool_id=configured["user_pool_id"],
            client_id=configured["client_id"],
            domain=domain,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )


@dataclass(slots=True)
class _Session:
    """A short-lived user session; token values are never written to disk."""

    created_at: float
    expires_at: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending_state: str | None = None
    pending_verifier: str | None = None
    pending_created_at: float = 0
    access_token: str | None = None
    refresh_token: str | None = None
    access_expires_at: float = 0


class CognitoSessionManager:
    """Manage Cognito authorization codes and tokens in process memory."""

    def __init__(self, config: CognitoConfig | None) -> None:
        self.config = config
        self._sessions: dict[str, _Session] = {}
        self._sessions_lock = asyncio.Lock()
        self._jwks_client = (
            PyJWKClient(config.jwks_uri, cache_keys=True) if config else None
        )

    @classmethod
    def from_env(cls) -> CognitoSessionManager:
        """Create a session manager using the current process environment."""
        return cls(CognitoConfig.from_env())

    def require_config(self) -> CognitoConfig:
        """Return configured Cognito settings or raise an actionable error."""
        if self.config is None:
            raise CognitoConfigurationError(
                "Cognito authentication is not configured. Set COGNITO_REGION, "
                "COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_DOMAIN, and "
                "COGNITO_REDIRECT_URI."
            )
        return self.config

    @property
    def cookie_secure(self) -> bool:
        """Whether session cookies must be sent only over HTTPS."""
        return urlsplit(self.require_config().redirect_uri).scheme == "https"

    async def start_login(self) -> tuple[str, str]:
        """Create a fresh session and PKCE authorization URL."""
        config = self.require_config()
        session_id = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            )
            .decode("ascii")
            .rstrip("=")
        )
        now = time.time()
        session = _Session(created_at=now, expires_at=now + SESSION_TTL_SECONDS)
        session.pending_state = state
        session.pending_verifier = verifier
        session.pending_created_at = now
        async with self._sessions_lock:
            expired_sessions = [
                key
                for key, value in self._sessions.items()
                if value.expires_at <= now
                or (
                    value.access_token is None
                    and (
                        value.pending_state is None
                        or now - value.pending_created_at > OAUTH_STATE_TTL_SECONDS
                    )
                )
            ]
            for key in expired_sessions:
                del self._sessions[key]
            self._sessions[session_id] = session

        query = urllib.parse.urlencode(
            {
                "client_id": config.client_id,
                "response_type": "code",
                "scope": " ".join(config.scopes),
                "redirect_uri": config.redirect_uri,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{config.domain}/oauth2/authorize?{query}", session_id

    async def complete_login(
        self, session_id: str | None, state: str, code: str
    ) -> None:
        """Validate one-time state and exchange the authorization code."""
        config = self.require_config()
        session = await self._get_session(session_id)
        if session is None:
            raise OAuthStateError("OAuth session is missing or expired.")

        async with session.lock:
            if (
                not session.pending_state
                or not session.pending_verifier
                or time.time() - session.pending_created_at > OAUTH_STATE_TTL_SECONDS
                or not secrets.compare_digest(session.pending_state, state)
            ):
                session.pending_state = None
                session.pending_verifier = None
                raise OAuthStateError("OAuth state is invalid or expired.")
            verifier = session.pending_verifier
            session.pending_state = None
            session.pending_verifier = None

            tokens = await asyncio.to_thread(
                _request_token,
                config,
                {
                    "grant_type": "authorization_code",
                    "client_id": config.client_id,
                    "code": code,
                    "redirect_uri": config.redirect_uri,
                    "code_verifier": verifier,
                },
            )
            access_token = _required_token(tokens, "access_token")
            access_expires_at = time.time() + _expires_in(tokens)
            claims = await self._verify_access_token(access_token)
            if not claims.get("sub"):
                await self._remove_session(session_id)
                raise CognitoTokenExchangeError(
                    "Cognito access token did not contain a user subject."
                )
            session.access_token = access_token
            session.refresh_token = _optional_token(tokens, "refresh_token")
            session.access_expires_at = access_expires_at

    async def cancel_login(self, session_id: str | None, state: str) -> None:
        """Validate a denied authorization callback before removing its session."""
        session = await self._get_session(session_id)
        if session is None:
            raise OAuthStateError("OAuth session is missing or expired.")
        async with session.lock:
            if (
                not session.pending_state
                or time.time() - session.pending_created_at > OAUTH_STATE_TTL_SECONDS
                or not secrets.compare_digest(session.pending_state, state)
            ):
                raise OAuthStateError("OAuth state is invalid or expired.")
            await self._remove_session(session_id)

    async def authenticate(self, session_id: str | None) -> dict[str, Any] | None:
        """Refresh and validate a session token, returning verified claims."""
        config = self.require_config()
        session = await self._get_session(session_id)
        if session is None:
            return None

        async with session.lock:
            if session.access_token is None:
                return None
            if session.access_expires_at <= time.time() + TOKEN_REFRESH_LEEWAY_SECONDS:
                if session.refresh_token is None:
                    await self._remove_session(session_id)
                    return None
                try:
                    tokens = await asyncio.to_thread(
                        _request_token,
                        config,
                        {
                            "grant_type": "refresh_token",
                            "client_id": config.client_id,
                            "refresh_token": session.refresh_token,
                        },
                    )
                    refreshed_access_token = _required_token(
                        tokens, "access_token"
                    )
                    refreshed_expiry = _expires_in(tokens)
                except CognitoTokenExchangeError:
                    await self._remove_session(session_id)
                    return None
                session.access_token = refreshed_access_token
                session.refresh_token = (
                    _optional_token(tokens, "refresh_token") or session.refresh_token
                )
                session.access_expires_at = time.time() + refreshed_expiry

            try:
                return await self._verify_access_token(session.access_token)
            except jwt.exceptions.PyJWKClientConnectionError as exc:
                raise CognitoUnavailableError(
                    "Unable to retrieve Cognito signing keys."
                ) from exc
            except jwt.PyJWTError:
                await self._remove_session(session_id)
                return None

    async def authenticate_bearer(self, token: str) -> dict[str, Any] | None:
        """Validate a caller-supplied Cognito access token without retaining it."""
        self.require_config()
        try:
            return await self._verify_access_token(token)
        except CognitoUnavailableError:
            raise
        except jwt.PyJWTError:
            return None

    async def logout(self, session_id: str | None) -> None:
        """Remove an in-memory session and all its token material."""
        await self._remove_session(session_id)

    async def _get_session(self, session_id: str | None) -> _Session | None:
        if not session_id:
            return None
        async with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session is not None and session.expires_at <= time.time():
                del self._sessions[session_id]
                return None
            return session

    async def _remove_session(self, session_id: str | None) -> None:
        if session_id:
            async with self._sessions_lock:
                self._sessions.pop(session_id, None)

    async def _verify_access_token(self, token: str) -> dict[str, Any]:
        config = self.require_config()
        if self._jwks_client is None:
            raise CognitoConfigurationError("Cognito signing keys are not configured.")
        try:
            return await asyncio.to_thread(
                self._verify_access_token_sync, config, token
            )
        except jwt.exceptions.PyJWKClientConnectionError as exc:
            raise CognitoUnavailableError(
                "Unable to retrieve Cognito signing keys."
            ) from exc

    def _verify_access_token_sync(
        self, config: CognitoConfig, token: str
    ) -> dict[str, Any]:
        if self._jwks_client is None:
            raise CognitoConfigurationError("Cognito signing keys are not configured.")
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=config.issuer,
            options={"verify_aud": False},
            leeway=30,
        )
        if (
            claims.get("token_use") != "access"
            or claims.get("client_id") != config.client_id
            or not isinstance(claims.get("sub"), str)
            or not claims["sub"]
        ):
            raise jwt.InvalidTokenError(
                "Token is not a Cognito access token for this app."
            )
        return claims


def _request_token(config: CognitoConfig, fields: dict[str, str]) -> dict[str, Any]:
    """Exchange an authorization or refresh token with Cognito."""
    request = urllib.request.Request(
        f"{config.domain}/oauth2/token",
        data=urllib.parse.urlencode(fields).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(response_body)
        except json.JSONDecodeError:
            error_payload = {}
        error_code = (
            error_payload.get("error", "token_exchange_rejected")
            if isinstance(error_payload, dict)
            else "token_exchange_rejected"
        )
        raise CognitoTokenExchangeError(
            f"Cognito rejected the token exchange ({error_code})."
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CognitoUnavailableError(
            "Unable to reach the Cognito token endpoint."
        ) from exc
    except json.JSONDecodeError as exc:
        raise CognitoTokenExchangeError(
            "Cognito returned an invalid token response."
        ) from exc

    if not isinstance(payload, dict):
        raise CognitoTokenExchangeError("Cognito returned an invalid token response.")
    return payload


def _required_token(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise CognitoTokenExchangeError(f"Cognito token response is missing {name}.")
    return value


def _optional_token(payload: dict[str, Any], name: str) -> str | None:
    value = payload.get(name)
    return value if isinstance(value, str) and value else None


def _expires_in(payload: dict[str, Any]) -> int:
    value = payload.get("expires_in")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CognitoTokenExchangeError(
            "Cognito token response has an invalid expires_in value."
        )
    return value
