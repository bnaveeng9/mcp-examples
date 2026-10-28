# mcp-examples

## Startup implementation plan

1. Keep the FastAPI application as the default for both the module and package
   commands, listening on port 8000 with MCP mounted at `/mcp/`.
2. Correct the Uvicorn startup target so it runs the application defined in
   `mcp_examples.server`.
3. Add an alternate standalone Streamable HTTP MCP mode on port 8000.
4. Document both launch modes and verify their HTTP endpoints.

## Run modes

Start the FastAPI app, including its `/mcp/` endpoint:

```powershell
uv run python -m mcp_examples.server
```

The installed package command starts the same app:

```powershell
uv run mcp-examples
```

To run the standalone Streamable HTTP MCP server instead, use:

```powershell
uv run python -m mcp_examples.server --mcp-http
```

The standalone mode also listens on port 8000 and exposes MCP at
`http://localhost:8000/mcp`. Run it instead of—not alongside—the FastAPI mode.
In the default mode, the FastAPI endpoints are available at
`http://localhost:8000/`, and MCP is available at
`http://localhost:8000/mcp/`.
