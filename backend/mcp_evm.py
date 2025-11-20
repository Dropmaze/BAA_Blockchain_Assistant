import asyncio
import os
import sys
import re
import requests
from textwrap import dedent
from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from agno.tools.mcp import MCPTools
from agno.tools import tool
from agno.utils import pprint as agno_pprint
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

#Fix for Windows asyncio event loop
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#Determine directory & path to server.py
ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(ROOT, "server.py")



#URL for Coingecko mcp server
#COINGECKO_MCP_CMD = 'npx mcp-remote https://mcp.api.coingecko.com/mcp'



#Initialize a Knowledge Base
knowledge = Knowledge(
    name="baa_knowledge",
    vector_db=LanceDb(
        table_name="baa_knowledge",
        uri="lancedb_data",
        embedder=OllamaEmbedder(
            id="all-minilm",
            dimensions=384,
        ),
    ),
)

#Add all files from the knowledge directory to the knowledge base
knowledge.add_content(
    path="C:/Users/Dylan/Desktop/BAA_Blockchain_Assistant/backend/knowledge"
)

# ======================================
# MCP Tool Call via STDIO Client
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
# Wrapper Tools 
# ======================================

@tool(requires_confirmation=True)
async def send_eth_hitl(to_address: str, amount_eth: float) -> str:
    """Wrapper tool to send ETH, requires manual confirmation."""
    return await call_mcp_tool("send_eth", to_address=to_address, amount_eth=amount_eth)


@tool(requires_confirmation=True)
async def send_erc20_hitl(token_address: str, to_address: str, amount: float) -> str:
    """Wrapper tool to send ERC20 tokens, requires manual confirmation."""
    return await call_mcp_tool(
        "send_erc20_token",
        token_address=token_address,
        to_address=to_address,
        amount=amount,
    )

@tool
async def get_eth_price_chf() -> str:
    """
    Returns the current ETH price in CHF using the CoinGecko public HTTP API.
    """

    def _fetch():
        # CoinGecko simple price API endpoint
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "ethereum", "vs_currencies": "chf"}

        try:
            # Perform HTTP request (blocking)
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()

            # Parse JSON data
            data = resp.json()
            price = data.get("ethereum", {}).get("chf")

            # Validate expected structure
            if price is None:
                return "Der ETH-Preis konnte nicht von der CoinGecko API gelesen werden."

            return f"Der aktuelle ETH-Preis beträgt CHF {price}."

        except requests.exceptions.Timeout:
            return "Die Anfrage an CoinGecko hat zu lange gedauert. Bitte versuche es später erneut."
        except requests.exceptions.RequestException as e:
            return f"Beim Abrufen des ETH-Preises von CoinGecko ist ein Fehler aufgetreten: {e}"
        except Exception:
            return "Es ist ein unbekannter Fehler beim Abrufen des ETH-Preises aufgetreten."

    # Run blocking HTTP call in a thread worker to avoid blocking the event loop
    return await asyncio.to_thread(_fetch)

# ======================================
#Helper Functions
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


#Regex pattern for transaction hash detection
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
        f"Hash: {tx_hash}\n")
    return normalized


# ======================================
#CLI Confirmation Display
# ======================================

def _print_rule(title: str) -> None:
    """Prints a simple section header for CLI output."""
    line = "─" * max(10, len(title) + 2)
    print("\n" + line)
    print(title)
    print(line)

