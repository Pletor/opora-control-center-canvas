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
- `Conversation`, `TurnBlock`: konverzace po tazích (hlavička „Tah N“ s tím, co je známé), „pracuje… 0:12“ na konci, u dlouhého přemýšlení nebo vstupu nástroje s řádkem „Přemýšlí… 3 kB“ / „Píše Write… 24 kB“ (událost `progress`). `MessageBlock`, `Markdown`, `ToolSteps`: zpráva, bezpečný Markdown, sbalené kroky nástrojů.
- `DecisionCards`: odpověď s otázkami ve tvaru grillingu jako mřížka karet (2 sloupce od šířky sloupce 640 px, jinak 1) s celým doporučením.
- `Outline` (celá plocha): kontext ze zprávy, průběh (tahy, aktivní zvýrazněný), otázky k rozhodnutí z poslední odpovědi, kroky.
- `ApprovalCard`: žádost asistenta o zápis na plátno (§5.1) v tahu konverzace: kam zápis jde (cíl, karta, projekt, workspace, cesta), shrnutí payloadu, důvod, poznámka a Povolit / Zamítnout. Uzavřená žádost je tichý řádek s výsledkem; automaticky zamítnutý nástroj jen jeden tlumený řádek.
- `Composer`: pole od tří řádků rostoucí s textem, Rozbalit/Sbalit pro dlouhé zadání, dlouhé vložení (od 1 500 znaků nebo 20 řádků) jako dlaždice `PastedBlocks` nad polem s tužkou zpět do pole (`logic/pasted-blocks.ts`; v konverzaci sbalené), počítadlo od 2 000 znaků (limit 60 000, `logic/composer-size.ts`), Stop, nápověda lomítkových příkazů; na celé ploše popisek „Odpověď do úkolu „…““. Pod polem `ScopeSwitch`: rozsah práce „Výběr / Celý obraz“ (§6.1) a u Výběru počet vybraných uzlů.

Logika (`logic/`), čisté funkce s testem vedle:

- `assistant-events.ts`: reducer událostí SSE a přepisu (značka konce tahu s délkou, čas odeslání u zpráv odsud, `approval` / `approval_resolved`).
- `progress-label.ts`: text řádku z poslední události `progress` (reducer ji drží v `conv.progress`, mizí s prvním viditelným výstupem).
- `approval.ts`: žádost o zápis z události (cíl, shrnutí, stav pending → sending → allowed/denied), popisky cíle, poznámka, položky konverzace a čekající žádosti; úkol s otevřenou žádostí je „Čeká na vás“.
- `markdown.ts`: text → bloky a inline uzly, bez HTML.
- `task-overview.ts`: stav slovem, relativní čas, náhled, „nové“, sousední úkol, platný název, skupiny a hledání.
- `turns.ts`: tahy z konverzace, hlavička tahu, popisek pro osnovu, kotvy, souhrn kroků.
- `decisions.ts`: otázky grillingu (úvod, `{id, topic, question, recommendation}`, závěr), jinak `null`.
- `tool-steps.ts`: sbalení po sobě jdoucích nástrojů. `slash-commands.ts`: nápověda `/grill-me`, `/wayfinder`.
- `assistant-prefs.ts`: preference aplikace (model, velikost, rozsah práce, výchozí `board`) a přechody velikostí.
- `work-scope.ts`: jména rozsahů a „Výběr: 2 uzly“ / „nic nevybráno“.
- `canvas-write.ts`: hlídač proudu událostí, který pozná doběhlý povolený zápis (`approval` Bash → `approval_resolved allow` → `tool_result ok`, párování podle id nástroje); přehrané staré události nespustí nic (§6.2).

React vazby (bez testu, jen skládají logiku a síť): `use-assistant-sessions.ts` (status, seznam session s pollingem 4 s, založit / přejmenovat / zavřít), `use-conversation.ts` (přepis, pak EventSource od `lastSeq`, u úkolu čekajícího na schválení od začátku bufferu; odeslání, Stop, rozhodnutí o žádosti), `use-task-memory.ts` (koncepty, „viděno“, náhledy), `use-task-outline.ts` (tahy, otázky, odeslaný kontext, posun), `use-active-turn.ts` (IntersectionObserver: který tah se čte), `use-panel-keys.ts` (zkratky). Volání API je v `assistant-api.ts`.

Kontext plátna (projekt, workspace, vrstva, výběr, prostředí) dodá App; panel k němu přidá `scope` z preferencí, ke každé zprávě ho přiloží a osnova ukazuje ten naposledy odeslaný (nebo ten, který se pošle).

Po doběhlém povoleném zápisu panel zavolá `onCanvasWritten`; App znovu načte graf (`/api/view`, bez vyprázdnění plátna) i stav Desktop v3 (`useDesktopState().reload`). Probíhající uložení grafu nebo stavu reload odloží na svůj konec; souběh pak řeší stávající digest a revize.
