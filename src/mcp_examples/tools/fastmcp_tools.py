"""FastMCP tool registration examples for the sample server."""

from fastmcp import FastMCP

from .gmailmessages import gmailmessagesjson


def register(mcp: FastMCP) -> None:
    """Register the example MCP tools on the given FastMCP instance."""

    @mcp.tool()
    def sudo_otp() -> str:
        """Return a dummy OTP string used for local demonstration purposes."""
        return "651243"

    @mcp.tool
    def get_otp_messages() -> list[dict[str, str]]:
        """Return recent Gmail inbox messages as a list of structured payloads."""
        return gmailmessagesjson()


def main() -> None:
    """Provide a direct-app startup entry point when this module is executed."""
    import uvicorn

    uvicorn.run("fastapi_lambdadocker:app", host="localhost", port=8000)

