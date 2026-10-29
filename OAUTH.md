# AWS Cognito OAuth

This project uses AWS Cognito Hosted UI Authorization Code flow with PKCE to
protect its FastAPI routes and MCP-over-HTTP capabilities. Cognito authentication
is separate from Google OAuth used by the Gmail example.

## Cognito setup

Create a Cognito user pool and configure an app client for a public client:

1. Enable the **Authorization code grant** and PKCE (`S256`) for the app client.
   Do not create or configure an app-client secret; this application is a public
   PKCE client.
2. Configure the Cognito Hosted UI domain (AWS-managed or a custom HTTPS domain).
3. Add the exact callback URI to the app client's allowed callback URLs:
   `http://localhost:8000/auth/callback` for local development, or the HTTPS
   callback URL used by the deployed application.
4. Allow the requested scopes. The default is `openid`; configure additional
   Cognito scopes only when the application needs them.
5. Configure the user pool's sign-in methods and users as required by the
   deployment.

The Cognito app client must have the same client ID, Hosted UI domain, user-pool
region, and callback URL as the application environment.

## Configuration

Set these environment variables before starting the application:

| Variable | Required | Description |
| --- | --- | --- |
| `COGNITO_REGION` | Yes | AWS region containing the Cognito user pool, for example `us-east-1`. |
| `COGNITO_USER_POOL_ID` | Yes | Cognito user-pool ID, for example `us-east-1_Example`. |
| `COGNITO_CLIENT_ID` | Yes | Public Cognito app-client ID. |
| `COGNITO_DOMAIN` | Yes | HTTPS Hosted UI origin, such as `https://example.auth.us-east-1.amazoncognito.com`; do not include a path. |
| `COGNITO_REDIRECT_URI` | Yes | Exact callback URL registered in Cognito. Plain HTTP is accepted only for `localhost` or `127.0.0.1`. |
| `COGNITO_SCOPES` | No | Space-separated scopes; defaults to the minimum `openid` scope. |

For local development, create the ignored `.env` file from the committed
placeholder file:

```powershell
Copy-Item .env.example .env
# Edit .env with your Cognito user-pool and app-client settings.
uv run --env-file .env python -m mcp_examples.server
```

For local non-Docker runs, the callback URI is
`http://localhost:8000/auth/callback`. The `.env` file is ignored by Git and
must not be committed.

## Docker Compose

Docker Compose reads `.env` for interpolation and passes the Cognito settings
to the container at runtime. Do not put credentials in the Dockerfile or build
arguments. For the repository's Compose port mapping, use
`http://localhost:9001/auth/callback` as `COGNITO_REDIRECT_URI` and register
that exact URI in Cognito. Then start the container:

```powershell
Copy-Item .env.example .env
# Edit .env with real Cognito values and the Docker callback URI above.
docker compose up --build
```

Use the deployment's HTTPS callback URI instead of the local callback when
running outside local Docker Compose, and register it in the Cognito app client.

The server fails with an actionable error if only part of the Cognito
configuration is supplied. When the application is embedded without Cognito
settings, `/health` remains available while protected routes return a
configuration error; the normal startup command refuses to start.

## Login and protected routes

Open `http://localhost:8000/auth/login` for a local run, or
`http://localhost:9001/auth/login` with Docker Compose. The application creates
a fresh, opaque session cookie and a cryptographically random OAuth `state` and
PKCE verifier, then redirects to Cognito. Cognito returns an authorization code
to `/auth/callback`; the application checks the one-time state, exchanges the
code using the PKCE verifier, validates the Cognito access token, and redirects
to `/`.

The callback cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` when the
configured callback uses HTTPS. Authorization codes, tokens, state values, and
PKCE verifiers are not written to application logs or files. Uvicorn access
logging is disabled for this reason; deployments must also redact OAuth
callback query strings from reverse-proxy and platform access logs.

The following are intentionally public:

- `GET /health` — liveness check
- `GET /auth/login` — starts the authorization flow
- `GET /auth/callback` — OAuth callback; requires the matching session cookie,
  state, and authorization code

All other FastAPI routes—including `/`, `/home`, `/numbers`, `/stream`,
`/auth/status`, and the OpenAPI endpoints—and all tools, prompts, and resources
served under `/mcp/` require authentication. The `data://cognito/status` MCP
resource reports whether the required environment variables are present and
lists missing variable names without returning their values. Unauthenticated
protected requests receive HTTP `401`; temporary Cognito service/key failures
return `503`.

`GET /auth/status` returns the authenticated Cognito subject. Use
`POST /auth/logout` to discard the current in-memory session and clear the
session cookie. This is a local application logout; it does not sign the user
out of the Cognito Hosted UI or revoke bearer tokens held by a separate client.
A client may also send a Cognito access token as
an HTTP Bearer authorization header; the server validates it but does not
retain it, so that client is responsible for obtaining and refreshing its own
token.

For cookie-based MCP access, the HTTP MCP client must retain and send the
`mcp_examples_session` cookie created during login on requests to `/mcp/`.
MCP clients that cannot share that cookie with the login browser can use the
Bearer-token option instead. This project does not implement MCP OAuth
authorization-server discovery or token issuance.

## Token lifecycle and deployment limits

Cognito access and refresh tokens are held only in the server process's memory,
associated with an unguessable session cookie. Sessions expire after eight
hours; access tokens are refreshed shortly before expiry when possible. Logging
out, expiration, or restarting the process removes or loses the session, so a
user must authenticate again after a restart. No Cognito token file, database,
or persistent token store is used.

This in-memory design is suitable only for a single process/demo deployment.
It is not multi-worker, multi-replica, or serverless-session safe: a later
request routed to another process will not find the session. Use a shared,
appropriately protected session store and a deployment-specific CSRF/session
design before scaling or exposing the service to multiple users. Always use
HTTPS outside localhost.

The `--mcp-http` launch option retains the authenticated FastAPI wrapper while
omitting the sample HTTP endpoints; it does not start an unprotected FastMCP
listener. The MCP endpoint remains mounted at `/mcp/`.

## Google Gmail OAuth is separate

The Gmail tool continues to use its existing Google OAuth implementation in
`src/mcp_examples/tools/gmailmessages.py`. Its Google credentials may be read
from or saved to `GOOGLE_TOKEN_FILE` (or its existing default path); this
behavior is unchanged. Accessing Gmail therefore requires both an authenticated
Cognito application session and valid Google Gmail credentials. Cognito tokens
are never stored in the Gmail token file.

## Verification

Run the focused tests and import check:

```powershell
uv run --group dev python -m unittest discover -s tests -v
uv run python -c "from mcp_examples.server import app; print(app.title)"
```

To confirm route protection after startup, `/health` should return `200`,
`/auth/login` should redirect to Cognito, and a request to `/home` or `/mcp/`
without a valid session cookie or Cognito bearer token should return `401`.
The tests validate PKCE/state binding, token verification, and access-control
behavior without contacting a real Cognito user pool.
