"""MCP example server entry points.

This module wires together a FastMCP server, a FastAPI wrapper, and a few sample
resources and tools. It exposes both the default app-based startup flow and a
standalone Streamable HTTP MCP mode.
"""

import argparse

from fastapi import FastAPI
from fastmcp import FastMCP
from mangum import Mangum

from .prompts.sample_prompts import register as register_prompts
from .resources.sample_resources import register as register_resources
from .tools.fastapi_endpoints import register as register_fastapi_endpoints
from .tools.fastmcp_tools import register as register_tools
from .tools.sample_tool import Mysubscription as subscriptions


def create_server() -> FastMCP:
    """Create the FastMCP server and register the example tools and resources."""
    mcp = FastMCP("mcp-lnbandi-sample-server")
    mcp.add_tool(subscriptions.getSumAsync)
    mcp.add_tool(subscriptions.getSum)
    register_resources(mcp)
    register_prompts(mcp)
    register_tools(mcp)
    return mcp


def create_app_server() -> FastAPI:
    """Create the FastAPI application that mounts the MCP HTTP endpoint."""
    app = FastAPI(title="mcp-lnbandi-sample-server", lifespan=mcp_http_app.lifespan)
    register_fastapi_endpoints(app)
    app.mount("/mcp", mcp_http_app)
    return app


mcp = create_server()
mcp_http_app = mcp.http_app(path="/", stateless_http=True)
app = create_app_server()


def main() -> None:
    """Run either the FastAPI app or the standalone Streamable HTTP MCP server."""
    parser = argparse.ArgumentParser(description="Run the MCP examples server.")
    parser.add_argument(
        "--mcp-http",
        action="store_true",
        help="Run the standalone Streamable HTTP MCP server instead of FastAPI.",
    )
    args = parser.parse_args()

    if args.mcp_http:
        mcp.run(transport="streamable-http", host="localhost", port=8000)
        return

    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)


if __name__ == "__main__":
    main()


handler = Mangum(app)