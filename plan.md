# Startup Fix Plan

## Problem and proposed approach

`uv run python -m mcp_examples.server` currently asks Uvicorn to import the invalid module target `mcp-examples:app`, resulting in `Error loading ASGI app. Could not import module "mcp-examples".` The package script also targets `mcp_examples:main`, but the callable is not present at that location. Keep the existing FastAPI app as the default and fix both startup entry points. Add a separate, explicit standalone Streamable HTTP MCP mode on port 8000, used instead of the FastAPI mode.

## Todos

1. Document the startup plan and both launch modes in README.md.
2. Fix the module command and package script to run the FastAPI app; add a `--mcp-http` option to launch standalone Streamable HTTP MCP on port 8000.
3. Validate module startup, package-script startup, and HTTP behavior for both run modes.

## Notes and considerations

- Default mode remains FastAPI on `localhost:8000`, including the existing `/mcp/` mount.
- Standalone mode also uses port 8000, so the two modes cannot run concurrently.
- Docker changes are out of scope.
- Current files already have user modifications; preserve all unrelated work while making the agreed surgical changes.
