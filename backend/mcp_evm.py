import asyncio
import os
from textwrap import dedent
from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.mcp import MCPTools


#The directory where this file (mcp_evm.py) is located
ROOT = os.path.dirname(os.path.abspath(__file__))
#Full path to your server.py file
SERVER_PATH = os.path.join(ROOT, "server.py")


async def run_agent(message: str) -> None:
    """Run the Ethereum Blockchain Assistant agent with the given message."""

    try:
        async with MCPTools(f'python "{SERVER_PATH}"') as mcp_tools:
            agent = Agent(
                model=Ollama(id=os.getenv("LLM_MODEL", "qwen2.5:3b")),
                tools=[mcp_tools],
                instructions=dedent("""\
                    Du bist ein Ethereum-Agent. Antworte ausschließlich auf Deutsch.
                    Verwende klare, knappe Formulierungen und bleibe technisch präzise.
                """),
                markdown=True,
                debug_mode=True,
            )

            # Run the agent
            await agent.aprint_response(message, stream=True)
    except Exception as e:
        print(f"Error while running the agent: {e}")


# Example usage
if __name__ == "__main__":
    # Basic example - exploring project license
    asyncio.run(run_agent("Wie hoch ist der Token Saldo der Adresse 0xdd2fd4581271e230360230f9337d5c0430bf44c0?"))

