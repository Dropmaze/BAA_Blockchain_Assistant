import asyncio
import json
from pathlib import Path
from textwrap import dedent
from agno.agent import Agent
from agno.team import Team
from agno.tools import tool
from agno.models.ollama import Ollama
from agno.tools.mcp import MCPTools



#=============================
#Tools
#=============================
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



#=============================
#Agent Runner
#=============================
async def run_agent(message: str) -> None:
    """Führt das Agent-Team aus und verarbeitet eine Nutzeranfrage."""

    async with MCPTools("python mcp_server.py") as mcp_tools:
        
        #Ethereum Agent
        eth_agent = Agent(
            model=Ollama(id="qwen2.5:3b"),
            tools=[mcp_tools],
            instructions=dedent("""
                Du bist der Ethereum-Agent. Deine Aufgaben:
                - Du arbeitest ausschließlich mit Ethereum-Adressen (0x...).
                - Du führst On-Chain-Abfragen, Saldenprüfungen und Analysen durch.
                - Wenn dir eine gültige Adresse übergeben wird, führst du die passende Blockchain-Abfrage aus.
                - Du interpretierst keine menschlichen Namen. Namen sind Aufgabe des Adressbuch-Agenten.
            """),
            markdown=True,
            debug_mode=True,
        )

        #Adress Book Agent
        address_book_agent = Agent(
            model=Ollama(id="qwen2.5:3b"),
            tools=[get_address_by_name],
            instructions=dedent("""
                Du bist der Adressbuch-Agent. Deine einzige Aufgabe ist es, menschliche Namen in Ethereum-Adressen umzuwandeln.
                Wenn ein Nutzer einen Namen verwendet:
                - Nutze ausnahmslos das Tool "get_address_by_name", um die passende Adresse nachzuschlagen.
                - Gib als Antwort ausschließlich die gefundene Adresse oder eine klare Meldung zurück,
                  wenn kein Eintrag existiert.
                - Führe keine Blockchain-Abfragen oder Analysen durch.
            """),
            markdown=True,
            debug_mode=True,
        )

        # Explain Agent
        explain_agent = Agent(
            model=Ollama(id="qwen2.5:3b"),
            tools=[],
            instructions=dedent("""
                Du bist der Erklär Agent für einen Blockchain Assistant.

                Deine Aufgaben:
                - Du liest aufmerksam, was der Ethereum-Agent oder andere Agenten zuvor geantwortet haben.
                - Du fasst die technische Antwort in sehr einfacher, alltagstauglicher Sprache zusammen.
                - Du erklärst Schritt für Schritt, was passiert (oder passieren würde).
                - Du vermeidest Fachjargon, wo immer möglich. Wenn Fachbegriffe vorkommen müssen,
                  erklärst du sie kurz in einem Satz.

                Wichtige Regeln:
                - Führe NIEMALS selbst Blockchain-Transaktionen aus.
                - Rufe KEINE Tools auf.
                - Erfinde keine zusätzlichen Aktionen - erkläre nur das, was bereits geplant oder ausgeführt wurde.
                - Wenn eine Transaktion nur simuliert wurde, stelle ganz klar heraus,
                  dass NICHT wirklich auf der Blockchain etwas ausgeführt wurde.
                - Am Ende deiner Erklärung zeigst du, falls vorhanden, den Transaktionshash in Backticks,
                  z.B.: `0xabc123...`.

                Stil:
                - Du schreibst so, dass auch Personen ohne Blockchain-Vorkenntnisse dich verstehen.
                - Du nutzt kurze Sätze und Beispiele aus dem Alltag (z.B. Kontostand wie beim E-Banking).
                - Du sprichst die Nutzerin/den Nutzer direkt mit "du" an.
            """),
            markdown=True,
            debug_mode=True,
        )


        #Agent Team    
        team = Team(
            name="Ethereum_Assistant_Team",
            members=[address_book_agent, eth_agent, explain_agent],
            model=Ollama(id="qwen3:8b"),
            instructions = dedent("""
                Ihr arbeitet gemeinsam an Nutzeranfragen.

                Rollenverteilung:
                - Der Adressbuch-Agent wandelt Namen in Ethereum-Adressen um, indem er das Tool `get_address_by_name` nutzt.
                - Der Ethereum-Agent verarbeitet ausschließlich Ethereum-Adressen (0x...) und führt darauf basierende Blockchain-Abfragen aus.
                - Der Erklär-Agent liest die Antworten des Ethereum-Agenten und übersetzt sie in einfache, laienverständliche Sprache.

                Arbeitsablauf:
                1. Wenn der Nutzer einen Namen nennt, soll der Adressbuch-Agent zuerst die Adresse liefern.
                2. Sobald eine konkrete Ethereum-Adresse vorliegt und der Nutzer eine Aktion wie Überweisung,
                   Saldo-Abfrage oder Transaktion verlangt, soll der Ethereum-Agent übernehmen und die passende
                   On-Chain-Abfrage oder Transaktion durchführen (über die MCP-Tools).
                3. Wenn der Ethereum-Agent eine technische Antwort oder einen Transaktions-Hash geliefert hat,
                   soll der Erklär-Agent diese Antwort in einfachen Worten zusammenfassen und als letzte Antwort
                   an den Nutzer ausgeben.
                4. Wenn der Nutzer nur nach einer Adresse fragt, darf KEIN weiterer Agent aktiviert werden.
                   Die Antwort des Adressbuch-Agenten ist dann die Endantwort.

                Zusätzliche Regeln:
                - Weder der Team-Leiter noch einer der Agenten dürfen externe Links oder URLs erzeugen
                  (z. B. Etherscan, Basescan, Explorer).
                - Bei Transaktionen soll der Ethereum-Agent wie bisher eine kurze, technische Beschreibung liefern
                  und den rohen Transaktionshash in Backticks ausgeben.
                - Der Erklär-Agent ergänzt danach eine leicht verständliche Erklärung für Laien.
            """),
            markdown=True,
            debug_mode=True,
        )

        await team.aprint_response(message, stream=True)


#=============================
#Example usage
#=============================
if __name__ == "__main__":
    #asyncio.run(run_agent("Was ist das Guthaben auf der Adresse 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266?"))
    #asyncio.run(run_agent("Bitte sende 100 ETH an die Adresse 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"))
    #asyncio.run(run_agent("Bitte überweise 100 VLZ an die Adresse 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"))
    #asyncio.run(run_agent("Bitte überweise 100 ETH an die Adresse von Joel"))
    #asyncio.run(run_agent("Bitte überweise 100 Voltaze an Patrick"))
    #asyncio.run(run_agent("Wie lautet die Adresse von Joel?"))
    #asyncio.run(run_agent("Welche Tools stehen dir alle zur Verfügung?"))
    asyncio.run(run_agent("Was ist der aktuelle Gas Preis und was ist ein Gas Preis überhaupt?"))