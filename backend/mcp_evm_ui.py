import asyncio
import os
import sys
from textwrap import dedent
from agno.agent.agent import Agent
from agno.models.ollama import Ollama
from agno.os import AgentOS
from agno.os.interfaces.agui import AGUI
from agno.tools import tool
from agno.tools.mcp import MCPTools
import uvicorn

#Windows Fix
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#The directory where this file (mcp_evm.py) is located
ROOT = os.path.dirname(os.path.abspath(__file__))

#Full path to your server.py file
SERVER_PATH = os.path.join(ROOT, "server.py") 


#Wrapper-Tools HITL Confirmation
@tool(requires_confirmation=True)
async def send_eth_hitl(to_address: str, amount_eth: float) -> str:
    """Führt einen ETH-Transfer aus – nur nach Bestätigung durch den Benutzer."""
    async with MCPTools(f'python "{SERVER_PATH}"') as mcp:
        return await mcp.execute("send_eth", to_address=to_address, amount_eth=amount_eth)
    
@tool(requires_confirmation=True)
async def send_erc20_hitl(token_address: str, to_address: str, amount: float) -> str:
    """Führt einen ERC20-Transfer aus – nur nach Bestätigung durch den Benutzer."""
    async with MCPTools(f'python "{SERVER_PATH}"') as mcp:
        return await mcp.execute(
            "send_erc20_token",
            token_address=token_address,
            to_address=to_address,
            amount=amount,
        )

async def main():
    # MCP-Server start
    async with MCPTools(f'python "{SERVER_PATH}"') as mcp_tools:
        agent = Agent(
            name="Ethereum-Agent",
            model=Ollama(id=os.getenv("LLM_MODEL", "qwen2.5:3b")),
            tools=[mcp_tools, send_eth_hitl, send_erc20_hitl],
            instructions=dedent("""\
                Du bist ein Ethereum-Agent. Antworte ausschliesslich auf Deutsch.
                - Verwende Tools aus dem MCP-Server für Blockchain-Abfragen.
                - Für "send_eth_hitl" und "send_erc20_hitl" ist IMMER eine Bestätigung nötig.
                - Andere Tools dürfen direkt ausgeführt werden.
                - Sei technisch präzise und knapp.
            """),
            markdown=True,
            debug_mode=True,
        )

        agent_os = AgentOS(agents=[agent], interfaces=[AGUI(agent=agent)])
        app = agent_os.get_app()

        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8000,
            reload=False,
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

    # Basic example - exploring project license
    #asyncio.run(run_agent("Wie hoch ist der Token Saldo der Adresse 0xdd2fd4581271e230360230f9337d5c0430bf44c0?"))
