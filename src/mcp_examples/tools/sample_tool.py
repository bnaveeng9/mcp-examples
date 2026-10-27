import asyncio
from collections.abc import AsyncGenerator
from fastmcp import FastMCP
from pydantic import BaseModel


mcp = FastMCP("subscriptions-mcpserver")


class Mysubscription(BaseModel):
    """ This class is a subscription defined class """

    def getSum(a: int, b: int) -> int:
        return a*b

    
    async def getSumAsync() -> AsyncGenerator[dict[str, list[int] | int], None]:
        j=0
        while j <=10: 
            numbers = list(range(1, 11))
            await asyncio.sleep(1)
            yield {
                "list": numbers,
                "sum": sum(numbers),
            }
        

async def main():
    obj = Mysubscription()
    mcp.add_tool(obj.getSumAsync)

    async for result in obj.getSumAsync():
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
