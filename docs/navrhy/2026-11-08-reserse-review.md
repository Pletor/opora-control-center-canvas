# Kontrola revize 7480db2 a návaznosti Rešerše

Kontrola zdrojů dne 8. 11. 2026. Referenční základ pracovní větve Rešerše: `f470d3e0`.
Jde o kontrolu kódu; tento dokument nepotvrzuje přijetí linie, produkční nasazení ani stav běžící aplikace.

## Vztah ke kontrolované revizi

`7480db24bc69bda2003bb542a2cbc758ec94a6e6` přidává deník rozhovoru, oznámení eskalací srdce a předání odpovědi
člověka přes Pletora. `git merge-base --is-ancestor 7480db2 f470d3e0` vrací 1: nejde o přímého předka základu.
Obsah `backend/agi_pletor/service.py` a `backend/brain_opora/determinism/gate.py` je však mezi touto revizí
a základem shodný (`git diff --quiet 7480db2 f470d3e0 -- <oba soubory>` vrací 0).

Základ obsahuje souhrnný commit `9949d09e` („Otázky Pletora Srdci (M1)“), jehož zpráva uvádí M1c jako `dc58f216`
a následné opravy jako `28c2ef42`. Proto nelze z nepřítomnosti původního SHA v historii odvodit, že jeho chování
v základu chybí. Stejně tak přítomnost kódu není důkaz nasazení.

## Zděděné nálezy mimo úpravu Rešerše

1. **Proaktivní oznámení se může spotřebovat bez přehrání.**
   `frontend/agi-pletor/hud/logic/use-pletor-voice.ts:172` nastaví `seen.current = key` před kontrolou na řádku 173.
   Když zpráva přijde během `speaking`, efekt ji přeskočí, ale klíč už označil za viděný. Pozdější průchod ji tedy
   nevybere k přečtení. Totéž se týká zavřeného hlasového rozhraní. Řešení vyžaduje oddělit přijetí zprávy od
   dokončeného/naplánovaného přehrání a uchovat čekající oznámení. Zde nebylo měněno.

2. **Výklad celé odpovědi naráží na kratší kontextový limit.**
   `backend/agi_pletor/questions.py:16` a kontrola na řádku 61 dovolují odpověď do 8 000 znaků.
   `backend/agi_pletor/context.py:31` nastavuje `ANSWER_FULL = 2600`; řádek 81 tím odpověď zkrátí před předáním
   modelu. Samotná revize `7480db2` měla v této cestě limit 450 znaků. Odpověď s variantou na konci nad limit
   proto není v základním kontextu celá. Rešerše nově umožňuje dohledat uloženou odpověď podle ID otázky a dočíst
   ji přes detail; starší nezrcadlené odpovědi tím nejsou automaticky doplněny. Původní kontextové limity zůstávají.

3. **Text označený jako odpověď člověka pochází z modelové akce.**
   `backend/agi_pletor/service.py:74` přijímá do `_run` jen projekt, prostor a modelovou akci. Na řádku 84 předává
   `action["text"]` do `gate.answer` s aktérem `human`, bez porovnání s původní zprávou člověka. Persona sice požaduje
   doslovná slova člověka, ale backend nemá v tomto místě jeho zprávu, aby podmínku ověřil. Případná modelová
   parafráze či domyšlený souhlas se tedy mohou uložit jako lidská odpověď. Prověřit vazbu na skutečný vstup před
   zápisem; samotné přidání další instrukce modelu tuto vlastnost nezajišťuje. Zde nebylo měněno.

Čísla řádků odpovídají pracovní verzi po integraci Rešerše; uvedené symboly určují místa i při dalších posunech.

## Opravy provedené při kontrole nové Rešerše

- Pokračovací čtení dostává instrukci předat `snapshot` spolu s `nextOffset`; nelze tiše spojit části různých revizí.
- Smyčka dovoluje 12 čtení. Po dosažení limitu přizná nedočtené podklady a neprovádí zápisy. Neslibuje obnovení
  čtení v dalším tahu, protože kurzor a narůstající kontext nejsou trvale ukládány.
- Ollama při čtení Rešerše používá kontext 32 768 a rezervu 1 024 tokenů na výstup. Konzervativní kontrola velikosti
  všech zpráv v UTF-8 včetně persony a historie odmítne nadlimitní vstup před voláním modelu. Původní okno 8 192
  u běžných tahů zůstává. Větší podklady stále vyžadují užší téma nebo jiný model; nejde o neomezené čtení.
- Persona nejprve hledá v Rešerši, potom žádá nové zjišťování srdce. Netvrdí, že zkrácený přehled obsahuje celou
  odpověď, a rozlišuje souhlas s výkladem od schválení varianty.

Ověření při této kontrole: 56 testů v `test_brains.py`, `test_research_turn.py`, `test_research_context.py`
a `test_service.py` prošlo. Testy poskytují simulovaný transport modelu; nejsou potvrzením kvality reálného
modelového výkladu nebo produkčního provozu.
