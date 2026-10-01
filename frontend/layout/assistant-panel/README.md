Panel Asistent: úkoly s Claude Code přímo v OPOŘE (kontrakt `docs/asistent.md`, UI v §9).

Tři velikosti: `minimized` (lišta vpravo dole nad minimapou), `side` (panel vpravo, cca 480 px) a `full` (celá plocha pod horní lištou). Velikost a výchozí model se ukládají jednou pro aplikaci (`localStorage` `opora:assistant:v1`), nikdy per projekt.

Dílky (`components/`):

- `AssistantButton`: tlačítko v pravém rohu horní lišty, tečka když nějaký úkol pracuje.
- `AssistantPanel`: rodič. Drží velikost, spojení, koncepty zpráv a zkratky (`Esc` zmenší, `Alt+↑/↓` přepíná úkoly) a skládá ostatní dílky. Zůstává připojený i zavřený, aby tečka na tlačítku věděla, kdy práce doběhla.
- `SizeSwitch`: tři ikony velikosti v hlavičce.
- `MinimizedBar`: minimalizovaná lišta s aktivním úkolem, stavem a počtem.
- `TaskList`, `TaskItem`: přehled úkolů (sloupec na celé ploše, rozbalovací pruh v panelu vpravo), přejmenování v řádku, zavření s potvrzením v řádku, „+ Nový úkol“ s modelem.
- `TasksEmpty`: prázdný stav s příklady otázek. `PanelNotice`: chybí projekt, `claude` nedostupný, selhání.
- `Conversation`, `MessageBlock`, `Markdown`, `ToolSteps`: konverzace jako dokument, bezpečný Markdown, sbalené kroky nástrojů, „pracuje… 0:12“.
- `Composer`: rostoucí pole, Stop, nápověda lomítkových příkazů.

Logika (`logic/`), čisté funkce s testem vedle:

- `assistant-events.ts`: reducer událostí SSE a přepisu.
- `markdown.ts`: text → bloky a inline uzly, bez HTML.
- `task-overview.ts`: stav slovem, relativní čas, náhled, „nové“, sousední úkol, platný název.
- `tool-steps.ts`: sbalení po sobě jdoucích nástrojů. `slash-commands.ts`: nápověda `/grill-me`, `/wayfinder`.
- `assistant-prefs.ts`: preference aplikace (model, velikost) a přechody velikostí.

React vazby (bez testu, jen skládají logiku a síť): `use-assistant-sessions.ts` (status, seznam session s pollingem 4 s, založit / přejmenovat / zavřít), `use-conversation.ts` (přepis, pak EventSource od `lastSeq`, odeslání, Stop), `use-task-memory.ts` (koncepty, „viděno“, náhledy), `use-panel-keys.ts` (zkratky). Volání API je v `assistant-api.ts`.

Kontext plátna (projekt, workspace, vrstva, výběr, prostředí) dodá App; panel ho ke každé zprávě přiloží.
