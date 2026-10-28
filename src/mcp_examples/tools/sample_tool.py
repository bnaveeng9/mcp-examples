"""Example FastMCP tools for arithmetic and async streaming demonstrations."""

import asyncio
from collections.abc import AsyncGenerator

from fastmcp import FastMCP
from pydantic import BaseModel


mcp = FastMCP("subscriptions-mcpserver")


class Mysubscription(BaseModel):
    """Simple subscription-style example model used to expose MCP tools."""

    def getSum(self, a: int, b: int) -> int:
        """Return the product of two integers for a basic arithmetic example."""
        return a * b

    async def getSumAsync(self) -> AsyncGenerator[dict[str, list[int] | int], None]:
        """Yield a streamed list of numbers and their running total every second."""
        for j in range(11):
            numbers = list(range(1, 11))
            await asyncio.sleep(1)
            yield {
                "list": numbers,
                "sum": sum(numbers),
                "iteration": j,
            }


async def main() -> None:
    """Exercise the sample async tool in a local CLI context."""
    obj = Mysubscription()
    mcp.add_tool(obj.getSumAsync)

    async for result in obj.getSumAsync():
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
