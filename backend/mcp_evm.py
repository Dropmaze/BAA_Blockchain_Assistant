import asyncio

from textwrap import dedent

from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.mcp import MCPTools
from mcp import StdioServerParameters


async def run_agent(message: str) -> None:
    """Run the filesystem agent with the given message."""


    # MCP server to access the filesystem (via `npx`)
    #async with MCPTools(
    #        f"fastmcp run /Users/fbweinga/src/AI/Agno/mcp_evm/server.py",  
    #    ) as mcp_tools:
    async with MCPTools(f"/Users/fbweinga/src/AI/Agno/.venv/bin/python /Users/fbweinga/src/AI/Agno/mcp_evm/server.py") as mcp_tools:
        agent = Agent(
            model=Ollama(id="qwen2.5:3b"),
            tools=[mcp_tools],
            instructions=dedent("""\
                You are a Ethereum agent. Help users explore the blockchain.

                - Check the balance of a given Address
            """),
            markdown=True,
            show_tool_calls=True,
            #debug_mode=True,
        )

        # Run the agent
        await agent.aprint_response(message, stream=True)


# Example usage
if __name__ == "__main__":
    # Basic example - exploring project license
    asyncio.run(run_agent("What is the balance of address 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266?"))
    #asyncio.run(run_agent("Please send 1 Token to address 0x70997970C51812dc3A010C7d01b50e0d17dc79C8"))
    #asyncio.run(run_agent("Please send 2 Token to address 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"))
    #asyncio.run(run_agent("Please send 3 Token to address 0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"))
    #asyncio.run(run_agent("What is the token balance of address 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266?"))
    #asyncio.run(run_agent("Please send 10 Token to address 0x70997970C51812dc3A010C7d01b50e0d17dc79C8"))
