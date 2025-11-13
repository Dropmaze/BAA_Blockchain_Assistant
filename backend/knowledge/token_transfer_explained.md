# Erklärung des ERC-20 Token Transfers

## Überblick
Die Funktion `transfer(address to, uint256 amount)` ist die Standardmethode, um Token zu übertragen.

## Ablauf eines Transfers
1. Der Nutzer erstellt eine Transaktion, die die Funktion `transfer()` im Smart Contract aufruft.  
2. Die Transaktion enthält:
   - Empfängeradresse
   - Anzahl Token in kleinstem Format (z. B. 1 Token = 10^18 wei)
   - Gas Limit und Gas Price
3. Die Ethereum Virtual Machine prüft:
   - Hat der Sender genug Token?
   - Ist der Contract korrekt aufgerufen?
4. Ist alles gültig, wird der Kontostand aktualisiert:
   - Sender: Token − Betrag  
   - Empfänger: Token + Betrag
5. Die Transaktion wird als neuer Block in der Blockchain gespeichert.

## Wichtige Hinweise
- Ein Token-Transfer kostet immer Gas (in ETH, nicht in Token!).  
- Die Höhe des Gaspreises hängt von der Netzwerkauslastung ab.  
- Token selbst liegen nicht in der Wallet, sondern in der internen Datenstruktur des Smart Contracts.
