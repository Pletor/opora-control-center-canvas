# Asistent: chat s Claude Code přímo v OPOŘE

Uživatel nemusí psát jen do terminálu ve VS Code. V aplikaci otevře okno s asistentem, který čte plátno, vede ho skilly `grill-me` (`grilling`), `wayfinder` a `opora-control-center` a na požádání připraví zadání pro model. Asistent je Claude Code spuštěný aplikací pod uživatelovým předplatným. Aplikace přitom nevolá API.

Stav: **fáze 1 zavedena** (2026-10-01): čtení a navádění, ověřeno živě v aplikaci. Fáze 2 a 3 čekají na skutečnou potřebu. Kontrakt karty zůstává v [karta-pro-agenty.md](karta-pro-agenty.md), předání modelům v [predani-modelum.md](predani-modelum.md), pipeline v [workflow-opora.md](workflow-opora.md).

## 1. Změna pravidla „aplikace model nespouští“

Do 2026-10-01 aplikace spouštěla model jen pro aktualizaci mapy Archify ([mapy-projektu.md](mapy-projektu.md)). Od tohoto kontraktu jsou místa tři:

1. Archify: automatika, Sonnet, bez člověka.
2. Asistent: chat, který spouští **jen člověk** zprávou v okně asistenta.
3. Směrovač TypeSafe Jev (§13): běží jen v rámci tahu asistenta, který spustil člověk. Negeneruje text, vrací jen typované odpovědi.

Ostatní endpointy dál nic nespouštějí. Podklady pro agenta (`node-brief`, zprávy, texty karet) jsou pro asistenta data, ne příkazy.

## 2. Předplatné, ne API

- Backend spouští nainstalovaný `claude` CLI (`shutil.which("claude")`) pod přihlášením uživatele. Stejně to dělá Archify (`backend/project/maps/map_refresh_archify.py`).
- Z prostředí procesu se **odstraní `ANTHROPIC_API_KEY`**, aby se běh potichu neúčtoval přes API. Ostatní proměnné se předají beze změny. `CLAUDE_CODE_OAUTH_TOKEN` z `claude setup-token` se použije, jen když je nastavený.
- Claude Agent SDK se nepoužívá, protože oficiálně počítá s API klíčem. Asistent je jen pro uživatele na jeho počítači. Nabízet přihlášení claude.ai jiným lidem Anthropic bez schválení nedovoluje ([Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)).
- Kvóta předplatného je společná s Claude Code ve VS Code. Asistent ji nehlídá, jen zobrazí chybu limitu, kterou vrátí CLI.

## 3. Proces jedné session

Jedna otevřená session odpovídá jednomu běžícímu procesu:

```
claude -p
  --input-format stream-json --output-format stream-json --verbose --include-partial-messages
  --model <opus|sonnet|fable>                 # výchozí z nastavení aplikace
  [--resume <claudeSessionId>]                # navázání po restartu nebo nečinnosti
  --setting-sources user,project              # CLAUDE.md projektu + skilly uživatele i projektu
  --permission-mode dontAsk                   # co není povoleno, je zamítnuto (fáze 1)
  --allowedTools <seznam z §5>
  --settings {"disableAllHooks": true, "permissions": {"deny": [<seznam z §5>]}}
```

- **cwd** je kořen zdroje projektu z `WorkspaceSources.root(project, workspace)`: u lokálního projektu originální složka (`draft`), u git projektu pracovní strom workspace (výchozí `main`). Proto se načte CLAUDE.md projektu a jeho `.claude/skills`.
- Zprávy jdou na stdin jako řádky stream-json. Události se čtou ze stdout po řádcích.
- Spuštění a ukončení přebírá obsluhu z Archify: `Popen(shell=False)`, `WindowsJob` (`backend/integrations/windows_job.py`), zabití celého stromu procesů.
- Limity v celé instanci:
  - nejvýš **3** běžící procesy,
  - po **15 min** nečinnosti se proces ukončí a další zpráva ho obnoví přes `--resume`,
  - jeden tah nejvýš **30 min**,
  - jedna událost do UI nejvýš 64 KB, delší se zkrátí se značkou.
