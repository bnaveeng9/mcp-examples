from fastmcp import FastMCP
from mangum import Mangum
from fastapi import FastAPI
from .prompts.sample_prompts import register as register_prompts
from .resources.sample_resources import register as register_resources
from .tools.fastapi_endpoints import register as register_fastapi_endpoints
from .tools.fastmcp_tools import register as register_tools
from .tools.sample_tool import Mysubscription as subscriptions

def create_server() -> FastMCP:
    mcp = FastMCP("mcp-lnbandi-sample-server")
    mcp.add_tool(subscriptions.getSumAsync)
    mcp.add_tool(subscriptions.getSum)
    register_resources(mcp)
    register_prompts(mcp)
    register_tools(mcp)
    return mcp

def create_app_server() -> FastAPI:
    app = FastAPI(title="mcp-lnbandi-sample-server", lifespan=mcp_http_app.lifespan)
    register_fastapi_endpoints(app)
    app.mount("/mcp", mcp_http_app)
    return app

mcp = create_server()
mcp_http_app = mcp.http_app(path="/", stateless_http=True)
app = create_app_server()


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)


if __name__ == "__main__":
    main()


handler = Mangum(app)