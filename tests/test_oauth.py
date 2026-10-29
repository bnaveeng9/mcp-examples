"""Tests for Cognito PKCE session handling and route protection."""

from __future__ import annotations

import base64
import hashlib
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from mcp_examples.oauth import (
    SESSION_COOKIE,
    CognitoConfig,
    CognitoConfigurationError,
    CognitoSessionManager,
    OAuthStateError,
)
from mcp_examples.server import create_app_server


def _config() -> CognitoConfig:
    return CognitoConfig(
        region="us-east-1",
        user_pool_id="us-east-1_testpool",
        client_id="test-client",
        domain="https://example.auth.us-east-1.amazoncognito.com",
        redirect_uri="http://localhost:8000/auth/callback",
    )


class CognitoSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_url_uses_pkce_s256_and_random_state(self) -> None:
        manager = CognitoSessionManager(_config())

        url, session_id = await manager.start_login()

        query = parse_qs(urlsplit(url).query)
        verifier = manager._sessions[session_id].pending_verifier
        expected_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            )
            .decode("ascii")
            .rstrip("=")
        )
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["code_challenge"], [expected_challenge])
        self.assertEqual(query["response_type"], ["code"])
        self.assertTrue(query["state"][0])

    async def test_callback_binds_exchange_to_state_and_session(self) -> None:
        manager = CognitoSessionManager(_config())
        with patch.object(
            manager,
            "_verify_access_token",
            new=AsyncMock(return_value={"sub": "user-123", "token_use": "access"}),
        ):
            await self._assert_callback_state(manager)

    async def _assert_callback_state(self, manager: CognitoSessionManager) -> None:
        url, session_id = await manager.start_login()
        state = parse_qs(urlsplit(url).query)["state"][0]
        verifier = manager._sessions[session_id].pending_verifier

        with patch(
            "mcp_examples.oauth._request_token",
            return_value={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
            },
        ) as exchange:
            await manager.complete_login(session_id, state, "auth-code")
            self.assertEqual(exchange.call_args.args[1]["code_verifier"], verifier)

        session = manager._sessions[session_id]
        self.assertEqual(session.access_token, "access-token")
        self.assertEqual(session.refresh_token, "refresh-token")
        self.assertIsNone(await manager.authenticate("another-session"))

    async def test_invalid_state_does_not_exchange_code(self) -> None:
        manager = CognitoSessionManager(_config())
        _, session_id = await manager.start_login()

        with patch("mcp_examples.oauth._request_token") as exchange:
            with self.assertRaises(OAuthStateError):
                await manager.complete_login(session_id, "wrong-state", "auth-code")
            exchange.assert_not_called()

    async def test_expired_access_token_is_refreshed_in_memory(self) -> None:
        manager = CognitoSessionManager(_config())
        url, session_id = await manager.start_login()
        state = parse_qs(urlsplit(url).query)["state"][0]
        with patch.object(
            manager,
            "_verify_access_token",
            new=AsyncMock(return_value={"sub": "user-123", "token_use": "access"}),
        ):
            with patch(
                "mcp_examples.oauth._request_token",
                return_value={
                    "access_token": "first-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                },
            ):
                await manager.complete_login(session_id, state, "auth-code")

            manager._sessions[session_id].access_expires_at = time.time() - 1
            with patch(
                "mcp_examples.oauth._request_token",
                return_value={"access_token": "refreshed-token", "expires_in": 3600},
            ) as refresh:
                claims = await manager.authenticate(session_id)

        self.assertEqual(claims["sub"], "user-123")
        self.assertEqual(manager._sessions[session_id].access_token, "refreshed-token")
        self.assertEqual(
            refresh.call_args.args[1]["grant_type"], "refresh_token"
        )
        self.assertEqual(
            manager._sessions[session_id].refresh_token, "refresh-token"
        )


class CognitoJwtTests(unittest.TestCase):
    def test_only_access_tokens_for_configured_client_are_accepted(self) -> None:
        config = _config()
        manager = CognitoSessionManager(config)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        manager._jwks_client = SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(
                key=private_key.public_key()
            )
        )
        claims = {
            "iss": config.issuer,
            "sub": "user-123",
            "client_id": config.client_id,
            "token_use": "access",
            "exp": int(time.time()) + 300,
        }
        access_token = jwt.encode(claims, private_key, algorithm="RS256")

        verified = manager._verify_access_token_sync(config, access_token)
        self.assertEqual(verified["sub"], "user-123")

        id_token = jwt.encode(
            {**claims, "token_use": "id", "aud": config.client_id},
            private_key,
            algorithm="RS256",
        )
        with self.assertRaises(jwt.InvalidTokenError):
            manager._verify_access_token_sync(config, id_token)


