"""FastAPI example endpoints used by the MCP example server."""

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse


def register(app: FastAPI) -> None:
    """Register a small set of example endpoints on the provided FastAPI app."""

    @app.get("/health")
    @app.get("/")
    async def health() -> dict[str, str]:
        """Return a simple status payload used for health checks."""
        return {"status": "ok"}

    @app.get("/home")
    @app.get("/story/stream/home")
    async def root() -> dict[str, str]:
        """Return a basic application greeting for local verification."""
        return {"message": "Hello from fastapi-lambdadocker!"}

    @app.get("/numbers", response_class=Response)
    async def numbers() -> Response:
        """Return a newline-delimited integer payload as plain text."""
        data = "".join(f"{i}\n" for i in range(1, 2000))
        return Response(content=data, media_type="text/plain")

    @app.get("/stream", response_class=StreamingResponse)
    async def stream() -> StreamingResponse:
        """Stream a sequence of chunks to demonstrate a simple async response."""

        async def generate() -> AsyncIterator[str]:
            for i in range(1, 4000):
                if i > 2:
                    await asyncio.sleep(0.01)
                yield f"chunk {i}\n"

        return StreamingResponse(generate(), media_type="text/plain")


def main() -> None:
    """Run this module directly as a FastAPI app if needed for debugging."""
    import uvicorn

    uvicorn.run("fastapi_lambdadocker:app", host="localhost", port=8000)

