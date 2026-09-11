# Live Run a skutečné výsledky

1. Zachovej project/workspace; otevři **Live Run**.
2. Použij stavový filtr, hledání `Hledat v bězích a ticketech` či `Jen vybraný uzel`.
3. Vyber session podle ID a typu. Návrhový běh a dokumentační handoff nejsou
   zaměnitelné ani když mají podobný název.
4. Karty detailu poskytují události, výsledek/důkazy, náklady, paměť/přesný kontext,
   ovládání, tickety a kontextovou osu. Názvy ověř v aktuálním UI.
5. U výsledku rozliš: text návrhu, dokumentační výstup, backendové ověření,
   skutečně uložený soubor. Stažení výstupu není nasazení.
6. **Načíst přesné předané zadání** použij u konkrétního handoffu; porovnej scope/digest.

## Co nelze tvrdit

- Seznam má limit nejvýše 20 návrhových a 20 handoff běhů v tomto API;
  prázdný filtrovaný seznam není důkaz prázdného archivu.
- Nedostupný jeden zdroj neznamená selhání ostatních. Zachované položky mohou být staré.
- Chybějící tokeny, USD či využití kontextu nejsou nula. Žádná vymyšlená procenta.
- V doloženém UI jsou **Upravit pokyn**, **Pokračovat**, **Compact nyní** a boční
  `/btw` neaktivní kvůli chybějícímu transportu. Neobcházej disabled tlačítka
  a nepiš, že byl pokyn odeslán.
- **Dohled běhů** je pokročilý přehled; návrat do hlavního Live Run není restart session.

## Zastavení

Jen na konkrétní uživatelův požadavek vyber správný aktivní run, **Zastavit tento běh**
a **Potvrdit zastavení**. Stav `stopping` znamená vyžádáno, ne ukončeno.
Načti opět stejné ID a ověř terminální stav. Nezastavuj celý server ani všechny agenty.

## Tickety

Ticket váže problém na skutečný nodeId/sessionId. Priority low/normal/high;
stavy open/doing/done. Nevyplňuj náhodné session ID. Celoprojektový ticket
nemusí mít konkrétní session. Autorství `human` nebo `agent` musí odpovídat
skutečnému původu. Stav done není automaticky ověřená oprava.
