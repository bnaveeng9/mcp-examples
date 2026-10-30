"""Example FastMCP tools for arithmetic and async streaming demonstrations."""

import asyncio
from collections.abc import AsyncGenerator

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp_types import (
    ElicitRequest,
    ElicitRequestFormParams,
    ElicitResult,
    InputRequiredResult,
)
from pydantic import BaseModel


mcp = FastMCP("subscriptions-mcpserver")


class Mysubscription(BaseModel):
    """Simple subscription-style example model used to expose MCP tools."""

    def getSum(self, a: int, b: int) -> int:
        """Return the product of two integers for a basic arithmetic example."""
        return a * b

    async def getSumAsync(
        self, ctx: Context
    ) -> AsyncGenerator[dict[str, list[int] | int], None]:
        """Yield updates and report MCP progress for each iteration."""
        for j in range(11):
            numbers = list(range(1, 11))
            await asyncio.sleep(1)
            await ctx.report_progress(
                progress=j + 1,
                total=11,
                message=f"Completed iteration {j + 1} of 11",
            )
            yield {
                "list": numbers,
                "sum": sum(numbers),
                "iteration": j,
            }

    def confirmWithClient(
        self, ctx: Context
    ) -> dict[str, bool | str] | InputRequiredResult:
        """Ask the client for confirmation through MCP's input-required flow."""
        session = ctx.session
        capabilities = session.client_capabilities
        if capabilities is None or capabilities.elicitation is None:
            raise ToolError("The connected MCP client does not support elicitation.")

        if ctx.input_responses is None:
            if capabilities.elicitation.form is None:
                raise ToolError(
                    "The connected MCP client does not support form elicitation."
                )
            return InputRequiredResult(
                input_requests={
                    "confirmation": ElicitRequest(
                        params=ElicitRequestFormParams(
                            message="Do you want to confirm this sample operation?",
                            requested_schema={
                                "type": "object",
                                "properties": {
                                    "confirmed": {
                                        "type": "boolean",
                                        "title": "Confirm",
                                    }
                                },
                                "required": ["confirmed"],
                                "additionalProperties": False,
                            },
                        )
                    )
                },
                request_state="confirmation-v1",
            )

        if ctx.request_state != "confirmation-v1":
            raise ToolError("The client confirmation request state is invalid.")

        response = ctx.input_responses.get("confirmation")
        if not isinstance(response, ElicitResult):
            raise ToolError("The client did not return a confirmation response.")
        if response.action != "accept":
            return {"status": response.action}

        confirmed = response.content.get("confirmed") if response.content else None
        if not isinstance(confirmed, bool):
            raise ToolError("The client confirmation response is invalid.")
        return {"status": "accepted", "confirmed": confirmed}


async def main() -> None:
    """Exercise the sample async tool in a local CLI context."""
    obj = Mysubscription()
    mcp.add_tool(obj.getSumAsync)

    ctx = Context(fastmcp=mcp)
    async for result in obj.getSumAsync(ctx):
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
