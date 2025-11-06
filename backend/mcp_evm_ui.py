import os
import sys
import asyncio
from textwrap import dedent
from agno.agent.agent import Agent
from agno.models.ollama import Ollama
from agno.os import AgentOS
from agno.os.interfaces.agui import AGUI
from agno.tools.mcp import MCPTools
import uvicorn

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#The directory where this file (mcp_evm.py) is located
ROOT = os.path.dirname(os.path.abspath(__file__))
#Full path to your server.py file
SERVER_PATH = os.path.join(ROOT, "server.py") 

async def main():
    # MCP-Server start
    async with MCPTools(f'python "{SERVER_PATH}"') as mcp_tools:
        agent = Agent(
            name="Blockchain Assistent",
            model=Ollama(id=os.getenv("LLM_MODEL", "qwen2.5:3b")),
            tools=[mcp_tools],
            instructions=dedent("""\
                Du bist ein Ethereum-Agent. Antworte ausschließlich auf Deutsch.
                Verwende klare, knappe Formulierungen und bleibe technisch präzise.
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
