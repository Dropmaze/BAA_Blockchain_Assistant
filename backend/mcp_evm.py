# mcp_evm.py
import asyncio
import os
import sys
import re
from textwrap import dedent

from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.mcp import MCPTools
from agno.tools import tool
from agno.utils import pprint as agno_pprint

# MCP client (direct invocation)
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

# Fix for Windows asyncio event loop
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Directory + path for server.py
ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(ROOT, "server.py")


# ======================================
#   MCP Tool Call via STDIO Client
# ======================================

async def call_mcp_tool(tool_name: str, **kwargs) -> str:
    """Call an MCP tool directly using the STDIO client interface."""
    params = StdioServerParameters(command="python", args=[SERVER_PATH])

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, kwargs)

            texts = []
            for item in result.content:
                # Handle both SDK object and dict types
                if hasattr(item, "type") and getattr(item, "type") == "text":
                    txt = getattr(item, "text", "")
                    if isinstance(txt, str) and txt.strip():
                        texts.append(txt)
                elif isinstance(item, dict) and item.get("type") == "text":
                    txt = item.get("text", "")
                    if isinstance(txt, str) and txt.strip():
                        texts.append(txt)

            return "\n".join(texts) if texts else ""


# ======================================
#   Wrapper Tools (Human-in-the-Loop)
# ======================================

@tool(requires_confirmation=True)
async def send_eth_hitl(to_address: str, amount_eth: float) -> str:
    """Wrapper tool to send ETH — requires manual confirmation."""
    return await call_mcp_tool("send_eth", to_address=to_address, amount_eth=amount_eth)


@tool(requires_confirmation=True)
async def send_erc20_hitl(token_address: str, to_address: str, amount: float) -> str:
    """Wrapper tool to send ERC20 tokens — requires manual confirmation."""
    return await call_mcp_tool(
        "send_erc20_token",
        token_address=token_address,
        to_address=to_address,
        amount=amount,
    )


# ======================================
#   Helper Functions
# ======================================

def _extract_text(rr) -> str | None:
    """Extracts plain text content from a RunResponse object."""
    if getattr(rr, "output_text", None):
        return rr.output_text

    out = getattr(rr, "output", None)
    if isinstance(out, str) and out.strip():
        return out
    if isinstance(out, dict):
        for key in ("text", "content", "message", "markdown"):
            val = out.get(key)
            if isinstance(val, str) and val.strip():
                return val

    msgs = getattr(rr, "messages", None)
    if isinstance(msgs, list) and msgs:
        for m in reversed(msgs):
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
            if role == "assistant":
                content = getattr(m, "content", None) if not isinstance(m, dict) else m.get("content")
                if isinstance(content, str) and content.strip():
                    return content
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") in ("text", "markdown"):
                            txt = item.get("text") or item.get("markdown")
                            if isinstance(txt, str) and txt.strip():
                                return txt
    return None


# Regex pattern for transaction hash detection
_TX_HASH_RE = re.compile(r"\b(0x)?[A-Fa-f0-9]{64}\b")

def _normalize_tx_text(text: str) -> str:
    """Formats text if a transaction hash is found."""
    match = _TX_HASH_RE.search(text)
    if not match:
        return text

    tx_hash = match.group(0)
    normalized = (
        "\nTransaktion erfolgreich übermittelt\n"
        "-----------------------------------\n"
        f"Hash: {tx_hash}\n"
    )
    return normalized


# ======================================
#   Agent Execution / HITL Flow
# ======================================

async def run_agent(message: str) -> None:
    """Runs the agent, handles HITL pauses and user confirmations."""
    try:
        async with MCPTools(f'python "{SERVER_PATH}"') as mcp_tools:
            agent = Agent(
                model=Ollama(id=os.getenv("LLM_MODEL", "qwen2.5:3b")),
                tools=[mcp_tools, send_eth_hitl, send_erc20_hitl],
                instructions=dedent("""\
                    Du bist ein Ethereum-Agent. Antworte ausschliesslich auf Deutsch.
                    - Verwende MCP-Tools für Blockchain-Operationen.
                    - Für `send_eth_hitl` und `send_erc20_hitl` ist IMMER eine Bestätigung nötig.
                    - Wenn eine Transaktion erfolgreich ausgeführt wurde, 
                      gib nur eine klare, kurze Bestätigung mit Hash aus.
                    - Fordere danach keine weitere Bestätigung an.
                """),
                markdown=True,
                #debug_mode=True,
            )

            run_response = await agent.arun(message)

            # Handle Human-in-the-Loop (confirmation) pauses
            while getattr(run_response, "is_paused", False):
                tools_conf = getattr(run_response, "tools_requiring_confirmation", []) or []
                if not tools_conf:
                    print("\nLauf ist pausiert, aber keine Tools zur Bestätigung vorhanden.\n")
                    break

                print("\nBestätigung erforderlich:\n")
                for i, t in enumerate(tools_conf, start=1):
                    print(f"{i}. {t.tool_name} mit Argumenten: {t.tool_args}")

                for t in tools_conf:
                    while True:
                        ans = input(f"Ausführen von {t.tool_name}? (y/n): ").strip().lower()
                        if ans in ("y", "n"):
                            t.confirmed = (ans == "y")
                            break
                        print("Bitte 'y' oder 'n' eingeben.\n")

                run_response = await agent.acontinue_run(run_response=run_response)

            # Display final output
            text = _extract_text(run_response)
            if text:
                print("\n" + _normalize_tx_text(text) + "\n")
            else:
                print("\nKeine lesbare Ausgabe – zeige Response-Details:\n")
                agno_pprint.pprint_run_response(run_response)

    except Exception as e:
        print(f"\nFehler beim Ausführen des Agenten: {e}\n")


# ======================================
#   CLI Loop
# ======================================

if __name__ == "__main__":
    print("\n")
    print("------------------------------------")
    print("********** Ethereum Agent **********")
    print("------------------------------------")
    print("\n")
    print("Tippe 'exit' oder 'quit' zum Beenden.\n")
    print("\n")
    try:
        while True:
            user_text = input("Eingabe: ").strip()
            if user_text.lower() in ("exit", "quit"):
                print("\nProgramm beendet.\n")
                break
            if not user_text:
                continue
            asyncio.run(run_agent(user_text))
    except (KeyboardInterrupt, EOFError):
        print("\nProgramm beendet\n")