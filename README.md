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

You can also inspect the command-line options with:

```powershell
uv run python -m mcp_examples.server --help
```

## Run modes

### 1) Default FastAPI mode

This is the default mode for both the module and package commands. It starts the FastAPI app, mounts the MCP server at `/mcp/`, and exposes a small set of example endpoints.

```powershell
uv run python -m mcp_examples.server
```

The installed package command starts the same application:

```powershell
uv run mcp-examples
```

Expected endpoints in this mode:

- `http://localhost:8000/` — FastAPI root endpoint
- `http://localhost:8000/health` — health check endpoint
- `http://localhost:8000/mcp/` — MCP endpoint mounted by the FastAPI app; access it using MCP protocol requests rather than a simple browser GET

### 2) Standalone Streamable HTTP MCP mode

Use the standalone mode when you want to run the MCP server directly without the FastAPI wrapper. This is an alternative to the default file-based or app-based startup flow and should be used instead of the FastAPI mode when you specifically want raw MCP HTTP transport.

```powershell
uv run python -m mcp_examples.server --mcp-http
```

Expected endpoint in this mode:

- `http://localhost:8000/mcp` — standalone Streamable HTTP MCP endpoint; use MCP protocol requests rather than a plain browser GET

## Example tool and prompt behaviors

The package includes a few small examples to show how to expose MCP capabilities:

- arithmetic helpers (`getSum`, `getSumAsync`)
- Gmail OTP helper examples
- sample prompt functions for topic explanations and code-generation requests
- sample resources that return greeting and config payloads

These examples are intentionally compact and designed to be easy to expand as a learning project or starting point for a larger MCP server.

## Detailed implementation notes

- The default FastAPI server is the canonical development flow because it exposes both app-specific HTTP endpoints and the MCP endpoint in one place.
- The `--mcp-http` flag runs the MCP server directly using the Streamable HTTP transport on port 8000.
- The app entry point is `mcp_examples.server`, which is the single source of truth for startup behavior.
- All public helper modules are documented with docstrings so future contributors can understand the purpose of each tool and registration function without reading the entire runtime flow.

## Validation checklist

Before finalizing changes to the project, confirm that:

- `uv run python -m mcp_examples.server` starts successfully
- `uv run mcp-examples` starts the same app without errors
- `uv run python -m mcp_examples.server --mcp-http` starts the standalone MCP HTTP server correctly
- the endpoints listed above are reachable and match the runtime behavior
- any new or updated docstrings reflect the current code rather than planned future behavior

## Documentation conventions

The package favors concise but informative docstrings that explain:

- the purpose of each module
- the role of each class
- the expected parameters and results for public functions
- any runtime behaviour that matters when wiring tools into FastMCP or FastAPI

This documentation style keeps the sample project approachable while making it easier to extend with new MCP examples.
