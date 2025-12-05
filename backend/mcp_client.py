import json
import requests

from pathlib import Path
from textwrap import dedent
from agno.agent import Agent
from agno.team import Team
from agno.tools import tool
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.models.ollama import Ollama
from agno.tools.mcp import MCPTools
from agno.utils import pprint
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from agno.vectordb.lancedb import LanceDb

# =============================
# Knowledge Base
# =============================

ROOT = Path(__file__).parent
KNOWLEDGE_PATH = ROOT / "knowledge"

knowledge = Knowledge(
    name="baa_knowledge",
    vector_db=LanceDb(
        table_name="baa_knowledge",
        uri="lancedb_data",
        embedder = OllamaEmbedder(id="openhermes"),
    ),
)

knowledge.add_content(
    path=str(KNOWLEDGE_PATH)
)

# =============================
# Helper Functions for Tool Calls
# =============================

ROOT = Path(__file__).parent
SERVER_PATH = ROOT / "mcp_server.py"


async def call_mcp_tool(tool_name: str, **kwargs) -> str:
    """
    Ruft ein MCP-Tool im mcp_server.py direkt über den MCP-Client auf
    und gibt den Text-Output zurück.
    """
    params = StdioServerParameters(
        command="python",
        args=[str(SERVER_PATH)],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, kwargs)

            texts: list[str] = []

            for item in result.content:

                if hasattr(item, "type") and getattr(item, "type") == "text":
                    txt = getattr(item, "text", "")
                    if isinstance(txt, str) and txt.strip():
                        texts.append(txt)

                elif isinstance(item, dict) and item.get("type") == "text":
                    txt = item.get("text", "")
                    if isinstance(txt, str) and txt.strip():
                        texts.append(txt)

            return "\n".join(texts) if texts else ""


# =============================
# Tools
# =============================

@tool(show_result=True, stop_after_tool_call=True)
def get_address_by_name(name: str) -> str:
    """
    Liest eine lokale JSON-Datei und gibt die passende Krypto-Adresse zurück.
    Args: name (str): Name der Person.
    """
    address_book_path = Path(__file__).parent / "address_book.json"

    with address_book_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    address = data.get(name)
    if address is None:
        return f"Kein Eintrag für '{name}' im Adressbuch gefunden."
    
    return f"Die Adresse von {name} lautet {address}."


@tool(name="get_eth_chf_price", show_result=True, stop_after_tool_call=True)
def get_eth_chf_price() -> str:
    """
    Ruft den aktuellen ETH/CHF-Kurs über eine öffentliche HTTP-API ab.
    Gibt eine kurze, laienverständliche Erklärung zurück.
    """
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "chf"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()

        price = data["ethereum"]["chf"]
        return f"1 ETH entspricht aktuell ungefähr {price:.2f} CHF (Quelle: CoinGecko)."

    except Exception as e:
        return f"Fehler beim Abrufen des ETH/CHF-Kurses: {e}"



# =============================
# Wrapper Tools for Confirmation
# =============================

@tool(name="send_eth_hitl")
async def send_eth_hitl(to_address: str, amount_eth: float) -> str:
    """
    Sicherer Wrapper für MCP-Tool 'send_eth'.
    Fragt den User direkt im Terminal nach einer Bestätigung.
    """
    print("\nAnfrage zum Senden von ETH")
    print(f"   Empfänger: {to_address}")
    print(f"   Betrag:    {amount_eth} ETH")
    answer = input("Willst du diese Transaktion wirklich ausführen? [y/n] ").strip().lower()

    if answer != "y":
        return "Die ETH-Transaktion wurde vom Nutzer abgebrochen."

    return await call_mcp_tool(
        "send_eth",
        to_address=to_address,
        amount_eth=amount_eth,
    )

@tool(name="send_erc20_hitl")
async def send_erc20_hitl(to_address: str, amount: float) -> str:
    """
    Sicherer Wrapper für MCP-Tool 'send_erc20_token'.
    Fragt den User direkt im Terminal nach einer Bestätigung.
    """
    print("\nAnfrage zum Senden von Voltaze (ERC20)")
    print(f"   Empfänger: {to_address}")
    print(f"   Betrag:    {amount} Voltaze")
    answer = input("Willst du diese Transaktion wirklich ausführen? [y/n] ").strip().lower()

    if answer != "y":
        return "Die Token-Transaktion wurde vom Nutzer abgebrochen."

    return await call_mcp_tool(
        "send_erc20_token",
        to_address=to_address,
        amount=amount,
    )




