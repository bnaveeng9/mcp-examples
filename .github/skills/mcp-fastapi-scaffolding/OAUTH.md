# Skill: OAuth2 PKCE Authentication for FastMCP Applications

## Purpose

Implement OAuth2 Authorization Code Flow with PKCE in a FastMCP application that connects to protected APIs, services, or MCP resources.

This skill is specifically designed for MCP hosts such as:

- VS Code
- Claude Desktop
- Cursor
- Windsurf
- Continue
- Any MCP-compliant host

The authentication experience is presented through MCP tools, prompts, and resources, allowing the host application to guide the user through authentication.

This skill intentionally excludes:

- Identity Provider provisioning
- Identity Provider configuration
- OAuth client registration
- User pool management
- Federation setup
- Infrastructure deployment

The focus of this skill is implementing authentication within a FastMCP application and exposing the authentication workflow through MCP-native interfaces.

---

# Design Principles

## Host Owns UX

The MCP host is responsible for displaying:

- Authentication prompts
- Login instructions
- Login URLs
- Authentication status
- Authentication errors

The FastMCP application is responsible for:

- PKCE generation
- Authorization URL generation
- Authorization code exchange
- Token storage
- Token refresh
- JWT validation
- Access control

## Tool First Design

Authentication capabilities should be exposed through:

- MCP Tools
- MCP Resources
- MCP Prompts

Avoid:

- Launching local browser windows automatically
- Creating custom desktop authentication flows
- Requiring terminal interaction
- Embedding UI frameworks

---

# Architecture

```text
┌──────────────────────────┐
│ MCP Host                 │
│ VS Code / Claude Desktop │
└────────────┬─────────────┘
             │
             │ Tool Calls
             ▼
┌──────────────────────────┐
│ FastMCP Application      │
│ Authentication Layer     │
└────────────┬─────────────┘
             │
             │ Authorization Request
             ▼
┌──────────────────────────┐
│ OAuth2 Provider          │
└────────────┬─────────────┘
             │
             │ Authorization Code
             ▼
┌──────────────────────────┐
│ Callback Endpoint        │
└────────────┬─────────────┘
             │
             │ Token Exchange
             ▼
┌──────────────────────────┐
│ Token Store              │
└────────────┬─────────────┘
             │
             │ Access Token
             ▼
┌──────────────────────────┐
│ Protected Services       │
└──────────────────────────┘
```

---

# Authentication State Model

Authentication should be modeled as a state machine.

```text
UNAUTHENTICATED
        │
        ▼
LOGIN_REQUIRED
        │
        ▼
LOGIN_URL_GENERATED
        │
        ▼
USER_AUTHENTICATING
        │
        ▼
TOKEN_EXCHANGE
        │
        ▼
AUTHENTICATED
        │
        ▼
TOKEN_REFRESH
        │
        ▼
AUTHENTICATED
```

---

# Required Python Packages

```bash
pip install \
    fastmcp \
    fastapi \
    uvicorn \
    httpx \
    authlib \
    pyjwt \
    cryptography
```

---

# AuthManager

Centralize authentication logic in a dedicated service.

```python
class AuthManager:

    async def is_authenticated(self):
        ...

    async def build_authorization_url(self):
        ...

    async def exchange_code(self, code):
        ...

    async def get_access_token(self):
        ...

    async def refresh_access_token(self):
        ...

    async def validate_token(self, token):
        ...

    async def logout(self):
        ...
```

AuthManager is responsible for:

- PKCE generation
- Authorization URL creation
- Token exchange
- Token storage
- Token validation
- Refresh token handling
- Authentication state

---

# PKCE Implementation

Generate a verifier and challenge for each login attempt.

```python
import base64
import hashlib
import secrets


def create_pkce():

    code_verifier = secrets.token_urlsafe(64)

    challenge = hashlib.sha256(
        code_verifier.encode()
    ).digest()

    code_challenge = (
        base64.urlsafe_b64encode(
            challenge
        )
        .decode()
        .rstrip("=")
    )

    return (
        code_verifier,
        code_challenge
    )
```

---

# Authorization URL Generation

Required parameters:

```python
params = {
    "response_type": "code",
    "client_id": CLIENT_ID,
    "scope": "openid profile",
    "redirect_uri": REDIRECT_URI,
    "state": state,
    "code_challenge": challenge,
    "code_challenge_method": "S256"
}
```

The generated URL should be returned through an MCP tool rather than opening a browser automatically.

---

# MCP Tool: auth_status

Returns authentication information.

```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="Protected Application"
)


@mcp.tool
async def auth_status():

    return {
        "authenticated":
            await auth_manager.is_authenticated()
    }
```

Example:

```json
{
  "authenticated": true
}
```

---

# MCP Tool: start_login

Initiates OAuth authentication.

```python
@mcp.tool
async def start_login():

    login_url = (
        await auth_manager
        .build_authorization_url()
    )

    return {
        "authenticated": False,
        "login_required": True,
        "login_url": login_url
    }
```

Example:

```json
{
  "authenticated": false,
  "login_required": true,
  "login_url": "https://example.com/auth"
}
```

The MCP host can render this URL as a clickable link.

---

# MCP Tool: logout

Allows the user to terminate the local session.

```python
@mcp.tool
async def logout():

    await auth_manager.logout()

    return {
        "success": True
    }
```

