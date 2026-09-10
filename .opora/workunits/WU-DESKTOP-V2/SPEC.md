# WU-DESKTOP-V2 — implementace schváleného hosted designu

## Autorita a cíl
Uživatel 2026-09-10 schválil hosted04 OPORA Desktop v2 a požaduje skutečnou implementaci do Canvasu. Po připojení local/new/GitHub následují Projekt | Editor | Live Run. Každé prostředí mění plochu a nástroje, sdílí projekt, worktree, vrstvu, výběr a kontext. Povrch Command/Inspect, Live Run sekundárně Monitor; existující tmavé OPORA tokeny, žádné nové CDN. Hosted soukromý projekt66ce0bf9-4cb8-4f05-9c00-44f392093bf7,04 etag1789038124444409,05 etag1789038785165472. Žádná ilustrační data z prototypu do produkce.

## Baseline a ownership
Jediný writer Astra, worktree .worktrees/desktop-v2, feat/desktop-workspaces-v2 z424f788. Main31452ec je předek baseline; runtime8740 mádbc19ff zproject-wireframe se společnou.data/production. Staré worktrees a jejich untracked soubory se nemění. Repozitář nemá remote: GitHub PR/CI nelze vykázat. Claude do uživatelem odhadnutého resetu15:17CEST nevolat; po resetu Sonnet a Opus pro oddělené role. Žádné přepsání runtime bez zálohy a identity check.

## Zachování
Board+sektory+vazby+zanoření, TextWorkspace+BlockOutline, NodeTextEditor, NodeJournal, NodeLinksPanel, NodeSpecEditor, DrawingWorkspace+DrawingTools, WireframeTools/Inspector/Preview, ProjectMap/Archify, NodeActivity, AgentsWorkspace, ProjectHome, PlanPanel a CodingPanel zůstávají dostupné. Draft scope project/workspace/node se nemění. Historické URL mode=structure/text/drawing/map/agents zůstanou funkční. Žádný agent se nespustí otevřením stránky ani přepnutím prostředí.

## Vertikální řezy
1. Projekt: read-only lazy skutečný strom povoleného rootu, žádná rekurze při načtení; stránkování bez zamlčených položek; .git vynecháno; symlink/junction/traversal odmítnut. Dokumentace nad cestou ukládána do app DB, nikoli zdrojových souborů; revize/CAS, cíl/podstata/architektura/technologie, vazba na existující uzly a společný shelf.
2. Shell/Editor: EnvironmentSwitch, scoped selection/shelf, toolbary pro současné editory, draft continuity a error/loading/read-only stavy.
3. Live: skutečné současné agentní zdroje, detail/karty/filtry, pouze dostupné schválené akce a source labels; chybějící /btw transport explicitně nepodporovaný, žádná falešná odpověď.
4. Integrace: RED→GREEN každého traceru, všechny regresní testy/build/lint, head-bound nezávislé review po resetu, malé commity/checkpointy, záloha/deploy/readback.

## Bezpečnost a důkazy
Host/Origin/JSON middleware zachován. Relativní cesty validovat před FS a containment po resolve. Nespouštět projektový kód pro čtení stromu. Strom neposílá obsahy souborů. Citlivé cesty se nebalí do agentního kontextu. Síť/dispatch není součástí GET. Evidence je zdrojová, nullable cost není nula. API testy nad dočasnými fixture bez reálných modelů. Browser pouze na výslovný uživatelův pokyn; vlastní izolované testy nesmějí navštěvovat cloudové účty ani produkční data.