# =============================
# Agent Runner
# =============================

async def run_agent(message: str) -> str:
    """Führt das Agent-Team aus und verarbeitet eine Nutzeranfrage."""

    async with MCPTools("python mcp_server.py") as mcp_tools:
        
        #Ethereum Agent
        eth_agent = Agent(
            name="Ethereum_Agent",
            model=Ollama(id="qwen2.5:3b"),
            tools=[mcp_tools, send_eth_hitl, send_erc20_hitl],
            instructions=dedent("""
            Du bist Ethereum- und DAO-Assistent.

            Nutze die Tools aus dem MCP-Server:
            - Für Abstimmungen, DAO, Proposals, Voting:
            - dao_list_proposals für "laufende Abstimmungen" / Übersicht
            - dao_get_winner für den aktuellen Gewinner
            - dao_vote, wenn der Nutzer eine Stimme abgeben will
            - Für ETH und Token:
            - get_eth_balance, get_erc20_token_balance
            - send_eth_hitl für ETH-Transaktionen
            - send_erc20_hitl für ERC20-Transaktionen

            Wenn eine Frage nach "Abstimmung", "Proposal", "Vote", "DAO" klingt,
            verwende IMMER die dao_* Tools.

            Antworte kurz und sachlich und erwähne das genutzte Tool im Text.
            """),
            markdown=True,
            debug_mode=True,
        )

        #Adress Book Agent
        address_book_agent = Agent(
            name="Address_Book_Agent",
            model=Ollama(id="qwen2.5:3b"),
            tools=[get_address_by_name],
            instructions=dedent("""
            Du bist nur für Adressen-Nachschlagen zuständig.

            Verwende ausschließlich das Tool get_address_by_name, wenn der Nutzer
            eine Person mit Namen erwähnt (z.B. "Joel", "Patrick") und nach einer
            Krypto-Adresse gefragt wird.

            Führe KEINE anderen Aufgaben aus und gehe nicht auf DAO- oder
            Blockchain-Fragen ein.

            Antworte nur mit der gefundenen Adresse oder einer klaren Fehlermeldung.
            """),
            markdown=True,
            debug_mode=True,
        )

        #Price Agent
        price_agent = Agent(
            name="Price_Agent",
            model=Ollama(id="qwen2.5:3b"),
            tools=[get_eth_chf_price],
            instructions=dedent("""
            Du bist nur für Preisabfragen zuständig.

            Wenn der Nutzer nach dem aktuellen Preis oder Kurs von ETH/Ethereum
            in CHF fragt (z.B. "Wie viel ist 1 ETH in CHF wert?",
            "Was ist der aktuelle Ethereum-Kurs?", "ETH/CHF Kurs"),
            dann verwende IMMER das Tool get_eth_chf_price.

            Antworte kurz, laienverständlich und nenne den Preis in CHF.
            Füge gerne einen Hinweis hinzu, dass sich der Kurs laufend ändern kann.
            """),
            markdown=True,
            debug_mode=True,
        )
        
        #Knowledge Agent
        knowledge_agent = Agent(
            name="Knowledge_Agent",
            model=Ollama(id="qwen2.5:7b"),
            knowledge=knowledge,
            instructions=dedent("""
            Du bist ein Erklär-Agent für Einsteiger.

            WICHTIG:
            - Du MUSST vor jeder Antwort ZUERST das Tool `search_knowledge_base`
            mit der Nutzerfrage als Query aufrufen.
            - Erst danach darfst du eine Antwort formulieren und dabei die gefundenen Inhalte
            zusammenfassen.
            - Antworte NIEMALS direkt, ohne vorher `search_knowledge_base` verwendet zu haben.
            """),
            search_knowledge=True,
            markdown=True,
            debug_mode=True,
        )

        #Agent Team
        team = Team(
            name="Ethereum_Assistant_Team",
            members=[eth_agent, address_book_agent, price_agent, knowledge_agent],
            model=Ollama(id="qwen2.5:7b"),
            instructions = dedent("""
            Du koordinierst vier Agenten mit unterschiedlichen Aufgaben und Tools und antwortest nur auf Deutsch.

            Routing-Regeln (welcher Agent wann zuständig ist):

            - Wenn die Nutzerfrage Wörter wie "Abstimmung", "Proposal",
            "Vote", "DAO", "Gewinner" enthält:
            → Delegiere an den Agenten, der Tools wie dao_list_proposals,
                dao_get_winner oder dao_vote besitzt (Ethereum_DAO_Agent).

            - Wenn der Nutzer eine Person mit Namen nennt (z.B. "Joel", "Patrick")
            und eine Krypto-Adresse braucht:
            → Delegiere an den Agenten, der das Tool get_address_by_name besitzt
                (Address_Book_Agent).

            - Wenn der Nutzer eine Transaktion (ETH oder Token) ausführen will:
            → Zuerst (falls nötig) Name via get_address_by_name auflösen,
                danach an den Agenten mit send_eth_hitl / send_erc20_hitl delegieren
                (Ethereum_DAO_Agent mit HITL-Wrappern).

            - Wenn die Nutzerfrage nach dem Preis oder Kurs von ETH/Ethereum in CHF fragt
            (z.B. "Wie viel ist 1 ETH in CHF wert?",
            "Was ist der aktuelle Ethereum-Kurs?",
            "ETH/CHF Kurs"):
            → Delegiere an den Agenten, der das Tool get_eth_chf_price besitzt
                (Price_Agent). Du darfst keinen Kurs erfinden!

            - Wenn der Nutzer nach Erklärungen, Grundlagen oder Definitionen fragt,
            z.B.:
            • "Was ist Ethereum?"
            • "Was ist ein Smart Contract?"
            • "Erkläre mir eine DAO."
            • "Was bedeutet Voting / Abstimmung auf der Blockchain?"
            oder allgemein "Erkläre mir das bitte einfach":
            → Delegiere an den Agenten, der mit der Knowledge Base verbunden ist
                (Knowledge_Agent, search_knowledge=True).

            - Bei kombinierten Fragen (z.B. "Was ist Ethereum und wie ist der aktuelle Kurs?"):
            → Zuerst Knowledge_Agent für die Erklärung nutzen,
                danach Price_Agent für den aktuellen Kurs.
            → Fasse die Ergebnisse laienverständlich in einer gemeinsamen Antwort zusammen.

            Nutze IMMER den Agenten mit den passenden Tools und der passenden Rolle.
            Du darfst mehrere Agenten nacheinander verwenden, wenn das für die Frage sinnvoll ist.

            ------------------------------------------------------------
            LAIENVERSTÄNDLICHE AUSGABEN:
            ------------------------------------------------------------
            - Formuliere die endgültige Antwort immer so,
            dass sie auch für absolute Laien verständlich ist.
            - Verwende klare, einfache Sprache. Kein Blockchain-Jargon.
            - Erkläre kurz, was passiert ist (z.B. "Die Zahlung wurde ausgeführt"),
            aber ohne technische Details wie Gas, Nonce, RPC, interne Variablennamen oder Toolnamen.
            - Wenn eine Transaktion ausgeführt wurde:
            • Erwähne Betrag und Empfänger.
            • Gib den Transaktions-Hash an.
            • Erkläre in einem Satz, dass der Hash eine Art "digitaler Beleg"
                ist, mit dem man die Zahlung im Blockchain-Explorer prüfen kann.
            - Bei DAO-Ergebnissen:
            • Beschreibe kurz, worum es geht ("Abstimmung", "Vorschlag", "aktueller Stand").
            • Keine internen Smart-Contract-Begriffe.
            - Bei Preisabfragen:
            • Nenne klar den aktuellen ETH-Preis in CHF, wie er vom zuständigen Agenten
                (Price_Agent) geliefert wurde. Du darfst keinen Kurs erfinden!
            - Wenn Wissen aus der Knowledge Base genutzt wurde:
            • Erkläre die Inhalte in eigenen, einfachen Worten
                und halte die Antwort kurz und gut verständlich.

            Halte das Ergebnis immer kurz, freundlich und gut verständlich.
            ------------------------------------------------------------
            """),
            markdown=True,
            debug_mode=True,
        )
        run_response = await team.arun(message)

        if hasattr(run_response, "content") and isinstance(run_response.content, str):
            return run_response.content

        return str(run_response)


# =============================
# Example usage
# =============================
#if __name__ == "__main__":
    #asyncio.run(run_agent("Was ist das Guthaben auf der Adresse 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266?"))
    #asyncio.run(run_agent("Bitte sende 1 ETH an die Adresse 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"))
    #asyncio.run(run_agent("Bitte überweise 1 Voltaze an die Adresse 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"))
    #asyncio.run(run_agent("Bitte überweise 0.5 ETH an die Adresse von Joel"))
    #asyncio.run(run_agent("Was ist Ethereum und was ist der aktuelle Kurs?"))