- Archify a asistent se navzájem neblokují.

## 4. Session: registr a historie

- Registr je jeden JSON v datovém kořeni aplikace (`assistant/sessions.json`, atomický zápis přes `.tmp` a `os.replace`). Záznam session:

  ```
  { id, projectId, workspace, title, model, claudeSessionId, createdAt, updatedAt,
    state: "idle" | "running" | "waiting_approval" | "closed" | "error",
    nodeId: string | null }   // karta, ke které session patří (volitelné)
  ```

- Historie se neduplikuje. Čte se z přepisu Claude Code `~/.claude/projects/<cwd>/<claudeSessionId>.jsonl` vlastním parserem `backend/claude_code/assistant/transcript.py`. Parser z `node_session_sources.py` vrací souhrny aktivity, ne texty zpráv. Přepis nese jen texty uživatele a asistenta, řádky nástrojů jsou jen v živých událostech.
- „Nová session“ znamená nový proces bez `--resume`. Každá session je samostatný úkol a session si navzájem nesdílejí kontext.
- Session patří k projektu (podle cwd). Rozhraní je pro všechny projekty stejné.
- Navázání na kartu se provede přes `POST /api/node-sessions/bind` (`source: "claude"`). Je to fáze 3.

## 5. Oprávnění

**Fáze 1, čti a naváděj:**

- Povoleno:
  - `Read`, `Glob`, `Grep`,
  - `Skill`,
  - `Bash` jen pro čtecí skript skillu `opora-control-center` (`python …/opora_read.py …`, GET-only).
- Zakázáno:
  - `Edit`, `Write`, `NotebookEdit`,
  - jakýkoli jiný `Bash`,
  - `WebFetch`, `WebSearch`,
  - `PowerShell` (nástroj Claude Code na Windows),
  - `Read(**/.env)`, `Read(**/.env.*)`, `Read(**/*.pem)`, `Read(**/*.key)`.
  - Celý `Bash` v deny **není**: deny má přednost před allow a zablokoval by i povolený čtecí skript. Ostatní Bash zamítne `--permission-mode dontAsk` (ověřeno v §11).
- Výsledek: asistent čte kód, mapy i plátno a radí, ale nic nezapíše.

**Fáze 2, zápis se schválením:**

- Přibude `--permission-prompt-tool mcp__opora_assistant__approve`. Malý stdio MCP server (`backend/mcp/`) má jediný nástroj `approve`. Ten pošle žádost backendu (`POST /api/assistant/approvals`, jen loopback) a čeká na rozhodnutí v UI.
  - Bez odpovědi do 10 min platí zamítnutí.
  - Odpověď je `{"behavior": "allow", "updatedInput": …}` nebo `{"behavior": "deny", "message": …}`.
- Schválit jde jen **zápis na plátno přes HTTP API OPORA**, tedy POST z receptů v `.claude/skills/opora-control-center/references/api.md`. Zápis se váže na revizi (`expectedRevision` / `digest`). Na 409 asistent znovu načte stav a nepřepisuje práci člověka.
- Změny v kódu projektu (`Edit`/`Write`/libovolný `Bash`) asistent nedělá. To je práce agenta, který dostane kartu.

## 6. Plátno a kontext

- Ke každé zprávě UI přiloží, na co se uživatel dívá:

  ```
  { projectId, workspace, layerId, selectedNodeIds[], environment: "project"|"editor"|"live" }
  ```

  Backend kontext vloží před text zprávy jako `<opora_context>…</opora_context>`. Je to údaj, ne pokyn. Zpráva začínající `/` (lomítkový příkaz) má kontext až za textem, aby ji CLI rozpoznalo jako příkaz.
- `wayfinder` a `grill-me` mají `disable-model-invocation: true`: model je sám nespustí, uživatel je píše jako `/wayfinder …` nebo `/grill-me …`. `grilling` a `opora-control-center` model použije sám.
- Plátno se čte přes skill `opora-control-center` (`opora_read.py`: `view`, `node-brief`, `frontier`, …).
- Skilly `grilling` a `wayfinder` píšou podle mapování ve [workflow-opora.md](workflow-opora.md) §3 a `references/workflow.md`. Ve fázi 1 jen navrhnou, co zapsat. Od fáze 2 zapisují se schválením.

