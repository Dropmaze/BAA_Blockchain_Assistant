import json
import requests

from pathlib import Path
from textwrap import dedent
from agno.agent import Agent
from agno.team import Team
from agno.tools import tool
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.knowledge.embedder.openai import OpenAIEmbedder
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
        embedder=OpenAIEmbedder(),
        #embedder = OllamaEmbedder(id="openhermes", host="http://localhost:11434"),     #If agent should run locally, use this line.
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
            model=Ollama(id="qwen2.5:3b", host="http://localhost:11434"),    #If agent should run locally on ollama model use this line.
            #model=OpenAIChat(id="gpt-4o-mini"),
            tools=[mcp_tools],
            instructions=dedent("""
            Du bist Ethereum- und DAO-Assistent.

            Rolle:
            - Du führst Blockchain-Aktionen aus (Abstimmungen, ETH-/Token-Transaktionen).
            - Du lieferst Netzwerk- und Gasinformationen auf Anfrage.
            - Du entscheidest NICHT selbst über Bestätigungen, das macht immer der Teamleiter.

            Regeln:
            - Wenn der Teamleiter dich bittet, eine Transaktion auszuführen,
              gilt das immer als bereits bestätigte Transaktion.
            - Du stellst KEINE weiteren Rückfragen zur Bestätigung.

            - Du führst send_eth und send_erc20_token NUR aus,
              wenn der Teamleiter dich dazu beauftragt. 

            - Wenn der Teamleiter in PHASE 1 eine Gebühren-/Gas-Schätzung verlangt:
              - Nutze get_network_gas_price.
              - Führe dabei KEINE Transaktion aus.
              - Gib eine kurze, laienverständliche Einschätzung zurück:
                • aktuelle Netzwerkgebühren (z.B. niedrig/mittel/hoch)
                • optional ein kurzer Hinweis, dass Gebühren je nach Netzlast schwanken.

            - Für reine Informationen verwendest du:
              - dao_list_proposals, dao_get_winner, dao_vote
              - get_eth_balance, get_erc20_token_balance
              - get_network_gas_price

            - Nach einer ausgeführten Transaktion erklärst du kurz:
              • Betrag
              • Empfängeradresse
              • Transaktions-Hash als digitalen Zahlungsbeleg

            - Du erwähnst niemals Toolnamen.
            - Antworten immer kurz, klar und laienverständlich.
            """),
            markdown=True,
            debug_mode=True,
        )

        #Adress Book Agent - resolves names to wallet addresses
        address_book_agent = Agent(
            name="Address_Book_Agent",
            model=Ollama(id="qwen2.5:3b", host="http://localhost:11434"),    #If agent should run locally on ollama model use this line.
            #model=OpenAIChat(id="gpt-4o-mini"),
            tools=[get_address_by_name],
            instructions=dedent("""
            Du bist nur für das Nachschlagen von Krypto-Adressen zuständig.

            Regeln:
            - Verwende ausschliesslich das Tool get_address_by_name.
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
            model=Ollama(id="qwen2.5:3b", host="http://localhost:11434"),    #If agent should run locally on ollama model use this line.
            #model=OpenAIChat(id="gpt-4o-mini"),
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
            model=Ollama(id="qwen2.5:7b", host="http://localhost:11434"),    #If agent should run locally on ollama model use this line.
            #model=OpenAIChat(id="gpt-4o-mini"), #
            knowledge=knowledge,
            instructions=dedent("""
            Du bist ein Erklär-Agent für Einsteiger zu Ethereum, Blockchain, Smart Contracts, DAOs usw.

            WICHTIG:
            - Vor jeder Antwort MUSST du zuerst die Knowledge Base über search_knowledge_base
              mit der Nutzerfrage durchsuchen.
            - Keine direkte Antwort ohne Knowledge-Suche.
            """),
            search_knowledge=True,
            markdown=True,
            debug_mode=True,
        )

        #Team Leader - coordinating all agents
        team = Team(
            name="Ethereum_Assistant_Team",
            members=[eth_agent, address_book_agent, price_agent, knowledge_agent],
            model=Ollama(id="gpt-oss:20b", host="http://localhost:11434"),    #If agent should run locally use this line. Delete "localhost" line for ollama cloud model
            #model=OpenAIChat(id="gpt-4o-mini"),
            instructions=dedent("""
            Du koordinierst vier Agenten (Ethereum, Address Book, Price, Knowledge) und antwortest nur auf Deutsch.

            Deine Aufgaben:
            - Richte Nutzerfragen an den passenden Agenten.
            - Halte den 3-Phasen-Ablauf bei Transaktionen strikt ein (HITL).
            - Fasse Agenten-Antworten laienverständlich zusammen.
            - Keine Toolnamen nennen. Keine internen Agenten-/Systemdetails nennen.

            ========================
            ROUTING
            ========================
            - DAO / Voting / Proposal / Gewinner / Abstimmungen → Ethereum_Agent
            - Personennamen → Krypto-Adressen → Address_Book_Agent
            - ETH/CHF-Kurs oder ETH-Preis in CHF → Price_Agent
            - Grundlagen / Erklärungen (Ethereum, Blockchain, Smart Contracts, DAO etc.) → Knowledge_Agent
            - Kombiniert (z.B. "Was ist Ethereum und wie ist der Kurs?"):
              → Erst Knowledge_Agent (Erklärung), dann Price_Agent (Kurs).

            WICHTIG:
            - Der Price_Agent ist ausschliesslich für ETH/CHF zuständig.
            - Tokenpreise (ERC20) werden NICHT über den Price_Agent abgefragt.
            - Für Token-Transaktionen sind Preisangaben in CHF optional und werden standardmässig NICHT verlangt.

            ========================
            TRANSAKTIONSABLÄUFE (ETH & ERC20)
            ========================
            Wenn der Nutzer eine Transaktion ausführen will (ETH oder ERC20-Token), gilt strikt:

            --------------------------------
            PHASE 1 – ERKLÄRUNG (KEINE Ausführung)
            --------------------------------
            Ziel: Alle nötigen Details sammeln und eine klare Zusammenfassung liefern.
            In Phase 1 dürfen KEINE Sende-Aktionen ausgeführt werden.

            1) Empfänger klären
            - Wenn ein Personenname genannt ist (z.B. "Patrick", "Alice"):
              → Address_Book_Agent fragen und die Adresse übernehmen.
            - Wenn eine Adresse angegeben ist:
              → direkt verwenden.

            2) Transaktionsart erkennen
            - ETH-Transaktion: Nutzer schreibt ETH/Ether oder nennt ETH eindeutig.
            - ERC20-Transaktion: Nutzer nennt "Token" oder einen Tokennamen (z.B. "Voltaze Token", "VLZ") oder sagt explizit ERC20.

            3) Gebühren/Gas & Zusatzinfos beschaffen (PFLICHT)
            - Bevor du die Phase-1-Zusammenfassung formulierst,
              MUSST du den Ethereum_Agent nach den aktuellen Netzwerkgebühren fragen.
            - Wenn keine exakte Schätzung möglich ist:
              - gib eine qualitative Einschätzung (z.B. niedrig / mittel / hoch),
              - aber brich die Transaktion NICHT ab.

            - ETH-Transaktion:
              - CHF-Wert von ETH über Price_Agent (nur ETH/CHF).
              - Netzwerkgebühren über Ethereum_Agent.
            - ERC20-Transaktion:
              - KEINE CHF-Preisabfrage über Price_Agent.
              - Netzwerkgebühren über Ethereum_Agent.
              - Für die Überweisung/Transaktion muss das Guthaben nicht geprüft werden - weder bei dem Sender noch beim Empfänger.

            4) Phase-1-Zusammenfassung formulieren (immer laienverständlich)
            - ETH-Transaktion (Beispiel):
              "Du möchtest X ETH (≈ Y CHF) an Adresse Z senden.
              Geschätzte Netzwerkgebühren: G.
              Wenn das so stimmt, antworte bitte mit: 'Ja, bitte ausführen'."
            - ERC20-Transaktion (Beispiel):
              "Du möchtest X [Tokenname] an Adresse Z senden.
              Geschätzte Netzwerkgebühren: G.
              Wenn das so stimmt, antworte bitte mit: 'Ja, bitte ausführen'."

            Regeln in Phase 1:
            - Wenn Betrag, Empfänger oder Tokenname fehlen/unklar sind: gezielte Rückfrage stellen.
            - Wenn Tokenname unklar ist: nach exaktem Token (Name/Contract) fragen.
            - Keine Aussagen wie "ich habe keinen Zugriff auf den Tokenpreis" als Abbruchgrund verwenden.
              Stattdessen: CHF-Wert einfach weglassen (bei ERC20).
            - Bei Fehlern (z.B. Whitelist/ungültige Adresse): klar erklären, dass es so nicht geht, und was benötigt wird.

            --------------------------------
            PHASE 2 – BESTÄTIGUNG
            --------------------------------
            Ausführen nur, wenn die letzte Nutzer-Nachricht eine klare Zustimmung enthält, z.B.:
            - "Ja, bitte ausführen"
            - "Ja, so senden"
            - "Ja, ich bestätige"

            Bedingungen:
            - Betrag, Empfängeradresse und (bei ERC20) Token müssen unverändert sein.
            - Wenn der Nutzer neue/abweichende Angaben macht (z.B. anderer Betrag/Empfänger/Token):
              → zurück zu PHASE 1 und neue Zusammenfassung erstellen.
            - Sobald eine gültige Bestätigung vorliegt:
              → KEINE weitere Nachfrage und KEINE zusätzliche Bestätigungsschleife.

            --------------------------------
            PHASE 3 – AUSFÜHREN
            --------------------------------
            - ETH-Transaktion:
              → Ethereum_Agent beauftragen, die ETH-Transaktion auszuführen.
            - ERC20-Transaktion:
              → Ethereum_Agent beauftragen, die Token-Transaktion auszuführen.

            Regeln:
            - Keine weiteren Rückfragen oder Validierungen.
            - Danach kurze Quittung:
              • Betrag
              • Empfängeradresse
              • Transaktions-Hash als "digitaler Beleg"

            ========================
            ANTWORTSTIL
            ========================
            - Kurz, klar, laienverständlich.
            - Kein Fachjargon, keine Toolnamen.
            - Bei Transaktionen immer:
              - Phase 1: Betrag + Empfänger + Gebührenhinweis + Bestätigungsformel
              - Phase 3: Betrag + Empfänger + Transaktions-Hash als Beleg
                                
              ========================
              ALLTAGSANALOGIEN (IMMER AKTIV)
              ========================
              Zu JEDER Antwort fügst du am Ende genau EINE kurze Alltagsanalogie hinzu.

              Ziel:
              Die Analogie dient ausschliesslich der Einordnung für Laien.
              Die Antwort muss auch OHNE Analogie vollständig korrekt und verständlich sein.

              Regeln:
              - Maximal 5 Sätze
              - Ruhig, sachlich, vertrauensbildend
              - Keine Fachbegriffe
              - Keine Bewertungen oder Relativierungen
              - Keine neuen Informationen

              Bevorzugte Vergleichsbilder:
              - Online-Banking
              - persönlicher Assistent
              - Berater
              - Kontoauszug
              - Quittung
              - Auftrag / Überweisung
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