# mcp-examples

A compact Python example project that demonstrates how to build and expose an MCP server using FastMCP, a FastAPI wrapper, and a small set of example tools, prompts, and resources.

## Implementation plan

1. Audit the current project structure and startup flow so the public entry points match the actual application wiring.
2. Keep the default FastAPI server as the canonical local run mode for both the module and package commands, with the MCP endpoint mounted at `/mcp/`.
3. Correct the startup path to run the application defined in `mcp_examples.server`, ensuring the server exposes the same app object for both direct and packaged usage.
4. Add and document the alternate standalone Streamable HTTP server mode using `--mcp-http`, while keeping it on port 8000.
5. Expand the README into a complete implementation guide that explains setup, launch modes, endpoints, and expected behavior.
6. Add module, class, and function docstrings across the package so the codebase is easier to understand and extend.
7. Validate the documented commands and HTTP endpoints to ensure the README matches the real server behavior.

## Project overview

The repository contains a small MCP sample implementation with the following structure:

- `src/mcp_examples/server.py` creates the FastMCP server, registers example tools, prompts, and resources, and exposes the FastAPI app with MCP mounted under `/mcp/`.
- `src/mcp_examples/tools/` contains example MCP tools and FastAPI helper endpoints.
- `src/mcp_examples/prompts/` contains reusable prompt examples.
- `src/mcp_examples/resources/` contains sample MCP resource definitions.
- `src/mcp_examples/__main__.py` forwards execution into the main server entry point.

## Setup

Install project dependencies with `uv`:

```powershell
uv sync
```

Configure AWS Cognito before starting the server. Copy `.env.example` to `.env`
and replace the Cognito placeholders with your app-client settings. See
[OAUTH.md](./OAUTH.md) for the app-client setup, required environment variables,
login flow, and protected routes. Cognito protects the HTTP and MCP surfaces;
the Gmail example still requires its separate Google OAuth credentials.

You can also inspect the command-line options with:

```powershell
uv run python -m mcp_examples.server --help
```

## Run modes

### 1) Default FastAPI mode

This is the default mode for both the module and package commands. It starts the FastAPI app, mounts the MCP server at `/mcp/`, and protects the application routes and MCP capabilities with Cognito.

```powershell
uv run --env-file .env python -m mcp_examples.server
```

The installed package command starts the same application:

```powershell
uv run --env-file .env mcp-examples
```

Expected endpoints in this mode:

- `http://localhost:8000/auth/login` — public Cognito login initiation route
- `http://localhost:8000/auth/callback` — OAuth callback registered in Cognito
- `http://localhost:8000/health` — public health check
- `http://localhost:8000/` — protected FastAPI root endpoint
- `http://localhost:8000/mcp/` — protected MCP endpoint; use MCP protocol requests and send the login session cookie or a Cognito bearer token

### 2) MCP-focused Streamable HTTP mode

Use this mode when you want the authenticated MCP endpoint without the sample HTTP endpoints. The MCP server remains mounted in an authenticated FastAPI wrapper so the direct server listener cannot bypass Cognito protection.

```powershell
uv run --env-file .env python -m mcp_examples.server --mcp-http
```

Expected endpoint in this mode:

- `http://localhost:8000/mcp/` — authenticated Streamable HTTP MCP endpoint; use MCP protocol requests and send the login session cookie or a Cognito bearer token

## Run with Docker Compose

Copy `.env.example` to `.env` and set your Cognito region, user-pool ID,
app-client ID, and Hosted UI domain. For the existing Compose port mapping, set
`COGNITO_REDIRECT_URI` to `http://localhost:9001/auth/callback` and add that
exact URI to the Cognito app client's allowed callback URLs. Compose passes
these settings to the container at runtime; they are not built into the image.

```powershell
docker compose up --build
```

Open `http://localhost:9001/auth/login` to sign in. The container's authenticated
MCP endpoint is available at `http://localhost:9001/mcp/`. Use an HTTPS callback
URI registered with Cognito for deployed environments.

## Example tool and prompt behaviors

The package includes a few small examples to show how to expose MCP capabilities:

- arithmetic helpers (`getSum`, `getSumAsync`)
- Gmail OTP helper examples (require both Cognito and Google Gmail authorization)
- sample prompt functions for topic explanations and code-generation requests
- sample resources that return greeting and config payloads, plus
  `data://cognito/status`, which reports whether required settings are present
  and names any missing settings without returning their values

These examples are intentionally compact and designed to be easy to expand as a learning project or starting point for a larger MCP server.

## MCP progress and client communication

`getSumAsync` continues to return its 11 result updates. It also reports explicit
MCP progress from 1 through 11, with a total and a short status message. A
client must send a progress token in the tool-call `_meta.progressToken` field
and register a progress handler to receive those notifications; progress is
separate from the tool's returned data.

The server's MCP middleware observes inbound request and notification method
names, including cancellation notifications, but deliberately does not log
message payloads or arguments. FastMCP handles MCP cancellation and propagates
cancellation to the running tool as `asyncio.CancelledError`; the example
doesn't suppress it. With stateless Streamable HTTP, a closed request does not
provide a reliable generic client connect/disconnect event or persistent
presence signal.

`confirmWithClient` demonstrates the standard multi-round-trip input flow. The
server returns a structured input request, the client displays it and sends
the user's response in a follow-up protocol request, and the tool then returns
the result. This uses FastMCP's current `InputRequiredResult` flow rather than
deprecated direct server-initiated requests. It requires a client that
supports form elicitation and has an elicitation handler configured;
otherwise the tool reports an explicit unsupported-capability error. This
example does not add a separate WebSocket or event channel.

The deployment workflow configures its Lambda Function URL for
`RESPONSE_STREAM`, but that setting alone does not verify end-to-end delivery
of incremental MCP progress through the application's Mangum adapter. Confirm
progress behavior against the deployed URL before depending on it in
production.

## Detailed implementation notes

- The default FastAPI server is the canonical development flow because it exposes both app-specific HTTP endpoints and the MCP endpoint in one place.
- The `--mcp-http` flag runs the authenticated MCP endpoint without the sample HTTP routes on port 8000.
- The app entry point is `mcp_examples.server`, which is the single source of truth for startup behavior.
- All public helper modules are documented with docstrings so future contributors can understand the purpose of each tool and registration function without reading the entire runtime flow.

## Validation checklist

Before finalizing changes to the project, confirm that:

- `uv run --env-file .env python -m mcp_examples.server` starts successfully
- `uv run --env-file .env mcp-examples` starts the same app without errors
- `uv run --env-file .env python -m mcp_examples.server --mcp-http` starts the authenticated MCP HTTP mode correctly
- the endpoints listed above are reachable and match the runtime behavior
- any new or updated docstrings reflect the current code rather than planned future behavior

## Documentation conventions

The package favors concise but informative docstrings that explain:

- the purpose of each module
- the role of each class
- the expected parameters and results for public functions
- any runtime behaviour that matters when wiring tools into FastMCP or FastAPI

This documentation style keeps the sample project approachable while making it easier to extend with new MCP examples.
