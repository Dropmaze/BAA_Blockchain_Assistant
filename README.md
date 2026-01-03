# Blockchain Assistant
Natürlichsprachliche Interaktion mit Smart Contracts

Dieser Prototyp entstand im Rahmen einer Bachelorarbeit an der Hochschule Luzern (HSLU) im Studiengang Wirtschaftsinformatik.

Ziel der Arbeit ist es, die Interaktion mit Smart Contracts und Blockchain-Technologien für Laien zugänglicher zu machen.
Dazu wurde ein Blockchain Assistant entwickelt, der natürliche Sprache verwendet, um ausgewählte Smart-Contract-Interaktionen verständlich zu erklären und auszuführen.

Hinweis:
Der Fokus liegt auf einem Proof of Concept und nicht auf einer produktiven Anwendung.

---

## Zielsetzung

- Vereinfachung der Blockchain-Interaktion für Nicht-Expertinnen und Nicht-Experten
- Übersetzung natürlicher Sprache in Smart-Contract-Aktionen
- Verständliche Erklärungen zu Blockchain-Vorgängen
- Sicherstellung der Nutzerkontrolle durch Human-in-the-Loop (HITL)

---

## Funktionsumfang

- Natürliche Sprachinteraktion mit Ethereum
- ETH-Transaktionen (lokales Testnetz)
- ERC20-Token-Transfers (lokales Testnetz)
- DAO-Abstimmungen über Smart Contracts
- Human-in-the-Loop (HITL) zur expliziten Bestätigung von Transaktionen
- RAG-basierte Knowledge Base für laienverständliche Erklärungen
- Web-Interface mit Streamlit
- Modularer Agenten-Ansatz (Agno + MCP)

---

## Architektur (vereinfacht)

- Frontend: Streamlit Web Interface
- Backend: Agenten-Team (Agno) + MCP-Client
- MCP-Server: Blockchain-Zugriffe (ETH, ERC20, DAO)
- Blockchain: Lokales Ethereum-Testnetz (Hardhat)
- Knowledge Base: RAG-basierte Wissensbasis

---

## Voraussetzungen (Windows)

Folgende Software muss lokal installiert sein:

- Python >= 3.10
- Node.js >= 18
- npm
- Git
- Ollama (https://ollama.com/download)
- Hardhat

---


## Installation und Start

### 1. Repository klonen

```powershell
git clone https://github.com/Dropmaze/BAA_Blockchain_Assistant.git
cd BAA_Blockchain_Assistant
```

---

### 2. Virtuelle Umgebung erstellen

```powershell
cd backend
python -m venv venv
```

Aktivieren:

```powershell
venv\Scripts\activate
```

---

### 3. Python-Abhängigkeiten installieren

```powershell
pip install -r requirements.txt
```

---

### 4. Hardhat installieren (falls noch nicht vorhanden)

```powershell
cd blockchain
npm install --save-dev hardhat
```

### 5. Lokales Blockchain-Netzwerk starten

> Hinweis: `npx hardhat node` muss dauerhaft laufen (es simuliert das lokale Testnet). Bitte dafür ein eigenes Terminal-Fenster verwenden.

```powershell
npx hardhat node
```

---

### 6. Smart Contracts deployen

In einem neuen PowerShell-Fenster:

```powershell
cd blockchain
npx hardhat run scripts/deploy_voltaze_token.js --network localhost
npx hardhat run scripts/deploy_dao_ballot.js --network localhost
```

---

### 7. Environment konfigurieren

```powershell
cd backend
copy .env.example .env
```

Danach die Datei .env manuell anpassen.
- Private Key: Private Key eines lokalen Test-Accounts aus dem Hardhat-Node ohne "0x"
- RPC URL: Wird beim Start des Hardhat-Nodes in der Konsole angezeigt (z.B. http://127.0.0.1:8545)
- Contract-Adressen: Werden beim Deployment der Smart Contracts in der Konsole ausgegeben


---

## 8. LLM-Modelle (Ollama)

Der Prototyp verwendet lokal ausgeführte Large Language Models von Ollama.

> Hinweis: Ollama Launcher (https://ollama.com/download) muss lokal installiert **und gestartet** sein bevor die Modelle via Powershell heruntergeladen werden können.
> Nach der Installation läuft Ollama im Hintergrund als lokaler Dienst.

Bitte stelle sicher, dass die folgenden Modelle lokal installiert sind:

```powershell
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
ollama pull gpt-oss:20b
```

Verwendung im Projekt:

- qwen2.5:3b
(Ethereum-, Price-, Address Book Agent)

- qwen2.5:7b
(Knowledge Agent)

- gpt-oss:20b
  Team-Leader-Agent zur Koordination und Entscheidungslogik

---

## Optional: Team-Leader Modell via Cloud (Ollama Cloud)

Standardmässig läuft der Team-Leader Agent lokal über das Ollama-Modell `gpt-oss:20b`.
Alternativ kann der Team-Leader über Ollama Cloud betrieben werden wenn die eigene Hardware zu wenig Leistung aufweist.

Voraussetzungen:
- Kostenlosen Account auf ollama.com erstellen und einen API-Key generieren. Diesen dann mit dem folgenden Befehl erfassen:

```powershell
$Env:OLLAMA_API_KEY="DEIN_API_KEY"
```
---

## 9. Anwendung starten

> Hinweis: Der MCP-Server wird automatisch vom Backend im `stdio`-Modus gestartet.  
> Ein separates Starten von `mcp_server.py` ist nicht erforderlich.

Stelle sicher, dass die virtuelle Python-Umgebung aktiv ist:

```powershell
cd backend
venv\Scripts\activate
streamlit run app.py
```