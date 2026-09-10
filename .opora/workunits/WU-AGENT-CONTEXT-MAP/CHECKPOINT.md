# WU-AGENT-CONTEXT-MAP — zpřístupněno v náhledu8750

## Aktuální doručení
Mapa/export a opravená tvorba sektorů/uzlů jsou nyní v náhledu8750. Záloha, runtime/frontend hash, stejné projekty a všechny datové tabulky byly ověřeny; živé UI prošlo bez JS chyb a bez POST. Produkce8740 nezměněna. Aktuální testy248 backend +67 hlavní UI +11 source UI +1 boundary; build/Ruff exit0. Source scope review uzavřeno nezávislým statickým reviewerem, Claude timeout není schválení. Podrobnosti: ../WU-REAL-HANDOFF/CHECKPOINT.md a preview-*.json.

## Historický checkpoint kandidáta před nasazením
Následující záznam popisuje předchozí stav; jeho části „není nasazeno“ už nejsou aktuálním stavem náhledu.


## Aktuální zadání a zdroj
Uživatel dodal https://claude-brain.preview.emergentagent.com/?utm_source=share a požádal o přenos užitečných prvků pro pochopení LLM, společný obraz pro člověka a agenty, sektory/uzly/komponenty a procesní kontrolu. Referenci jsem skutečně prošel v izolovaném Chrome přes cua-driver. Pozorování a vědomá omezení jsou v SPEC.md.

## Hotový dílčí krok
- Skutečný komponent `src/AgentContextMap.tsx`, vložený v `EditorWorkbench.tsx`, vlastní CSS v existujícím brandu.
- Diagram vybraného kontextu a předků, pojmenované příchozí/odchozí hrany, uložená vazba na zdroj. Grafové vazby nejsou deklarovány jako pozorované runtime závislosti.
- Uložený cíl, mimo-rozsah a akceptace ze skutečného kontextového paketu; vynechané a zkrácené podklady.
- Samostatný lokální snímek designContext vedle nezměněného canvasPacket; přehled pro člověka i agenta v Markdownu a JSONu. Žádné automatické čtení shelf souborů nebo spuštění modelu.
- Známé vzory tajných tokenů redigovány v diagramových popiscích; raw CanvasNode se do exportu nepřenáší přes spread. Test reprodukoval návrat redigovaného tokenu přes purpose a následně prošel.
- Ověřené opravy: opožděný paket po změně scope se ignoruje a neblokuje tlačítko; při změně focus/scope se vyčistí sousedé; mimo rozsah 1000–500000 nebo necelé číslo se paket nesestaví.
- Zachovány LLM návrh, Coding, původní graf/volné plátno, text, drawing, deníky a workspaces. Starou tvorbu volného uzlu uvnitř volného builtin sektoru zachytil původní RED canvas.spec.ts; úzká výjimka opravena a plná regrese prošla.

## Skutečně provedené ověření
Izolovaná lane `.worktrees/v2-agent-context-map`. Finální src/ a backend/ se hashově shodují s `.worktrees/desktop-v2`; záznam VERIFIED-CANDIDATE.json.
- Build a TypeScript: exit 0 (neblokující existující varování o velkých bundlích).
- Backend: 244 passed / 3 skipped; ruff exit 0.
- Hlavní UI: 67 passed / 1 paid-live skipped.
- Source-creation UI: 9 passed.
- Nezávislé boundary orákulum (redakce + export + opožděný paket + sousedé + limit): 1 passed.
- Celkem 77 různých UI testů passed; původní placený live test nebyl spuštěn.
- `context-map-fixture.png` je skutečný screenshot z testu, vizuálně prohlédnutý, se SYNTHETICKÝMI fixture daty, nikoli živým běžícím agentem.

## Nezávislé review a hranice
Soubor `C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/agent-context-map-review.json` obsahuje nezávislé statické review. Claude Code timeout po 180 s bez výstupu; nelze tvrdit, že Claude review prošlo. Statický reviewer našel zůstávající skryté sousedy (medium) a nehlídaný minimum limitu (low); obě připomínky byly potom reprodukovány RED a opraveny GREEN, jak dokládají testy. JSON review nese hash PŘED těmito opravami; finální hash je VERIFIED-CANDIDATE.json, nikoli nové schválení Claudem.

## Není nasazeno
Náhled 8750 ani produkce 8740 nebyly restartovány/přepsány. Frontend dist nového kandidáta zůstává v izolované lane. Nemazala se ani nemigrovala uživatelská data. Git merge/push/release nebyl proveden.

Širší release v2 má samostatně otevřené review starší source-creation větve (viz agent-context-source-review.json; posoudit i existující backend.graph.relative_path guard před přijetím tvrzení o traversal), a dokončení Live Run controls. Tento dílčí kontextový přehled není automatický handoff/spouštěč agentů, vizualizace tokenů ani hotová celá procesní orchestrace.

## Pro další bezpečnou integraci
Preview-inspection/backup helper: C:/Users/Admin/AppData/Local/hermes/handoffs/canvas-orchestration/inspect_agent_context_preview.py (inspect ověřeno; backup zatím nespouštěn). Skutečný současný preview identity je uložen ve VERIFIED-CANDIDATE.json. Nejprve uzavřít širší review, potom čerstvá záloha dat, přesná runtime identita, kontrolovaný restart a browser/API readback. Neoznačovat tuto budoucí práci za již provedenou.
