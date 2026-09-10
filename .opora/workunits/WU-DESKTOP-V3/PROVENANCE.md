# WU-DESKTOP-V3 — provenance a ověřovací brány

## Zdroje
- Přímý požadovaný zdroj: https://claude.ai/design/p/66ce0bf9-4cb8-4f05-9c00-44f392093bf7?file=06+OPORA+Desktop+v3.dc.html
- Stažen původní soubor přes All project files → přesný soubor → Download, 684 řádků /118428 bytů; SHA256 `541cb172c681e2e9745ad4da2259a8db10bbab144c46271fb61b83c186428bce`.
- Editor zkontrolován i v reálně vykresleném iframe původního projektu. Obsah označen NÁVRH V3, ILUSTRAČNÍ DATA, ŽÁDNÉ REÁLNÉ SESSIONS. Dummy běhy/commity/falešné ovládání nejsou výrobní data.
- Stažen podpůrný `support.js`. Pokus vykreslit samotný .dc.html offline selhal (DC runtime potřebuje hostitelské React/render prostředí). Nevydává se za úspěšné vizuální ověření.

## Zachování
- Původní rozpracovaný checkout na P: se neupravuje během agentních lanes.
- Baseline `bf8a1767ae098433dd6f5ee61a08602d8713b193` obsahuje snapshot aktuálního kódu včetně předchozí dokumentační/clean-editor práce. Staging původního checkoutu nezměněn.
- Izolovaný integrátor `C:/Users/Admin/opora-v3`, branch integration/desktop-v3.
- Výlučné lanes fable / sonnet / opus, společný CONTRACT.md. Každý <=75turnů, <=1500s, <=20USD CLI limit, Windows Job Object pro potomky.
- Ověřená modelová identita v stream events: claude-fable-5-1; claude-sonnet-5; claude-opus-5.
- Žádný agent nemá měnit běžící server ani produkční SQLite data. Generování kresby nebo preview automaticky nevolá LLM.

## Brány — před integrací
- Baseline `uv run pytest tests -q`: exit0,265 passed,4 skipped,2 dependency deprecation warnings,123.47s.
- `npm ci && uv sync --frozen`: exit0; existující peer/deprecation warnings, npm audit0 vulnerabilities. Žádná změna lockfile.
- Koordinátorova oracle `tests/test_v3_acceptance.py`: první pokus narazil na chybu fixture (expectedRevision místo existujícího expected_revision). Fixture opravena. Skutečný RED: POST /api/desktop-v3/packet/preview404; uložená kresba rodiče před tím úspěšně vrácena200. Zatím NE GREEN.

## Akceptace (před nasazením musí mít důkaz)
1. Původní source explorer + mapa + dokumentace použitelné.
2. Canvas + kreslení + text + tvorba sektorů/uzlů s/bez sourceRef zachované.
3. Projekt/Editor/Live Run sdílejí vybraný projekt/workspace/relevantní kontext.
4. Canvas-first compact desktop,1280/1440/1920; inspektor/podklady skrytelné.
5. Světlý i tmavý OPORA brand, persistence; kresba i panely čitelné.
6. Paměť projektu: nastavení/pravidla/rozhodnutí se uloží a po reloadu načtou, CAS a scope guard.
7. Fáze/kritéria/kroky uzlu; plánovací fáze se nevydává za provedené testy.
8. Scope balíčku uzel/cesta/projekt/session dle skutečně podporovaného obsahu.
9. Manifest zahrnutí/vynechání, předkové/kresby/revize, dokumentace, reference, neuložená poznámka.
10. Snapshot je neměnný, preview změny se odmítají409, předání použije stejný obsah.
11. Příprava nic nespouští; dokumentační start výslovný, scope/timeout/stop guardy nezhoršeny.
12. Návrhový výstup je dohledatelný a není zaměněn za dokončenou implementaci.
13. Tickety persistují; kontext/osa jen ze skutečných zdrojů, neznámé výslovně.
14. Původní omezené Plan/Coding a TaskHandoff dostupné; žádný fake obecný coding.
15. Nezávislé review, backend/UI regrese, tsc/build/lint/diff, skutečná integrační vizuální kontrola.
16. Před výměnou vlastního8768 záloha dat/dist, shoda runtime root/PID/data, absence aktivních běhů; po výměně readback identity a nezměněných původních tabulek. Port8740 ani cizí procesy nedotýkat.

Tyto body jsou požadavky, nikoli prohlášení hotovo; konečné důkazy budou v CHECKPOINT.md.
