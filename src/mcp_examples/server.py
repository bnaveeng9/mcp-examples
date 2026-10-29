"""MCP example server entry points.

This module wires together a FastMCP server, a FastAPI wrapper, and a few sample
resources and tools. It exposes an authenticated FastAPI app and an MCP-focused
HTTP mode that uses the same authentication wrapper.
"""

import argparse
import logging

import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastmcp import FastMCP
from mangum import Mangum

from .oauth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    CognitoConfigurationError,
    CognitoSessionManager,
    CognitoTokenExchangeError,
    CognitoUnavailableError,
    OAuthStateError,
)
from .prompts.sample_prompts import register as register_prompts
from .resources.sample_resources import register as register_resources
from .tools.fastapi_endpoints import register as register_fastapi_endpoints
from .tools.fastmcp_tools import register as register_tools
from .tools.sample_tool import Mysubscription as subscriptions

logger = logging.getLogger(__name__)


def create_server() -> FastMCP:
    """Create the FastMCP server and register the example tools and resources."""
    mcp = FastMCP("mcp-lnbandi-sample-server")
    mcp.add_tool(subscriptions.getSumAsync)
    mcp.add_tool(subscriptions.getSum)
    register_resources(mcp)
    register_prompts(mcp)
    register_tools(mcp)
    return mcp


def create_app_server(
    auth_manager: CognitoSessionManager | None = None,
    include_http_examples: bool = True,
) -> FastAPI:
    """Create the authenticated FastAPI application and mount its MCP endpoint."""
    auth = auth_manager or CognitoSessionManager.from_env()
    app = FastAPI(title="mcp-lnbandi-sample-server", lifespan=mcp_http_app.lifespan)
    app.state.cognito_auth = auth
    if include_http_examples:
        register_fastapi_endpoints(app)
    else:
        @app.get("/health")
        async def health() -> dict[str, str]:
            """Expose the public liveness probe in MCP-only mode."""
            return {"status": "ok"}

    @app.middleware("http")
    async def require_cognito_session(request: Request, call_next):
        """Guard app and MCP routes while allowing OAuth bootstrap and health."""
        if request.url.path == "/health":
            return await call_next(request)
        if request.url.path in {"/auth/login", "/auth/callback"}:
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        try:
            claims = await auth.authenticate(request.cookies.get(SESSION_COOKIE))
            authorization = request.headers.get("authorization", "")
            scheme, _, bearer_token = authorization.partition(" ")
            if claims is None and scheme.lower() == "bearer" and bearer_token:
                claims = await auth.authenticate_bearer(bearer_token.strip())
        except CognitoConfigurationError as exc:
            return JSONResponse(
                status_code=503,
                content={"detail": str(exc)},
                headers={"Cache-Control": "no-store"},
            )
        except CognitoUnavailableError:
            logger.exception("Cognito authentication service is unavailable.")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Cognito authentication is temporarily unavailable."
                },
                headers={"Cache-Control": "no-store"},
            )
        if claims is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Cognito authentication is required."},
                headers={"Cache-Control": "no-store"},
            )
        request.state.cognito_claims = claims
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/auth/login", include_in_schema=False)
    async def start_cognito_login() -> RedirectResponse:
        """Start a PKCE login and bind its one-time state to a fresh session."""
        try:
            authorization_url, session_id = await auth.start_login()
        except CognitoConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        response = RedirectResponse(authorization_url, status_code=302)
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=auth.cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    @app.get("/auth/callback", include_in_schema=False)
    async def cognito_callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> RedirectResponse:
        """Validate Cognito's state and exchange the authorization code."""
        session_id = request.cookies.get(SESSION_COOKIE)
        if not state:
            raise HTTPException(
                status_code=400,
                detail="Cognito authorization callback is missing state.",
            )
        if error or not code:
            try:
                await auth.cancel_login(session_id, state)
            except OAuthStateError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise HTTPException(
                status_code=400,
                detail="Cognito authorization was cancelled or returned invalid data.",
            )
        try:
            await auth.complete_login(session_id, state, code)
        except OAuthStateError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except CognitoConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except CognitoUnavailableError as exc:
            logger.exception("Cognito token exchange could not reach the provider.")
            raise HTTPException(
                status_code=503,
                detail="Cognito authentication is temporarily unavailable.",
            ) from exc
        except (CognitoTokenExchangeError, jwt.PyJWTError) as exc:
            logger.warning("Cognito rejected an OAuth callback: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Cognito authentication could not be completed.",
            ) from exc
        return RedirectResponse("/", status_code=303)

    @app.get("/auth/status")
    async def cognito_status(request: Request) -> dict[str, object]:
        """Return the authenticated Cognito subject for this session."""
        claims = request.state.cognito_claims
        return {"authenticated": True, "subject": claims["sub"]}

    @app.post("/auth/logout", status_code=204)
    async def cognito_logout(request: Request) -> Response:
        """Remove the current in-memory session and clear its browser cookie."""
        await auth.logout(request.cookies.get(SESSION_COOKIE))
        response = Response(status_code=204)
        response.delete_cookie(
            SESSION_COOKIE,
            path="/",
            secure=auth.cookie_secure if auth.config else False,
            httponly=True,
            samesite="lax",
        )
        return response

    app.mount("/mcp", mcp_http_app)
    return app


mcp = create_server()
mcp_http_app = mcp.http_app(path="/", stateless_http=True)
app = create_app_server()


def main() -> None:
    """Run the protected FastAPI application or its MCP-only HTTP mode."""
    parser = argparse.ArgumentParser(description="Run the MCP examples server.")
    parser.add_argument(
        "--mcp-http",
        action="store_true",
        help="Run the authenticated HTTP wrapper for the Streamable MCP endpoint.",
    )
    args = parser.parse_args()

    auth = app.state.cognito_auth
    auth.require_config()
    import uvicorn

    selected_app = (
        create_app_server(auth, include_http_examples=False) if args.mcp_http else app
    )
    uvicorn.run(selected_app, host="localhost", port=8000, access_log=False)


if __name__ == "__main__":
    main()


handler = Mangum(app)