## 7. Zadání pro model

Když o to uživatel požádá, asistent připraví zadání podle [predani-modelum.md](predani-modelum.md):

- Zadání jde **do karty, ne do promptu**: spec `goal / non_goals / acceptance`, bloky s podmínkami, pravidla `must / must_not`, vazby, `sourceRef`. Výsledkem je úplný `node-brief`.
- Doporučený model a effort zapíše jako rozhodnutí na kartu (`decisions` s `nodeId`), například `Model: Sonnet 5.5, effort medium. Rutinní dílek s testy.`
- Export pro externího agenta zůstává stávající (`/api/desktop-v3/packet/*` → `tasks/<node>.md`).
- Agent, který zadání vykoná, **nespouští asistent**. Spouští ho člověk ve VS Code nebo v terminálu, jako dosud.

## 8. API (`backend/api/editor/assistant_routes.py`, logika `backend/claude_code/assistant/`)

| Metoda | Cesta | Tělo / dotaz | Co dělá |
|---|---|---|---|
| GET | `/api/assistant/status` | | `{available, claudePath, version, running, limit}`, bez spuštění modelu (`claude --version`) |
| GET | `/api/assistant/sessions` | `project` | seznam session projektu |
| POST | `/api/assistant/sessions` | `{project, workspace?, title?, model?}` | založí session, proces vznikne až s první zprávou |
| POST | `/api/assistant/sessions/{id}/messages` | `{text, context}` | zařadí zprávu, vrátí 202. Během běžícího tahu 409 |
| GET | `/api/assistant/sessions/{id}/events` | `after=<seq>` | **SSE** stream událostí, po výpadku se naváže od `after` |
| GET | `/api/assistant/sessions/{id}/transcript` | | historie z JSONL přepisu |
| POST | `/api/assistant/sessions/{id}/title` | `{title}` | přejmenuje úkol (1–80 znaků), vrátí `{session}` |
| POST | `/api/assistant/sessions/{id}/stop` | | ukončí běžící tah (zabije proces, další zpráva obnoví přes `--resume`) |
| POST | `/api/assistant/sessions/{id}/close` | | ukončí proces a session označí `closed` |
| POST | `/api/assistant/approvals/{approvalId}` | `{decision: "allow"\|"deny", note?}` | rozhodnutí člověka (fáze 2) |

Události SSE (`{seq, type, …}`):

- `status`: `{state}`
- `text_delta`: `{messageId, text}`
- `message`: `{role, text}`
- `tool_use`: `{id, name, summary}`
- `tool_result`: `{id, ok, summary}`
- `approval`: `{approvalId, tool, input, reason}`
- `approval_resolved`: `{approvalId, decision}`
- `turn_end`: `{durationMs, usage}`
- `error`: `{message}`

Backend drží posledních 2000 událostí session v paměti. Starší historie se čte z přepisu.

Všechny `/api/assistant/*` jsou **jen pro loopback**. Přes tunel ([vzdaleny-pristup.md](vzdaleny-pristup.md)) vrací 403 i s tokenem, stejně jako `/api/agent-hooks/event`. Kdo má URL tunelu, nesmí ovládat agenta na tomto počítači.

## 9. UI (`frontend/layout/assistant-panel/`)

Asistent slouží k přemýšlení nad víc úkoly najednou. Proto má přehled úkolů na první pohled, rychlé přepínání a text, který se čte jako dokument, ne jako chat v bublinách. Design je prostorný a klidný: hodně vzduchu, jedna akcentní barva, žádné rámečky navíc.

**Tlačítko.** **Asistent** je v pravém rohu horní lišty za `LOKÁLNĚ · port` (`frontend/layout/top-bar/components/TopBar.tsx`) ve všech prostředích. Když nějaká session pracuje, tlačítko to ukáže tečkou.

**Tři velikosti** (přepínač v hlavičce panelu, ikonami s popiskem):

