# from .app import app
# from .tools import greeting  # Importing the module registers its tool.

# if __name__ == "__main__":
#     app.run()

# server.py
from fastmcp import FastMCP
from mangum import Mangum

from .prompts.sample_prompts import register as register_prompts
from .resources.sample_resources import register as register_resources
#from .tools.sample_tool import register as register_tools
from .tools.sample_tool import Mysubscription as subscriptions

def create_server() -> FastMCP:
    mcp = FastMCP("mcp-lnbandi-sample-server")
    mcp.add_tool(subscriptions.getSumAsync)
    mcp.add_tool(subscriptions.getSum)
    register_resources(mcp)
    register_prompts(mcp)

    return mcp


mcp = create_server()
app = mcp.http_app(path="/", stateless_http=True)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)


if __name__ == "__main__":
    main()


handler = Mangum(app)