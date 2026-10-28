# mcp-examples

Run the MCP server locally with:

```powershell
uv run python -m mcp_examples.server
```

With `python -m`, use the dotted module path (`mcp_examples.server`); the
colon form is for entry-point references and is not valid module syntax.

The FastAPI endpoints are available at `http://localhost:8000/` and the
Streamable HTTP MCP endpoint is available at `http://localhost:8000/mcp/`.