---

# MCP Resource: Authentication State

Expose authentication details through a resource.

```python
@mcp.resource(
    "auth://status"
)
async def auth_status_resource():

    return {
        "authenticated":
            await auth_manager.is_authenticated()
    }
```

This enables hosts to query authentication status without repeatedly calling tools.

---

# MCP Prompt: Authentication Required

```python
@mcp.prompt
def authentication_required():

    return """
Authentication is required.

Run the start_login tool.

Complete authentication using the
returned authorization URL.

After login, retry your request.
"""
```

Hosts may surface prompts automatically.

---

# Callback Endpoint

A FastAPI endpoint receives the authorization code.

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/oauth/callback")
async def oauth_callback(
    code: str,
    state: str
):

    await auth_manager.exchange_code(
        code
    )

    return {
        "success": True,
        "message": (
            "Authentication completed"
        )
    }
```

Responsibilities:

- Validate state
- Validate PKCE verifier
- Exchange authorization code
- Store tokens

---

# Token Exchange

```python
import httpx

payload = {
    "grant_type":
        "authorization_code",
    "client_id":
        CLIENT_ID,
    "code":
        code,
    "redirect_uri":
        REDIRECT_URI,
    "code_verifier":
        code_verifier
}

response = httpx.post(
    TOKEN_ENDPOINT,
    data=payload
)
```

Expected response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "id_token": "...",
  "expires_in": 3600
}
```

---

# Token Storage

Store:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_at": 1730000000
}
```

Recommended storage:

- keyring
- encrypted file
- secrets manager

Avoid:

- source control
- plaintext files
- committed configuration

---

# Token Refresh

Refresh before token expiration.

```python
async def refresh_access_token():

    payload = {
        "grant_type":
            "refresh_token",
        "refresh_token":
            refresh_token,
        "client_id":
            CLIENT_ID
    }

    ...
```

Automatic refresh should occur before protected operations.

---

# JWT Validation

Every access token should be verified.

Validate:

- Signature
- Issuer
- Audience
- Expiration
- Not Before
- Subject

Example:

```python
from jwt import decode

claims = decode(
    token,
    key=public_key,
    algorithms=["RS256"],
    issuer=ISSUER,
    audience=AUDIENCE,
)
```

Reject invalid tokens.

---

# Authentication Guard

Protect tools requiring authorization.

```python
async def require_auth():

    authenticated = (
        await auth_manager
        .is_authenticated()
    )

    if not authenticated:

        raise RuntimeError(
            "AUTH_REQUIRED"
        )
```

---

# Protected MCP Tool

```python
@mcp.tool
async def list_resources():

    await require_auth()

    token = (
        await auth_manager
        .get_access_token()
    )

    return await service.list(
        token
    )
```

---

# Structured Authentication Errors

Authentication failures should return structured metadata.

```json
{
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "User authentication required",
    "action": "start_login"
  }
}
```

Benefits:

- Host can provide guidance
- Host can suggest the login tool
- User receives consistent experience

---

# Recommended User Flow

```text
User Requests Tool
          │
          ▼
Authentication Check
          │
    ┌─────┴─────┐
    │           │
 Authenticated  No
    │           │
    ▼           ▼
 Execute    AUTH_REQUIRED
 Tool            │
                 ▼
          Run start_login
                 │
                 ▼
          Login URL Returned
                 │
                 ▼
         Host Displays URL
                 │
                 ▼
         User Signs In
                 │
                 ▼
         Callback Invoked
                 │
                 ▼
         Tokens Stored
                 │
                 ▼
          Retry Original Tool
```

---

# VS Code Experience

```text
User invokes MCP tool
          │
          ▼
AUTH_REQUIRED
          │
          ▼
Run start_login
          │
          ▼
Display login URL
          │
          ▼
User authenticates
          │
          ▼
auth_status = true
          │
          ▼
Tool succeeds
```

---

# Claude Desktop Experience

```text
Claude invokes tool
          │
          ▼
AUTH_REQUIRED
          │
          ▼
Claude presents login URL
          │
          ▼
User authenticates
          │
          ▼
Claude retries tool
```

---

# Security Requirements

Mandatory:

- Authorization Code Flow
- PKCE S256
- State validation
- HTTPS
- Access token validation
- Refresh token rotation support
- JWT verification

Strongly Recommended:

- Keyring-backed storage
- Token encryption at rest
- Least-privilege scopes
- Audit logging
- Refresh token expiration checks

---

# Anti-Patterns

Do Not:

- Automatically launch browsers
- Require terminal copy/paste workflows
- Embed custom desktop UI
- Store plaintext refresh tokens
- Skip token validation
- Bypass PKCE
- Hardcode access tokens

---

# Deliverables

A completed implementation should provide:

- OAuth2 Authorization Code Flow
- PKCE support
- MCP-native authentication experience
- auth_status tool
- start_login tool
- logout tool
- Authentication resource
- Authentication prompt
- Authorization code exchange
- Token storage
- Automatic refresh
- JWT validation
- Protected MCP tools
- Host-compatible login workflows

The resulting FastMCP application should allow VS Code, Claude Desktop, Cursor, and other MCP hosts to present and manage the authentication experience while the FastMCP application remains responsible for security, token lifecycle management, and authorization.
