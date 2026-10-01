Panel Asistent: úkoly s Claude Code přímo v OPOŘE (kontrakt `docs/asistent.md`, UI v §9).

Tři velikosti: `minimized` (lišta vpravo dole nad minimapou), `side` (panel vpravo, cca 480 px) a `full` (celá plocha pod horní lištou). Velikost a výchozí model se ukládají jednou pro aplikaci (`localStorage` `opora:assistant:v1`), nikdy per projekt.

Celá plocha má tři sloupce: úkoly (288 px) | konverzace (sloupec až 920 px, odstavce cca 80 znaků) | osnova (296 px, jen od šířky okna 1280 px).

Dílky (`components/`):

- `AssistantButton`: tlačítko v pravém rohu horní lišty, tečka když nějaký úkol pracuje.
- `AssistantPanel`: rodič. Drží velikost, spojení, koncepty zpráv a zkratky (`Esc` zmenší, `Alt+↑/↓` přepíná úkoly, na celé ploše v pořadí skupin) a skládá ostatní dílky. Zůstává připojený i zavřený, aby tečka na tlačítku věděla, kdy práce doběhla.
- `PanelHead`, `SizeSwitch`: hlavička (na celé ploše i název a model úkolu) a tři ikony velikosti.
- `MinimizedBar`: minimalizovaná lišta s aktivním úkolem, stavem a počtem.
- `TaskColumn` (celá plocha): „+ Nový úkol“, hledání v názvech a skupiny Pracuje / Čeká na vás / Ostatní. `TaskList` (panel vpravo): rozbalovací pruh. Oba skládají `TaskItem` (přejmenování v řádku, zavření s potvrzením v řádku) a `NewTask` (tlačítko s modelem).
- `TasksEmpty`: prázdný stav s příklady otázek. `PanelNotice`: chybí projekt, `claude` nedostupný, selhání.
- `Conversation`, `TurnBlock`: konverzace po tazích (hlavička „Tah N“ s tím, co je známé), „pracuje… 0:12“ na konci. `MessageBlock`, `Markdown`, `ToolSteps`: zpráva, bezpečný Markdown, sbalené kroky nástrojů.
- `DecisionCards`: odpověď s otázkami ve tvaru grillingu jako mřížka karet (2 sloupce od šířky sloupce 640 px, jinak 1) s celým doporučením.
- `Outline` (celá plocha): kontext ze zprávy, průběh (tahy, aktivní zvýrazněný), otázky k rozhodnutí z poslední odpovědi, kroky.
- `Composer`: rostoucí pole, Stop, nápověda lomítkových příkazů; na celé ploše popisek „Odpověď do úkolu „…““.

Logika (`logic/`), čisté funkce s testem vedle:

- `assistant-events.ts`: reducer událostí SSE a přepisu (značka konce tahu s délkou, čas odeslání u zpráv odsud).
- `markdown.ts`: text → bloky a inline uzly, bez HTML.
- `task-overview.ts`: stav slovem, relativní čas, náhled, „nové“, sousední úkol, platný název, skupiny a hledání.
- `turns.ts`: tahy z konverzace, hlavička tahu, popisek pro osnovu, kotvy, souhrn kroků.
- `decisions.ts`: otázky grillingu (úvod, `{id, topic, question, recommendation}`, závěr), jinak `null`.
- `tool-steps.ts`: sbalení po sobě jdoucích nástrojů. `slash-commands.ts`: nápověda `/grill-me`, `/wayfinder`.
- `assistant-prefs.ts`: preference aplikace (model, velikost) a přechody velikostí.

React vazby (bez testu, jen skládají logiku a síť): `use-assistant-sessions.ts` (status, seznam session s pollingem 4 s, založit / přejmenovat / zavřít), `use-conversation.ts` (přepis, pak EventSource od `lastSeq`, odeslání, Stop), `use-task-memory.ts` (koncepty, „viděno“, náhledy), `use-task-outline.ts` (tahy, otázky, odeslaný kontext, posun), `use-active-turn.ts` (IntersectionObserver: který tah se čte), `use-panel-keys.ts` (zkratky). Volání API je v `assistant-api.ts`.

Kontext plátna (projekt, workspace, vrstva, výběr, prostředí) dodá App; panel ho ke každé zprávě přiloží a osnova ukazuje ten naposledy odeslaný (nebo ten, který se pošle).
