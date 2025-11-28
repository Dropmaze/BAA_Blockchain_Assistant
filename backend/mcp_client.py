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
            model=Ollama(id="llama3.2:latest"),
            tools=[mcp_tools],
            instructions=dedent("""
                Du bist der Ethereum-Agent. Deine Aufgaben:
                - Du arbeitest ausschließlich mit Ethereum-Adressen (0x...).
                - Du führst On-Chain-Abfragen, Saldenprüfungen und Analysen durch.
                - Wenn dir eine gültige Adresse übergeben wird, führst du die passende Blockchain-Abfrage aus.
                - Du interpretierst keine menschlichen Namen. Namen sind Aufgabe des Adressbuch-Agenten.
            """),
            markdown=True,
            #debug_mode=True,
        )

        #Adress Book Agent
        address_book_agent = Agent(
            model=Ollama(id="llama3.2:latest"),
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
            #debug_mode=True,
        )

        #Agent Team    
        team = Team(
            name="Ethereum_Assistant_Team",
            members=[address_book_agent, eth_agent],
            model=Ollama(id="llama3.2:latest"),
            instructions=dedent("""
                Ihr arbeitet gemeinsam an Nutzeranfragen.
                Rollenverteilung:
                - Der Adressbuch-Agent wandelt Namen in Ethereum-Adressen um, indem er das Tool `get_address_by_name` nutzt.
                - Der Ethereum-Agent verarbeitet ausschließlich Adressen und führt darauf basierende Blockchain-Abfragen aus.
                Arbeitsablauf:
                1. Wenn der Nutzer einen Namen nennt, soll der Adressbuch-Agent zuerst die Adresse liefern.
                2. Wenn der Nutzer ausdrücklich nach Blockchain-Daten fragt (z. B. Guthaben, Transaktionen,
                Gas oder Saldo), soll der Ethereum-Agent übernehmen.
                3. Wenn der Nutzer NICHT nach Blockchain-Daten fragt, sondern NUR nach der Adresse,
                darf KEIN weiterer Agent aktiviert werden. Die Antwort des Adressbuch-Agenten ist dann die Endantwort.
                4. Der Team-Leiter darf keine Tools oder Agenten ohne ausdrückliche Nutzeranforderung aktivieren.
            """),
            markdown=True,
            #debug_mode=True,
        )


        await team.aprint_response(message, stream=True)


#=============================
#Example usage
#=============================
if __name__ == "__main__":
    #asyncio.run(run_agent("Was ist das Guthaben auf der Adresse 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266?"))
    asyncio.run(run_agent("Wie lautet die Adresse von Samira?"))
    #asyncio.run(run_agent("Welche Tools stehen dir alle zur Verfügung?"))