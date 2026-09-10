# WU-DOCUMENT-TASK — UI kandidát, nikoli živá acceptance

## Implementováno
- Editor / AI nástroje / Dokumentační úkol. Stávající Kontext, Plan a Coding zachovány.
- Explicitní příprava bez modelu, přesný export se shodným id+digest před potvrzením, samostatný potvrzený start.
- Obnova uloženého běhu pro aktuální uzel, ověřený výsledek a stažení dokumentu/kontextu.
- Polling včetně stopping/verifying; chybně směrovaný snapshot se nezobrazí.
- Stop má zvláštní potvrzení, během přijatého zastavování se nepotvrzuje opakovaně. Chyba není doklad zastavení.
- Změna scope/focus/packet remountuje panel a invaliduje opožděné odpovědi.

## Skutečně provedené brány
- Build exit0.
- 11 focused Playwright testů GREEN (transport doubles, ne skutečný agent).
- Před posledními úzkými review opravami celá UI regrese: **67 passed, 1 skipped**. Ne 68 passed; nezávislá review zpráva tento počet chybně interpretovala. Čerstvý celý průchod je nutný při integraci.
- RED→GREEN pro původně chybějící UI, restore/export, stop, přesný náhled, přechodové stavy; dále reprodukovaná RED pro cizí poll, duplicitní stop, cizí export a nevysvětlené main.
- Review `document-task-ui-review.json`: obě medium a low opraveny a pokryty testy. Nebylo to Claude schválení.

## Zbývá před doručením
Backend correction/security gates; spojení kandidátů; skutečný bounded Hermes běh s dočtením uložené WorkspaceDocument (značka jen v podkladech, ne v promptu); ověření skutečného result.md a zhasnutého vlastního procesu; skutečný API/UI persistence readback; finální celé brány. Nenahradit tuto acceptance doubles.
Nenasazeno na8750, žádný model touto UI sadou spuštěn nebyl.
