import asyncio
from collections.abc import AsyncIterator
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastmcp import FastMCP
from mangum import Mangum
from .gmailmessages import gmailmessagesjson

def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def sudo_otp() -> str:
        """
        Returns a dummy OTP like string.
        :return:  a dummy OTP like string.
        """
        return "651243"

    @mcp.tool
    def get_otp_messages() -> list[dict[str, str]]:
        """Return recent Gmail inbox messages."""
        return gmailmessagesjson()


def main() -> None:
    import uvicorn
    uvicorn.run("fastapi_lambdadocker:app", host="localhost", port=8000)


#handler = Mangum(app)
