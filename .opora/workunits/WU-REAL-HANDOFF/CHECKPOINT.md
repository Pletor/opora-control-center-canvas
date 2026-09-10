# WU-REAL-HANDOFF — stav po uzavření prerekvizity

## Aktivní požadavek
Dokumentace → izolovaný úkol s kontextem → skutečný agent/orchestrátor → průběh a ověřený výsledek v novém Control Center. Žádné nefunkční spouštěče.

## Dokončený funkční krok
Mapový kontext, export Markdown/JSON a tvorba sektorů/uzlů byly zpřístupněny v odděleném náhledu8750. Produkce8740 nezměněna. Runtime src/backend hashově odpovídá plně testovanému kandidátu v2-agent-context-map. Před změnou vytvořena SQLite záloha a zachován starý dist; záloha po zastavení zachytila i poslední případné editace. Readback potvrdil stejné tabulky, hashe a projekty; data se nemigrovala ani nenahrazovala.

## Ověření
- Backend:248 passed,3 skipped; dvě existující deprecation warnings.
- Source-creation UI:11 passed.
- Hlavní UI:67 passed,1 paid-live skipped.
- Nezávislé map boundary:1 passed.
- Build a Ruff:exit0; existující varování velikosti bundlů.
- Živé UI8750: rozbalená mapa, skutečný focus Frontend a vazba na Přihlášení, žádná JS chyba ani POST; screenshot preview-live-map.png.
- Nezávislé review source-scope-closure-review.json: PASS_WITH_NONBLOCKING_TEST_GAPS. Claude Sonnet timeout180s, není jeho schválení. Zbylé mezery: překryv busy A/B, okamžité zavření dialogu, HTTP re-save legacy node bez sourceRef.
- Opravené reprodukované RED: starý save po A→B→A přepisoval vrstvu; stará chyba z A se zobrazila v B. Generation guardy nyní GREEN.
- Traversal-shaped návrhové cesty již odmítal původní grafový validátor; charakterizační HTTP testy potvrzují409 a nulovou mutaci.

## Důkazy
build-final-scope.json,source-green.json,backend.json,ruff.json,ui-final-scope.json,map-boundary-final.json,preview-install.json,preview-readback.json,preview-ui-readback.json. Lokální review artefakt: C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/source-scope-closure-review.json.

## Další konkrétní hranice
Skutečný obecný handoff zatím není implementován. Starý Supervisor Bridge8710 neběží; OporaCC8720 i8738 hlásí degraded.8738 ve skutečnosti běží z wt-cc-platno, nikoli OporaCC/main; read-only discovery tohoto starého transportu proto není důkazem shody celého živého API.

README a PRODUCT-CONTRACT nového Canvasu výslovně určují samostatný backend mimo starý OporaCC. Starý Bridge proto není nutná závislost pro nové předání úkolů. Existující coding_worker.py již používá přímý Hermes AIAgent se třemi explicitně scope-bound nástroji a bez host shellu; je ale jen calculator.py oracle. Nová vertikála má využít tento bezpečnostní vzor, nikoli vydávat starý fixture za obecného agenta.
