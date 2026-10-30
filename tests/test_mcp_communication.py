"""Tests for MCP progress and client communication examples."""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx2
from fastapi import FastAPI
from fastmcp import Client
from fastmcp.client.transports.http import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext

from mcp_examples.server import MCPActivityMiddleware, create_server
from mcp_examples.tools.sample_tool import Mysubscription


class MCPProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_tool_reports_progress_and_keeps_all_updates(self) -> None:
        progress: list[tuple[float, float | None, str | None]] = []

        async def record_progress(
            current: float,
            total: float | None,
            message: str | None,
        ) -> None:
            progress.append((current, total, message))

        server = create_server()
        async with Client(server) as client:
            tools = await client.list_tools()
            tool = next(tool for tool in tools if tool.name == "getSumAsync")
            self.assertNotIn("self", tool.input_schema["properties"])

            with patch(
                "mcp_examples.tools.sample_tool.asyncio.sleep",
                new=AsyncMock(),
            ):
                result = await client.call_tool(
                    "getSumAsync",
                    meta={"progressToken": "progress-test"},
                    progress_handler=record_progress,
                )

        self.assertEqual(len(progress), 11)
        self.assertEqual([item[0] for item in progress], list(range(1, 12)))
        self.assertTrue(all(item[1] == 11 for item in progress))
        self.assertEqual(progress[0][2], "Completed iteration 1 of 11")
        self.assertEqual(len(result.content), 1)
        updates = json.loads(result.content[0].text)
        self.assertEqual(len(updates), 11)
        self.assertEqual(updates[0]["iteration"], 0)
        self.assertEqual(updates[-1]["iteration"], 10)

    async def test_streamable_http_delivers_progress_notifications(self) -> None:
        server = create_server()
        mcp_app = server.http_app(path="/", stateless_http=True)
        app = FastAPI(lifespan=mcp_app.lifespan)
        app.mount("/mcp", mcp_app)
        transport = StreamableHttpTransport(
            "http://test/mcp/",
            httpx_client_factory=lambda **kwargs: httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                **kwargs,
            ),
        )
        progress: list[float] = []

        async def record_progress(
            current: float,
            _: float | None,
            __: str | None,
        ) -> None:
            progress.append(current)

        async with app.router.lifespan_context(app):
            async with Client(transport) as client:
                with patch(
                    "mcp_examples.tools.sample_tool.asyncio.sleep",
                    new=AsyncMock(),
                ):
                    await client.call_tool(
                        "getSumAsync",
                        meta={"progressToken": "http-progress-test"},
                        progress_handler=record_progress,
                    )

        self.assertEqual(progress, list(range(1, 12)))

    async def test_tool_cancellation_is_not_swallowed(self) -> None:
        async def cancel_sleep(_: float) -> None:
            raise asyncio.CancelledError

        context = AsyncMock()
        with patch(
            "mcp_examples.tools.sample_tool.asyncio.sleep",
            new=cancel_sleep,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await anext(Mysubscription().getSumAsync(context))


class MCPClientInteractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_can_answer_input_required_request(self) -> None:
        async def accept_confirmation(*_: object) -> dict[str, bool]:
            return {"confirmed": True}

        async with Client(
            create_server(),
            elicitation_handler=accept_confirmation,
        ) as client:
            result = await client.call_tool("confirmWithClient")

        self.assertEqual(
            result.structured_content,
            {"status": "accepted", "confirmed": True},
        )

    async def test_client_without_elicitation_is_rejected_explicitly(self) -> None:
        async with Client(create_server()) as client:
            with self.assertRaisesRegex(ToolError, "does not support elicitation"):
                await client.call_tool("confirmWithClient")


class MCPActivityMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_observes_a_real_inbound_client_request(self) -> None:
        with patch("mcp_examples.server.logger") as logger:
            async with Client(create_server()) as client:
                await client.list_tools()

        logger.info.assert_any_call(
            "MCP client %s method=%r",
            "request",
            "tools/list",
        )

    async def test_inbound_client_messages_are_observed_without_payloads(self) -> None:
        middleware = MCPActivityMiddleware()
        message = {"method": "notifications/cancelled", "params": {"reason": "secret"}}
        context = MiddlewareContext(
            message=message,
            source="client",
            type="notification",
            method="notifications/cancelled",
        )
        call_next = AsyncMock(return_value=None)

        with patch("mcp_examples.server.logger") as logger:
            await middleware.on_message(context, call_next)

        logger.info.assert_called_once_with(
            "MCP client %s method=%r",
            "notification",
            "notifications/cancelled",
        )
        call_next.assert_awaited_once_with(context)
        self.assertNotIn("secret", repr(logger.info.call_args))


if __name__ == "__main__":
    unittest.main()
