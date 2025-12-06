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
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools
from agno.vectordb.lancedb import LanceDb
from agno.db.sqlite import SqliteDb


# =============================
# Knowledge Base Setup
# =============================

# Path to the custom knowledge base folder
ROOT = Path(__file__).parent
KNOWLEDGE_PATH = ROOT / "knowledge"

# Create a LanceDB-backed vector knowledge base
# Used by the Knowledge_Agent for explanations
knowledge = Knowledge(
    name="baa_knowledge",
    vector_db=LanceDb(
        table_name="baa_knowledge",
        uri="lancedb_data",
        embedder = OllamaEmbedder(id="openhermes"),
    ),
)

# Load all documents inside /knowledge (PDFs, Markdown, etc.)
knowledge.add_content(
    path=str(KNOWLEDGE_PATH)
)


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
# Agent Runner
# =============================

async def run_agent(message: str, session_id: str | None = None) -> str:
    """Führt das Agent-Team aus und verarbeitet eine Nutzeranfrage."""

    async with MCPTools("python mcp_server.py") as mcp_tools:
        
        #Ethereum Agent - handles real blockchain operations via MCP server
        eth_agent = Agent(
            name="Ethereum_Agent",
            model=Ollama(id="qwen2.5:7b"),
            tools=[mcp_tools], # Provides access to onchain commands
            instructions=dedent("""
            Du bist Ethereum- und DAO-Assistent.

            Rolle:
            - Du führst Blockchain-Aktionen aus (Abstimmungen, ETH-/Token-Transaktionen, Gas-Infos).
            - Du entscheidest NICHT selbst über Bestätigungen, das macht immer der Teamleiter.

            Regeln:
            - Wenn der Teamleiter dich bittet, eine Transaktion auszuführen,
              gilt das immer als bereits bestätigte Transaktion.
            - Du stellst KEINE weiteren Rückfragen zur Bestätigung.
            - Du führst send_eth und send_erc20_token direkt aus, wenn du dazu beauftragt wirst.
            - Für Infos verwendest du:
              - dao_list_proposals, dao_get_winner, dao_vote
              - get_eth_balance, get_erc20_token_balance
              - get_network_gas_price
            - Nach einer Transaktion erklärst du in einfachen Worten,
              was passiert ist (Betrag, Empfänger, Transaktions-Hash).
            - Du erwähnst niemals Toolnamen.
            - Antworten knapp und laienverständlich halten.
            """),
            markdown=True,
            debug_mode=True,
        )

        #Adress Book Agent - resolves names to wallet addresses
        address_book_agent = Agent(
            name="Address_Book_Agent",
            model=Ollama(id="qwen2.5:3b"),
            tools=[get_address_by_name],
            instructions=dedent("""
            Du bist nur für das Nachschlagen von Krypto-Adressen zuständig.

            Regeln:
            - Verwende ausschließlich das Tool get_address_by_name.
            - Keine Erklärungen zu Blockchain, DAO, Transaktionen etc.
            - Antworte nur mit:
              - gefundener Adresse oder
              - klarer Fehlermeldung, wenn kein Eintrag existiert.
            - Antwort kurz, ohne Zusatztexte.
            """),
            markdown=True,
            debug_mode=True,
        )

        #Price Agent - provides ETH/CHF exchange rate via CoinGecko API
        price_agent = Agent(
            name="Price_Agent",
            model=Ollama(id="qwen2.5:3b"),
            tools=[get_eth_chf_price],
            instructions=dedent("""
            Du bist nur für ETH/CHF-Preisabfragen zuständig.

            Regeln:
            - Wenn nach Preis oder Kurs von ETH/Ethereum in CHF gefragt wird,
              nutze IMMER das Tool get_eth_chf_price.
            - Erfinde niemals einen Kurs, nutze nur das Tool-Ergebnis.
            - Antworte kurz, z.B.:
              "1 ETH entspricht aktuell ca. X CHF. Der Kurs kann sich laufend ändern."
            """),
            markdown=True,
            #debug_mode=True,
        )
        
        #Knowledge Agent - provides friendly explanations using the custom knowledge base
        knowledge_agent = Agent(
            name="Knowledge_Agent",
            model=Ollama(id="qwen2.5:3b"),
            knowledge=knowledge,
            instructions=dedent("""
            Du bist ein Erklär-Agent für Einsteiger zu Ethereum, Blockchain, Smart Contracts, DAOs usw.

            WICHTIG:
            - Vor jeder Antwort MUSST du zuerst die Knowledge Base über search_knowledge_base
              mit der Nutzerfrage durchsuchen (dies passiert automatisch).
            - Formuliere danach eine kurze, einfache Erklärung in eigenen Worten.
            - Keine direkte Antwort ohne Knowledge-Suche.
            - Erkläre so, dass auch absolute Anfänger es verstehen.
            """),
            search_knowledge=True,
            markdown=True,
            debug_mode=True,
        )

        #Team Leader - coordinating all agents
        team = Team(
            name="Ethereum_Assistant_Team",
            members=[eth_agent, address_book_agent, price_agent, knowledge_agent],
            model=OpenAIChat(id="gpt-4o-mini"),
            instructions=dedent("""
            Du koordinierst vier Agenten (Ethereum, Address Book, Price, Knowledge) und
            antwortest nur auf Deutsch.

            Deine Aufgaben:
            - Richte Nutzerfragen an den passenden Agenten.
            - Halte den 3-Phasen-Ablauf bei Transaktionen strikt ein.
            - Fasse Agenten-Antworten laienverständlich zusammen.

            ========================
            ROUTING
            ========================
            - DAO / Voting / Proposal / Gewinner → Ethereum_Agent
            - Personennamen → Krypto-Adressen → Address_Book_Agent
            - ETH/CHF-Kurs → Price_Agent
            - Grundlagen / Erklärungen → Knowledge_Agent
            - Kombiniert (z.B. "Was ist Ethereum und wie ist der Kurs?"):
              → Erst Knowledge_Agent (Erklärung), dann Price_Agent (Kurs).

            ========================
            TRANSAKTIONSABLÄUFE
            ========================
            Wenn der Nutzer eine ETH- oder Token-Transaktion ausführen will:

            PHASE 1 – ERKLÄRUNG (KEINE Ausführung)
            - Adressauflösung (falls Name) über Address_Book_Agent.
            - Betrag, CHF-Wert und Gas-/Gebührenschätzung über Price_Agent / Ethereum_Agent.
            - Danach eine Zusammenfassung formulieren, z.B.:
              "Du möchtest X ETH (~Y CHF) an Adresse Z senden.
               Geschätzte Gebühren: G.
               Wenn das so stimmt, antworte bitte mit: 'Ja, bitte ausführen'."
            - In dieser Phase dürfen KEINE Tools zum Senden aufgerufen werden.

            PHASE 2 – BESTÄTIGUNG
            - Ausführen nur, wenn die letzte Nutzer-Nachricht eine klare Zustimmung enthält
              (z.B. "Ja, bitte ausführen", "Ja, so senden", "Ja, ich bestätige").
            - Betrag und Empfänger müssen unverändert sein.
            - Keine widersprüchlichen neuen Angaben.

            WICHTIG:
            - Sobald eine gültige Bestätigung vorliegt → KEINE weitere Nachfrage.
            - Keine zweite oder dritte Bestätigungs-Schleife.

            PHASE 3 – AUSFÜHREN
            - Direkt den Ethereum_Agent beauftragen, die Transaktion auszuführen
              (send_eth oder send_erc20_token).
            - Keine weiteren Rückfragen oder Validierungen.
            - Danach kurze Quittung für den Nutzer:
              • Betrag
              • Empfängeradresse
              • Transaktions-Hash als "digitaler Beleg"

            ========================
            ANTWORTSTIL
            ========================
            - Immer laienfreundlich, kurz und klar.
            - Kein Fachjargon, keine Toolnamen.
            - Besonders bei Transaktionen:
              - Betrag + Empfänger nennen
              - Hinweis, dass der Hash eine Art digitaler Zahlungsbeleg ist.
            """),
            markdown=True,
            debug_mode=True,

            # Enables persistent multi-turn memory
            db=SqliteDb(db_file="tmp/ethereum_team.db"),
            add_history_to_context=True,
        )

        # Execute the team run
        run_response = await team.arun(message, session_id=session_id)

        # Return the final answer to the UI
        if hasattr(run_response, "content") and isinstance(run_response.content, str):
            return run_response.content

        return str(run_response)