| Velikost | Co uživatel vidí | Kdy |
|---|---|---|
| `minimized` | Malá lišta vpravo dole: název aktivního úkolu, stav (pracuje / čeká na vás / hotovo) a počet úkolů. Klik ji rozbalí zpět. | Asistent pracuje, uživatel kouká na plátno |
| `side` (výchozí) | Panel vpravo přes celou výšku pod lištou, šířka cca 480 px (na okně pod 900 px celá šířka). Nahoře rozbalovací přehled úkolů, pod ním konverzace. | Práce s plátnem a asistentem zároveň |
| `full` | Celá plocha pod horní lištou. Vlevo trvalý sloupec úkolů (cca 300 px), vpravo konverzace ve středu se sloupcem textu nejvýš cca 72 znaků. | Soustředěné přemýšlení, delší odpovědi, grilling |

- Velikost se ukládá jednou pro aplikaci (`localStorage` `opora:assistant:v1`, stejně jako výchozí model), nikdy per projekt.
- Zkratky: `Esc` v `full` přejde na `side`, v `side` na `minimized`. `Alt+↑` / `Alt+↓` přepíná na předchozí / další úkol.

**Celá plocha: tři sloupce** (návrh: artboard 1 v artefaktu https://claude.ai/artifact/C6jQswc2bWSgcBUj5bmUfg):

- **Úkoly vlevo (288 px):**
  - nahoře „+ Nový úkol“ a pod ním hledání v názvech;
  - úkoly jsou rozdělené do skupin **Pracuje**, **Čeká na vás** (připravené s novou odpovědí) a **Ostatní**; prázdná skupina se nezobrazí.
- **Konverzace uprostřed:**
  - sloupec široký až 920 px, aby se vešly tabulky, kód a karty otázek; odstavce jsou dál nejvýš asi 80 znaků;
  - konverzace je členěná po **tazích**: každý tah má hlavičku „Tah N“ s časem, délkou a počtem kroků, pod ní zprávu uživatele, kroky nástrojů a odpověď;
  - pole pro zprávu je stejně široké jako sloupec a nad textem říká, do kterého úkolu se píše.
- **Osnova vpravo (296 px, jen od šířky okna 1280 px):**
  - **Kontext:** projekt, vrstva a vybraná karta z posledního odeslaného kontextu;
  - **Průběh:** odkazy na tahy; klik posune konverzaci a aktivní tah je zvýrazněný;
  - **Otázky k rozhodnutí:** otázky Q1…Qn z poslední odpovědi, které klik posune na místo;
  - **Kroky:** počet kroků a zamítnutých nástrojů.
- **Otázky ve tvaru grillingu:**
  - Odpověď, ve které je víc otázek ve tvaru grillingu (`❓ **Q1** - **Téma**: otázka` a pod ní `➡️ doporučení`), se vykreslí jako mřížka karet otázek (2 sloupce, na úzké ploše 1).
  - Karta má číslo a téma, otázku a doporučení jako štítek.
  - Rozpoznání je čistá funkce `logic/decisions.ts` s testem. Když rozpoznání selže, zobrazí se běžný Markdown.
- V režimu vpravo a ve velikosti minimalizovat zůstává rozvržení z dosavadního kontraktu. Jen odpověď s otázkami grillingu dostane karty v jednom sloupci.

**Přehled úkolů** (každá session je jeden úkol):

- Položka ukazuje:
  - název (lze přejmenovat dvojklikem nebo tužkou),
  - stav tečkou a slovem: *pracuje*, *připraveno*, *chyba*,
  - model,
  - čas poslední změny relativně („před 5 min“),
  - první řádek poslední odpovědi asistenta jako náhled, když je k dispozici.
- Aktivní úkol je zvýrazněný. Kliknutí přepne bez ztráty rozepsané zprávy: koncept zprávy se drží per session v paměti panelu.
- Úkol, který doběhl, zatímco se uživatel díval jinam, má značku „nové“, dokud ho neotevře.
- „+ Nový úkol“ s výběrem modelu je nahoře v přehledu. Zavřít úkol jde z položky, s potvrzením v řádku, ne dialogem.

**Konverzace:**

- Zpráva uživatele je odsazený blok s jemným akcentem vlevo. Odpověď asistenta je čistý text přes celou šířku sloupce. Žádné bubliny.
- Odpověď asistenta se vykresluje jako bezpečný základní Markdown bez HTML: odstavce, `**tučně**`, `*kurzíva*`, `` `kód` ``, bloky kódu, nadpisy, odrážky, číslované seznamy, oddělovač `---` a odkazy jako text. Implementace je vlastní (`logic/markdown.ts` → struktura → React prvky), bez `innerHTML` a bez nové závislosti, s testem.
- Písmo 15 px, řádkování 1,6, mezi zprávami velká mezera.
- Řádky nástrojů jsou jeden tlumený řádek. Víc nástrojů po sobě se sbalí do „3 kroky (Read, Grep, Skill)“ a rozbalí se kliknutím.
- Stav běhu je u konce konverzace („pracuje…“ s časem od začátku tahu). Stop je vedle pole pro zprávu.
- Pole pro zprávu roste s textem do cca 40 % výšky. `Enter` odešle, `Shift+Enter` udělá nový řádek. Nápověda `/grill-me`, `/wayfinder` se ukáže, když pole začíná `/`.

**Přejmenování úkolu:** `POST /api/assistant/sessions/{id}/title {title}` (1–80 znaků, bez řídicích znaků) → `{session}`.

**Dílky:**

- `AssistantButton`
- `AssistantPanel`: rodič, drží velikost, spojení a stav
- `TaskList`, `TaskItem`
- `SizeSwitch`
- `MinimizedBar`
- `Conversation`
- `MessageBlock`
- `Markdown`
- `ToolSteps`
- `Composer`
- `ApprovalCard` (fáze 2)

**Logika bez Reactu:**

- `assistant-events.ts`
- `markdown.ts`
- `task-overview.ts`: stav, náhled, „nové“, relativní čas
- `assistant-prefs.ts`

Každá s testem `*.test.ts`.

Když `status.available` je `false`, panel řekne, že `claude` není nainstalovaný nebo přihlášený, a nabídne příkaz `claude` k přihlášení v terminálu.

## 10. Fáze a ověření

| Fáze | Obsah | Hotovo, když |
|---|---|---|
| 0 | Ověření | Ruční běh `claude -p` se stream-json pod předplatným potvrdí tvar událostí, `--include-partial-messages`, vzor `Bash(...)` v `--allowedTools` a `--resume` s novou zprávou. Výsledek se zapíše sem do §11 |
| 1 | Čti a naváděj | Tlačítko, panel, víc session, SSE, `--resume`, kontext plátna, skilly. Žádný zápis. Testy: `pytest` správce session (falešný proces), `assistant-events.test.ts`. `uv run pytest backend`, `npm test`, `npm run build` |
| 2 | Zápis se schválením | MCP `approve`, karty schválení, zápis karty a zadání podle §7. Test: zamítnutý zápis nic nezmění, 409 vede k novému čtení |
| 3 | Session na kartě | `nodeId` v registru, `node-sessions/bind`, otevření session z karty |

Další fáze se staví, až předchozí ukáže skutečnou potřebu.

## 11. Ověřeno ve fázi 0 (2026-10-01, Claude Code na Windows, haiku)

- Přihlášení: `system/init` má `apiKeySource: "none"` bez `ANTHROPIC_API_KEY`, tedy předplatné.
- Jeden proces přijme víc zpráv po sobě: každá zpráva na stdin = jeden tah. Každý tah začne `system/init` (stejné `session_id`) a skončí `result`.
- Události stdout, jeden JSON na řádek:
  - `system`: `init`, `status` a `thinking_tokens`. Pole `init`: `session_id`, `model`, `tools`, `skills`, `slash_commands`, `apiKeySource`, `cwd`.
  - `stream_event`: `event.type` je `message_start`, `content_block_start`, `content_block_delta` (`delta.type: "text_delta"`, `delta.text`), `content_block_stop`, `message_delta` nebo `message_stop`.
  - `assistant`: `message.content[]` s bloky `thinking` (prázdný text), `text` a `tool_use {id, name, input}`.
  - `user`: `message.content[]` s `tool_result {tool_use_id, content, is_error}`.
  - `rate_limit_event`.
  - `result`: `subtype` (`success`…), `is_error`, `num_turns`, `session_id`, `duration_ms`, `result`, `permission_denials[]`, `usage`.
- Skilly `grill-me`, `grilling`, `wayfinder` a `opora-control-center` jsou v `init.skills` / `slash_commands`.
- Zápis je zamítnutý. `--disallowedTools` nástroje úplně odebere (`Write` „No such tool available“). `--permission-mode dontAsk` zamítne Bash mimo povolený vzor (`python -c "open(...,'w')…"`, `echo > soubor`); zamítnutí jsou v `result.permission_denials`. Soubor nevznikl.
- Čtecí příkazy (`python --version`) Claude Code povolí sám i mimo vzor. Je to vestavěné chování pro příkazy jen ke čtení a nevadí to.

Živý test fáze 1 (2026-10-01, Sonnet, lokální projekt v `draft`):

- **Panel:** tlačítko v liště otevře panel, „+ Nová session“ založí session a text se streamuje.
- **Kontext a oprávnění:** model správně přečetl kontext plátna. `Read` prošel, `Write` byl zamítnut a soubor nevznikl.
- **Restart backendu:**
  - Session zůstala v registru a historie se načetla z přepisu.
  - Další zpráva navázala přes `--resume`; model si pamatoval předchozí tah.
  - Windows job ukončil celý strom procesů, žádný `claude -p` nezůstal viset.
- **Lomítkový příkaz:** `/grill-me …` spustil skill `grilling` a vrátil první kolo otázek s doporučenými odpověďmi.

## 12. Neověřeno / otevřené

- [neověřeno] Přerušení tahu bez zabití procesu (`control_request` interrupt). Fáze 1 proces zabíjí.
- Hooky uživatele jsou v asistentovi vypnuté (`disableAllHooks`), stejně jako u Archify. Zapnout je lze jen rozhodnutím zapsaným sem.
- Skill `opora-control-center` čte plátno z `http://127.0.0.1:8740`. Instance na jiném portu (test, profil) by četla jinou instanci. Kontext zprávy port zatím nenese.

## 13. Plán: asistent pro plán a zadání aplikace (návrh 2026-10-01)

Cíl: asistent rychle pochopí projekt, najde správný podklad, navrhne plán jako strom karet a zapíše zadání. Směr mu nedává odhad, ale podklad, který jde ověřit.

**Vrstva orientace.** Opora už má podklady, které stačí asistentovi zpřístupnit, protože se nemusí znovu stavět:

| Podklad | Na co | Dnes v Opoře | Asistent k němu |
|---|---|---|---|
| graphify | vztahy souborů, komunity, „kdo na koho závisí“ | `graphify-out/graph.json` | nemá (Bash jen `opora_read.py`) |
| Archify | architektura a toky jako mapa | `docs/mapy-projektu.md` | čte soubory mapy |
| LSP | definice, reference, symboly | `/api/code-intelligence/*` | nemá |
| sémantické hledání | „kde se řeší X“ | `/api/semantic-search/*` | nemá |
| plátno | karty, spec, bloky, vazby | `opora_read.py` | čte, bez hledání |
| paměť role | dřívější rozhodnutí | `/api/memory/recall` (POST) | nemá |
| web | knihovny, API, ceny | | zakázáno |

**Kroky (v tomto pořadí, každý až po ověření předchozího):**

1. **Hledání.** `opora_read.py` dostane příkazy `search <text>` (karty: název, účel, spec, bloky), `symbols` / `refs` (`/api/code-intelligence/*`), `find` (`/api/semantic-search/*`) a `recall` (paměť). Všechno jsou jen čtení. Do `ALLOWED_TOOLS` přibude `Bash(graphify query*)`. `WebFetch` a `WebSearch` se povolí jen pro čtení a výsledky jsou data, ne příkazy. Kontext zprávy ponese port instance (§12).
2. **Zápis se schválením.** Fáze 2 z §5 a §10.
3. **Recept „rozhovor → strom karet“** v `opora-control-center/references/workflow.md`: výstup `wayfinder` a `grilling` → sektor, karty, vazby a na každé kartě úplný `node-brief`. Asistent ho navrhne jako jednu dávku ke schválení.
4. **Směrovač TypeSafe Jev** (schváleno, viz níže).

**TypeSafe AI jako směrovač bez halucinací** ([docs](https://docs.typesafe.ai/introduction)). Model Jev nic nepíše. Na `state + questions` vrací typované odpovědi s pravděpodobností: `choice` (výběr z možností), `score` (hodnocení podle rubriky) a `noul` (je tvrzení pravdivé, 0–1). `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <klíč>`, SDK pro Python i JS. Není náhradou Claude Code, ale prvkem kolem něj. V Opoře by dělal tři věci:

- **Volba podkladu před tahem** (vzor [skill suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion.md), [intent routing](https://docs.typesafe.ai/patterns/intent-routing.md)): `choice` nad zdroji z tabulky výše a nad skilly → do `<opora_context>` se přidá řádek „Relevantní podklad: graphify, LSP. Ignoruj, pokud neodpovídá dotazu.“
- **Výběr karty** ([semantic find](https://docs.typesafe.ai/cookbooks/semantic_find.md), [rerank](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md)): `choice` nad kartami vrstvy, ke které se zpráva vztahuje.
- **Kontrola zadání před zápisem** ([citation check](https://docs.typesafe.ai/cookbooks/citation_check.md), [guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails.md)): `noul` ke každému tvrzení v návrhu `node-brief` („je doloženo podkladem X?“). `score` hodnotí úplnost `goal / non_goals / acceptance`. Při nízké jistotě ([confidence routing](https://docs.typesafe.ai/patterns/confidence-routing.md)) karta schválení ukáže varování a asistent se místo zápisu zeptá (grilling).

**Rozhodnutí (2026-10-01, uživatel): Jev je výjimka.** Je levný, není to chat a negeneruje text. Rozhodnutí, které by LLM stálo čas a tokeny (kam sáhnout, která karta, je tvrzení doložené), vyřeší jedním voláním. Proto je to jediné placené API v aplikaci a třetí místo v §1 a v CLAUDE.md. Pro něj neplatí pravidlo §2 „předplatné, ne API“. Pro Claude Code platí dál.

Pravidla výjimky:

- Jev **nikdy nezapisuje** a nerozhoduje za člověka. Jeho odpověď je údaj v `<opora_context>` nebo varování na kartě schválení, ne příkaz.
- Spouští se jen v tahu asistenta, který spustil člověk. Žádná automatika na pozadí bez rozhodnutí zapsaného sem.
- Klíč `TYPESAFE_API_KEY` patří do nastavení aplikace (jednou pro aplikaci), ne do projektu. Nikdy se nedostane do kontextu ani do prostředí procesu `claude`.
- Volání jde z backendu (`backend/integrations/typesafe_client.py`, test vedle), ne z modelu. Asistent dostane jen výsledek.
- Bez klíče nebo při chybě (401, 422, 429, 529) asistent běží jako dnes. Jev zrychluje, ale není podmínkou.
- Na `api.typesafe.ai` odchází jen nezbytný `state`: text zprávy, názvy a spec karet, krátké výřezy. Tajné soubory (`.env`, klíče) nikdy. [neověřeno] Retence a cena: ověřit v [legal](https://docs.typesafe.ai/legal.md) a zapsat sem.
- Přínos se měří v telemetrii: počet čtení a tokenů na tah s Jevem a bez něj a počet chybně zvolených podkladů.

Později může stejnou kontrolou (`noul`: odpovídá kód zadání?) zrychlit Oracle v [synchronizace-pravdy.md](synchronizace-pravdy.md). Oracle přitom dál nic nezapisuje. Tohle se staví, až to ukáže potřeba.
