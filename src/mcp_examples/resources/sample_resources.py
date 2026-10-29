"""Example resource registrations for the FastMCP server."""

import json
import os

from fastmcp import FastMCP

from mcp_examples.oauth import COGNITO_REQUIRED_ENV_VARS


def get_cognito_status() -> dict[str, object]:
    """Report Cognito setting presence without returning configured values."""
    missing = [
        name
        for name in COGNITO_REQUIRED_ENV_VARS
        if not os.environ.get(name, "").strip()
    ]
    return {
        "required_settings_present": not missing,
        "missing": missing,
    }


def register(mcp: FastMCP) -> None:
    """Register a few simple dynamic resources that return greeting and config data."""

    @mcp.resource("resource://greeting")
    def get_greeting() -> str:
        """Return a static greeting string exposed as an MCP resource."""
        return "Hello from FastMCP Resources!"

    @mcp.resource("data://config")
    def get_config() -> str:
        """Return application configuration as a JSON-formatted string."""
        return json.dumps(
            {
                "theme": "dark",
                "version": "1.2.0",
                "features": ["tools", "resources"],
            }
        )

    @mcp.resource("data://configdict")
    def get_config_dict() -> dict:
        """Return application configuration as a dictionary payload."""
        return {
            "theme": "dark",
            "version": "1.2.0",
            "features": ["tools", "resources"],
        }

    mcp.resource("data://cognito/status")(get_cognito_status)