class CognitoRouteTests(unittest.TestCase):
    def test_health_is_public_while_app_and_mcp_routes_are_protected(self) -> None:
        client = TestClient(create_app_server(CognitoSessionManager(_config())))

        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.get("/home").status_code, 401)
        self.assertEqual(client.get("/mcp/").status_code, 401)

    def test_login_callback_status_logout_flow(self) -> None:
        manager = CognitoSessionManager(_config())
        client = TestClient(create_app_server(manager))

        with (
            patch.object(
                manager,
                "_verify_access_token",
                new=AsyncMock(return_value={"sub": "user-123", "token_use": "access"}),
            ),
            patch(
                "mcp_examples.oauth._request_token",
                return_value={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                },
            ),
        ):
            login = client.get("/auth/login", follow_redirects=False)
            self.assertEqual(login.status_code, 302)
            self.assertIn("code_challenge_method=S256", login.headers["location"])
            self.assertIn(SESSION_COOKIE, client.cookies)
            state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]

            callback = client.get(
                "/auth/callback",
                params={"code": "auth-code", "state": state},
                follow_redirects=False,
            )

            self.assertEqual(callback.status_code, 303)
            self.assertEqual(client.get("/auth/status").json()["subject"], "user-123")
            self.assertEqual(client.get("/home").status_code, 200)
            self.assertNotEqual(client.get("/mcp/").status_code, 401)
            self.assertEqual(client.post("/auth/logout").status_code, 204)

        self.assertEqual(client.get("/auth/status").status_code, 401)

    def test_bearer_access_token_can_authenticate_mcp_client(self) -> None:
        manager = CognitoSessionManager(_config())
        client = TestClient(create_app_server(manager))

        with patch.object(
            manager,
            "authenticate_bearer",
            new=AsyncMock(return_value={"sub": "bearer-user"}),
        ):
            response = client.get(
                "/auth/status",
                headers={"Authorization": "Bearer cognito-access-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subject"], "bearer-user")

    def test_callback_rejects_state_mismatch_before_token_exchange(self) -> None:
        client = TestClient(create_app_server(CognitoSessionManager(_config())))
        login = client.get("/auth/login", follow_redirects=False)
        state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]

        with patch("mcp_examples.oauth._request_token") as exchange:
            response = client.get(
                "/auth/callback",
                params={"code": "auth-code", "state": f"{state}-wrong"},
            )

        self.assertEqual(response.status_code, 400)
        exchange.assert_not_called()

    def test_unconfigured_cognito_fails_closed(self) -> None:
        client = TestClient(create_app_server(CognitoSessionManager(None)))

        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.get("/home").status_code, 503)
        self.assertEqual(client.get("/auth/login").status_code, 503)


class CognitoConfigurationTests(unittest.TestCase):
    def test_empty_environment_does_not_use_cognito_defaults(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(CognitoConfig.from_env())

    def test_partial_environment_configuration_is_actionable(self) -> None:
        with patch.dict(
            "os.environ",
            {"COGNITO_REGION": "us-east-1"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                CognitoConfigurationError, "COGNITO_USER_POOL_ID"
            ):
                CognitoConfig.from_env()

    def test_complete_environment_configuration_is_loaded(self) -> None:
        values = {
            "COGNITO_REGION": "us-west-2",
            "COGNITO_USER_POOL_ID": "us-west-2_TestPool",
            "COGNITO_CLIENT_ID": "test-client-id",
            "COGNITO_DOMAIN": "https://example.auth.us-west-2.amazoncognito.com",
            "COGNITO_REDIRECT_URI": "http://localhost:9001/auth/callback",
        }
        with patch.dict("os.environ", values, clear=True):
            config = CognitoConfig.from_env()

        self.assertIsNotNone(config)
        self.assertEqual(config.region, "us-west-2")
        self.assertEqual(config.user_pool_id, "us-west-2_TestPool")
        self.assertEqual(config.client_id, "test-client-id")
        self.assertEqual(config.domain, values["COGNITO_DOMAIN"])
        self.assertEqual(config.redirect_uri, values["COGNITO_REDIRECT_URI"])


if __name__ == "__main__":
    unittest.main()
