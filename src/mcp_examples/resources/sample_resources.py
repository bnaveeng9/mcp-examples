import json
from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    # Basic dynamic resource returning a string
    @mcp.resource("resource://greeting")
    def get_greeting() -> str:
        """Provides a simple greeting message."""
        return "Hello from FastMCP Resources!"

    # Resource returning JSON data
    @mcp.resource("data://config")
    def get_config() -> str:
        """Provides application configuration as JSON."""
        return json.dumps({
            "theme": "dark",
            "version": "1.2.0",
            "features": ["tools", "resources"],
        })

    # Resource returning JSON data
    @mcp.resource("data://configdict")
    def get_config_dict() -> dict:
        """Provides application configuration as JSON."""
        return {
            "theme": "dark",
            "version": "1.2.0",
            "features": ["tools", "resources"],
        }