def _confirm_tool_cli(tool) -> bool:
    """Renders a readable confirmation block for the given tool and asks the user to confirm."""
    name = getattr(tool, "tool_name", "")
    args = getattr(tool, "tool_args", {}) or {}

    if name == "send_eth_hitl":
        amount = args.get("amount_eth")
        to_addr = args.get("to_address")

        _print_rule("Bestätigung erforderlich")
        print("Aktion: ETH senden")
        print(f"Betrag: {amount} ETH")
        print(f"Empfängeradresse: {to_addr}")

    elif name == "send_erc20_hitl":
        amount = args.get("amount")
        token_addr = args.get("token_address")
        to_addr = args.get("to_address")

        _print_rule("Bestätigung erforderlich")
        print("Aktion: ERC-20 Token senden")
        print(f"Betrag: {amount}")
        print(f"Token-Adresse: {token_addr}")
        print(f"Empfängeradresse: {to_addr}")

    else:
        # Fallback for unknown tools: show raw name/args
        _print_rule("Bestätigung erforderlich")
        print(f"Aktion: {name}")
        print(f"Argumente: {args}")

    # Ask for confirmation
    while True:
        ans = input("\nMöchtest du diese Aktion ausführen? (y/n): ").strip().lower()
        if ans in ("y", "n"):
            return ans == "y"
        print("Bitte 'y' oder 'n' eingeben um die Aktion auszuführen oder abzubrechen.")


# ======================================
#Agent Execution / HITL Flow
# ======================================

async def run_agent(message: str) -> None:
    """Runs the agent, handles HITL pauses and user confirmations."""
    try:
        async with MCPTools(f'python "{SERVER_PATH}"') as mcp_tools:
            agent = Agent(
                model=Ollama(id="qwen2.5:7b"),
                tools=[mcp_tools, send_eth_hitl, send_erc20_hitl, get_eth_price_chf],
                knowledge=knowledge,
                search_knowledge=True,
                instructions=dedent("""\
                    Du bist ein Ethereum-Agent. Antworte ausschliesslich auf Deutsch und suche 
                    mittels "search_knowledge_base" nach Informationen sofern du eine Frage erhälst und dazu keine passendes Tool findest.
                    - Verwende MCP-Tools für Blockchain-Operatione.
                    - Verwende die CoinGecko HTTP-API für Kurs- und Marktdaten (z.B. Preis von ETH in CHF).
                    - Für "send_eth_hitl" und "send_erc20_hitl" ist IMMER eine Bestätigung nötig.
                    - Wenn eine Transaktion erfolgreich ausgeführt wurde, gib nur eine klare, kurze Bestätigung mit Hash aus.
                    - Wenn Nutzer*innen abstimmen möchte oder eine Abstimmung erwähnt, dann verwende NICHT search_knowledge_base.
                    Nutze stattdessen IMMER folgende DAO-Tools: "dao_find_proposal_by_name" und "_dao_vote".
                    - Fordere danach keine weitere Bestätigung an.
                """),
                markdown=True,
                debug_mode=True,
            )

            run_response = await agent.arun(message)

            # Handle HITL (confirmation) pauses
            while getattr(run_response, "is_paused", False):
                tools_conf = getattr(run_response, "tools_requiring_confirmation", []) or []
                if not tools_conf:
                    print("\nLauf ist pausiert! Keine Tools zur Bestätigung vorhanden.\n")
                    break

                # Friendly, readable CLI confirmation
                for t in tools_conf:
                    t.confirmed = _confirm_tool_cli(t)

                # Continue after gathering all confirmations
                run_response = await agent.acontinue_run(run_response=run_response)

            # Display final output
            text = _extract_text(run_response)
            if text:
                print("\n" + _normalize_tx_text(text) + "\n")
            else:
                print("\nKeine lesbare Ausgabe, zeige Response-Details:\n")
                agno_pprint.pprint_run_response(run_response)

    except Exception as e:
        print(f"\nFehler beim Ausführen des Agenten: {e}\n")



# ======================================
#CLI Loop
# ======================================

if __name__ == "__main__":
    print("\n")
    print("----------------------------------------------------------")
    print("************* E T H E R E U M - A G E N T ****************")
    print("----------------------------------------------------------")
    print("Sensible Aktionen werden erst nach manueller Zustimmung ausgeführt.")
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
        print("\nProgramm beendet.\n")