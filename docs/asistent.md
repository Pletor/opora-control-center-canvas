# Asistent: chat s Claude Code přímo v OPOŘE

Uživatel nemusí psát jen do terminálu ve VS Code. V aplikaci otevře okno s asistentem, který čte plátno, vede ho skilly `grill-me` (`grilling`), `wayfinder` a `opora-control-center` a na požádání připraví zadání pro model. Asistent je Claude Code spuštěný aplikací pod uživatelovým předplatným. Aplikace přitom nevolá API.

Stav: **fáze 1 zavedena** (2026-10-01): čtení a navádění, ověřeno živě v aplikaci. **Fáze 2 postavena** (2026-10-02): zápis na plátno se schválením podle §5.1, ověřeno testy s falešným CLI; živě ověřeno 2026-10-02 (§10). Fáze 3 čeká na skutečnou potřebu. Kontrakt karty zůstává v [karta-pro-agenty.md](karta-pro-agenty.md), předání modelům v [predani-modelum.md](predani-modelum.md), pipeline v [workflow-opora.md](workflow-opora.md).

## 1. Změna pravidla „aplikace model nespouští“

Do 2026-10-01 aplikace spouštěla model jen pro aktualizaci mapy Archify ([mapy-projektu.md](mapy-projektu.md)). Od tohoto kontraktu jsou místa tři (od K8 čtyři):

1. Archify: automatika, Sonnet, bez člověka.
2. Asistent: chat, který spouští **jen člověk** zprávou v okně asistenta.
3. Směrovač TypeSafe Jev (§13): běží jen v rámci tahu asistenta, který spustil člověk. Negeneruje text, vrací jen typované odpovědi. Ve Schránce smí Jev běžet i na žádost agenta nebo člověka jako poradní kontrola brány (`POST /api/brief-vault/gate-check`, [schranka-neurony.md](schranka-neurony.md) §7), pořád jen s typovanými odpověďmi a jen po výslovném povolení člověka pro projekt a poskytovatele.
4. Zrcadlo (BioCortexAI, [zrcadlo.md](zrcadlo.md)): lokální vývojový model jen na `127.0.0.1`, volaný jen po zápisu brány `synthesized` / `verified` u projektu zapnutého v `opora.local.toml` `[mirror]` (výchozí vypnuto), nikdy neblokuje bránu.

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
  --permission-mode default --permission-prompt-tool stdio   # dotaz mimo allow jde backendu (§5.1)
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
  - zpráva uživatele nejvýš 60 000 znaků (vejde se celé zadání projektu),
  - jedna událost do UI nejvýš 64 KB, delší se zkrátí se značkou; zpráva uživatele má strop 256 KB, takže se nezkrátí.
- Archify a asistent se navzájem neblokují.

## 4. Session: registr a historie

- Registr je jeden JSON v datovém kořeni aplikace (`assistant/sessions.json`, atomický zápis přes `.tmp` a `os.replace`). Záznam session:

  ```
  { id, projectId, workspace, title, model, claudeSessionId, createdAt, updatedAt,
    state: "idle" | "running" | "waiting_approval" | "closed" | "error",
    nodeId: string | null }   // karta, ke které session patří (volitelné)
  ```

- Historie se neduplikuje. Čte se z přepisu Claude Code `~/.claude/projects/<cwd>/<claudeSessionId>.jsonl` vlastním parserem `backend/claude_code/assistant/transcript.py`. Přepis nese jen texty uživatele a asistenta, řádky nástrojů jsou jen v živých událostech.
- „Nová session“ znamená nový proces bez `--resume`. Každá session je samostatný úkol a session si navzájem nesdílejí kontext.
- Session patří k projektu (podle cwd). Rozhraní je pro všechny projekty stejné.
- Navázání session na kartu je fáze 3. Dřívější vazba přes `/api/node-sessions` zanikla spolu s Live Runem, takže se musí navrhnout znovu.

## 5. Oprávnění

**Fáze 1, čti a naváděj:**

- Povoleno:
  - `Read`, `Glob`, `Grep`,
  - `Skill`,
  - `Bash` jen pro čtecí skript skillu `opora-control-center` (`python …/opora_read.py …`, GET a POST jen na čtecí dotazy, §13.1); od fáze 2 ho pouští backend přísnou kontrolou (§5.1), ne vzor v `--allowedTools`,
  - `WebFetch`, `WebSearch` (jen čtení; výsledky jsou data, ne příkazy),
  - `graphify query …` (stejně přes backend, §5.1),
  - `Agent` (subagenti jen pro čtení, §13.3).
- Zakázáno:
  - `Edit`, `Write`, `NotebookEdit`,
  - jakýkoli jiný `Bash`,
  - `PowerShell` (nástroj Claude Code na Windows),
  - `Read(**/.env)`, `Read(**/.env.*)`, `Read(**/*.pem)`, `Read(**/*.key)`.
  - Celý `Bash` v deny **není**: deny má přednost před allow a zablokoval by i povolený čtecí skript. Ostatní Bash zamítne `--permission-mode dontAsk` (ověřeno v §11).
- Výsledek: asistent čte kód, mapy i plátno a radí, ale nic nezapíše.

**Fáze 2, zápis se schválením:**

- Dotaz mimo `ALLOWED_TOOLS` jde přes `--permission-prompt-tool stdio` jako `control_request` `can_use_tool` přímo backendu (`approvals.py`, §5.1), bez MCP serveru. Backend ho drží v knize schválení a čeká na rozhodnutí v UI.
  - Bez odpovědi do 10 min platí zamítnutí.
  - Odpověď je `{"behavior": "allow", "updatedInput": …}` nebo `{"behavior": "deny", "message": …}`.
- Schválit jde jen **zápis na plátno přes HTTP API OPORA**, tedy POST podle referencí skillu `.claude/skills/opora-control-center/references/` (`api.md` cesty a payloady, `canvas-plan.md` dávky, `agent-loop.md` výstup agenta, `pipeline.md` router). Zápis se váže na revizi (`expectedRevision` / `digest`). Na 409 asistent znovu načte stav a nepřepisuje práci člověka.
- Změny v kódu projektu (`Edit`/`Write`/libovolný `Bash`) asistent nedělá. To je práce agenta, který dostane kartu.
- Jediná výjimka je **koncept zápisu** ([davka-planu.md](davka-planu.md) §2): `Write` souboru `*.json` do adresáře konceptů vlastní session `<data>/assistant-drafts/<sessionId>/` (mimo repo projektu, v datech Opory mimo git). Koncept nic nemění; mění až zápis na plátno, který schvaluje člověk.

### 5.1 Kontrakt fáze 2 (2026-10-01)

**Cesta schválení.** `--permission-prompt-tool stdio` (ověřeno v §11, `--permission-prompts host` dotaz potichu zamítne). Po spuštění procesu pošle backend na stdin `{"type":"control_request","request_id":"init","request":{"subtype":"initialize"}}`. CLI pak u nástroje mimo `ALLOWED_TOOLS` pošle na stdout `{"type":"control_request","request_id","request":{"subtype":"can_use_tool","tool_name","input","description","tool_use_id",…}}`. Backend odpoví na stdin `{"type":"control_response","response":{"subtype":"success","request_id","response":{"behavior":"allow","updatedInput":input}|{"behavior":"deny","message":…}}}`. MCP server není potřeba.

**Zapisovací skript.** `.claude/skills/opora-control-center/scripts/opora_write.py <cesta> --project --workspace --json-file <soubor>|--json <json>`:

- pošle POST jen na pevný seznam: `/api/graph`, `/api/node-spec`, `/api/node-text`, `/api/desktop-v3/state`, `/api/desktop-v3/block`, `/api/desktop-v3/agent-workspace`, `/api/desktop-v3/agent-output`, `/api/canvas-plan` (dávka plánu, [davka-planu.md](davka-planu.md) §3); payload nejvýš 2 MiB;
- `Content-Type: application/json`, `Origin` podle base, výchozí base z `OPORA_BASE_URL`;
- na jinou cestu nic nepošle; při 409 vypíše `conflict` a skončí kódem 3 (asistent znovu načte a použije jen svou změnu).

**Co se ptá a co ne:**

- `Read`, `Glob`, `Grep`, `Skill`, `WebFetch`, `WebSearch` a `Agent` jsou v `ALLOWED_TOOLS` a nikdy se neptají.
- Čtecí Bash (`python <cesta>/opora_read.py …` a `graphify query …`) **není** v `ALLOWED_TOOLS`. Vzor `Bash(python *opora_read.py*)` by pustil i `python -c "…" x/opora_read.py`, tedy libovolný kód. Dotaz na něj proto přijde backendu a ten ho povolí sám bez UI (`approvals.is_read`): skript musí následovat hned po `python`, soubor se jmenuje přesně `opora_read.py` a v příkazu není `; & | < > $`, backtick ani nový řádek. Jinak platí zamítnutí.
- `Edit`, `NotebookEdit` a `PowerShell` zůstávají v `DENY` i v `--disallowedTools` a nikdy se neptají.
- `Write` **není** v `DENY`, `--disallowedTools` ani `ALLOWED_TOOLS` (od 2026-10-02, koncept zápisu): deny i odebrání by dotaz zastavily dřív, než dojde k backendu, a allow by ho pustil kamkoli. Každý `Write` se proto zeptá backendu a ten rozhodne sám, bez UI (`approvals.is_draft_write`):
  - **adresář konceptů** `<data>/assistant-drafts/<sessionId>/` (`<data>` = datový kořen instance, např. `.data/production`) založí backend při spuštění procesu session a smaže ho při `close`; proces ho zná z env `OPORA_DRAFTS_DIR` (vedle `OPORA_BASE_URL`) a z pole `draftsDir` v `<opora_context>`, které plní jen backend (UI ho poslat nesmí). Model v příkazu nesmí `$`, proto potřebuje cestu doslova;
  - `auto_allow`, jen když `file_path` je absolutní, po `Path.resolve()` (odstraní `..`, následuje symlinky i junction) leží uvnitř adresáře konceptů **té** session, jméno končí `.json` a nemá `:` (alternativní datový proud NTFS), `content` je text do 2 MiB v UTF-8 a adresář existuje;
  - cokoli jiného (relativní cesta, `..` ven, symlink ven, cizí session, jiná přípona, větší obsah, session bez adresáře) je `auto_deny` s obvyklou zprávou.
- `--permission-mode` přejde z `dontAsk` na `default` a přibude `--permission-prompt-tool stdio`, aby se dotazy dostaly k backendu.
- Backend dotaz **sám zamítne bez UI**, když nejde o `Bash` s příkazem `python …opora_write.py …` ani o `Write` konceptu. Zpráva: „Asistent zapisuje jen na plátno přes opora_write.py.“
- `--json-file <soubor>` je platný jen pro koncept: absolutní cesta (v uvozovkách, s `/`), která po `resolve` leží v adresáři konceptů session a končí `.json`; soubor nejvýš 2 MiB, UTF-8, JSON objekt. Backend ho přečte a `payloadSummary` je souhrn **skutečného obsahu** (u `/api/canvas-plan` počty: „Přidá 1 oblast, 2 karty, 3 bloky, 3 porty, 3 vazby (next 1, block 1, flow 1), 2 pravidla, 1 rozhodnutí, text u 2 karet.“, s předponou „Jen ověření (dryRun), nic nezapíše.“ u `dryRun`). Jinak `auto_deny`. Otisk obsahu (sha256) drží kniha schválení; když se koncept mezi žádostí a rozhodnutím změní, `allow` se změní na `deny` („Koncept se po žádosti o schválení změnil; pošli zápis znovu.“).
- Ostatní dotazy se ukážou v UI. Session přejde do `waiting_approval` a pošle událost `approval {approvalId, tool, input, reason}`, kde `input` obsahuje rozparsovaný `{route, project, workspace, payloadSummary}`. Bez odpovědi do 10 min platí zamítnutí.
- `POST /api/assistant/approvals/{approvalId} {decision, note?}` pošle `control_response` (`allow` s `updatedInput` = původní input, nebo `deny` s `message` = poznámka). Událost `approval_resolved` vrátí session do `running`.
- Pozor: povolovací pravidla z `--setting-sources user,project` se sčítají s `--settings`. Pravidlo `Write`/`Bash(…)` v allow uživatele nebo projektu by dotaz k backendu obešlo (Ample má `Bash(graphify *)`); deny v `--settings` hlídá jen `Edit`, `NotebookEdit`, `PowerShell` a citlivé `Read`.

**UI.** `ApprovalCard` v konverzaci ukáže, kam zápis jde (cesta a karta), shrnutí payloadu a tlačítka Povolit / Zamítnout s poznámkou. Úkol čekající na schválení je ve skupině „Čeká na vás“. Logika parsování a shrnutí je v `logic/approval.ts` s testem.

**Hotovo, když:**
- zamítnutý zápis nic nezmění (test i živě),
- povolený `/api/node-spec` se na kartě objeví,
- 409 vede k novému čtení,
- `Edit` se na nic neptá a projde zamítnutý.

## 6. Plátno a kontext

- Ke každé zprávě UI přiloží, na co se uživatel dívá:

  ```
  { projectId, workspace, layerId, selectedNodeIds[], environment: "project"|"editor"|"hub" }
  ```

  Backend kontext vloží před text zprávy jako `<opora_context>…</opora_context>`. Je to údaj, ne pokyn. Zpráva začínající `/` (lomítkový příkaz) má kontext až za textem, aby ji CLI rozpoznalo jako příkaz.
- `wayfinder` a `grill-me` mají `disable-model-invocation: true`: model je sám nespustí, uživatel je píše jako `/wayfinder …` nebo `/grill-me …`. `grilling` a `opora-control-center` model použije sám.
- Plátno se čte přes skill `opora-control-center` (`opora_read.py`: `view`, `node-brief`, `frontier`, …).
- Skilly `grilling` a `wayfinder` píšou podle mapování ve [workflow-opora.md](workflow-opora.md) §3 a `references/workflow.md`. Ve fázi 1 jen navrhnou, co zapsat. Od fáze 2 zapisují se schválením.

### 6.1 Rozsah práce: „Výběr“ a „Celý obraz“ (kontrakt 2026-10-02)

Vznikl z běhu `707d5523…`: asistent v jednom tahu stavěl celé plátno pěti dávkami po 30–45 kB, minuty generoval naslepo a člověk nevěděl, na čem pracuje. Proto jsou dva módy:

- **Celý obraz** (`scope: "board"`, výchozí): jako dosud, asistent pracuje autonomně nad celým plátnem.
- **Výběr** (`scope: "selection"`): rozsah = uzly vybrané na plátně (`selectedNodeIds`; oblast nebo sektor zahrnuje i svůj obsah). Asistent jde do hloubky jen u nich: text karty (podklad), spec, bloky s porty, pravidla, `sourceRef`. Když práce navazuje na uzel mimo výběr, **jen vytvoří vazbu** (`next` / `block`) na existující uzel, nic v něm nemění a nezakládá nové uzly mimo výběr. Na konci napíše, co v rozsahu udělal, a navrhne **jeden další navazující uzel** (po vazbách) a počká, až ho člověk vybere. Bez výběru v tomto módu se nejdřív zeptá, na čem pracovat.
- Rozsah se **nevynucuje** v backendu (rozhodnutí uživatele 2026-10-02), je to instrukce pro model. Schvalování zápisů zůstává beze změny.
- **Kontext:** UI pošle `scope` v kontextu zprávy (`"board"` | `"selection"`, `validate_context` jiné hodnoty odmítne). `compose` při `"selection"` přidá za `<opora_context>` jednu větu: `Rozsah: jen vybrané uzly (selectedNodeIds) do hloubky; navazující uzly jen propoj vazbou; na konci navrhni další uzel a počkej.` Bez výběru: `Rozsah: výběr, ale nic není vybráno; zeptej se, na čem pracovat.`
- **UI:** přepínač „Výběr / Celý obraz“ v panelu asistenta u pole zprávy; volba je preference aplikace (`assistant-prefs`), ne projektu. U módu Výběr panel ukáže, kolik uzlů je vybráno.
- **Skill:** `references/workflow.md` „Mód Výběr“ popisuje postup výše.

### 6.2 Plátno se po zápisu asistenta načte znovu

Zápis asistenta jde přes backend z jiného procesu; otevřený editor o něm dosud nevěděl (`frontend/shared/desktop-state/logic/state-store.ts` načítá jen při mountu), takže po „Povolit“ se na plátně nic nezměnilo. Pravidlo: když v panelu přijde `tool_result` s `ok: true` k nástroji, jehož žádost o zápis člověk povolil (`approval` → `approval_resolved allow` → `tool_result` téhož tahu), panel to ohlásí callbackem nahoru (`onCanvasWritten`) a rodič editoru znovu načte graf i stav Desktop v3 (stejná cesta jako při otevření projektu). Neuložené místní úpravy se nepřepíšou: platí stávající zámek a revize; při rozporu se ukáže stávající konflikt.

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
| POST | `/api/assistant/sessions/{id}/messages` | `{text, context}` | zařadí zprávu (text nejvýš 60 000 znaků), vrátí 202. Během běžícího tahu 409 |
| GET | `/api/assistant/sessions/{id}/events` | `after=<seq>` | **SSE** stream událostí, po výpadku se naváže od `after` |
| GET | `/api/assistant/sessions/{id}/transcript` | | historie z JSONL přepisu |
| POST | `/api/assistant/sessions/{id}/title` | `{title}` | přejmenuje úkol (1–80 znaků), vrátí `{session}` |
| POST | `/api/assistant/sessions/{id}/stop` | | ukončí běžící tah (zabije proces, další zpráva obnoví přes `--resume`) |
| POST | `/api/assistant/sessions/{id}/close` | | ukončí proces a session označí `closed` |
| POST | `/api/assistant/approvals/{approvalId}` | `{decision: "allow"\|"deny", note?}` | rozhodnutí člověka o zápisu na plátno (§5.1): `{approvalId, decision, session}`. Neznámá žádost 404, už rozhodnutá (i po 10 min nebo automaticky) 409, špatné tělo 422 |

Události SSE (`{seq, type, …}`):

- `status`: `{state}`
- `progress`: `{messageId, kind, chars, name?}` — model generuje bez viditelného textu: `kind: "thinking"` (přemýšlení) nebo `"tool_input"` (vstup nástroje, `name` = nástroj, např. koncept dávky přes `Write`). `chars` je dosud vygenerovaná délka; stream ho posílá nejvýš po každých 2 000 nových znacích bloku a znovu od nuly u nového bloku. Panel ho ukáže u běžícího tahu („Přemýšlí… 3 kB“, „Píše Write… 24 kB“), aby dlouhé generování nevypadalo jako zaseknutí.
- `text_delta`: `{messageId, text}`
- `message`: `{role, text}`
- `tool_use`: `{id, name, summary}`
- `tool_result`: `{id, ok, summary}`
- `approval`: `{approvalId, tool, input, reason}`; `input` je `{route, project, workspace, node, script, payloadSummary}`. Automatické zamítnutí má `auto: true` a `input: {summary}`
- `approval_resolved`: `{approvalId, decision, note?, auto?, timeout?}`
- `turn_end`: `{durationMs, usage}`
- `error`: `{message}`

Backend drží posledních 2000 událostí session v paměti. Starší historie se čte z přepisu.

Všechny `/api/assistant/*` jsou **jen pro loopback**. Přes tunel ([vzdaleny-pristup.md](vzdaleny-pristup.md)) vrací 403 i s tokenem, chybou „Tohle běží jen na tomto počítači.“ (totéž platí pro `/api/rlm*`), stejně jako `/api/agent-hooks/event`. Kdo má URL tunelu, nesmí ovládat agenta na tomto počítači.

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
| 2 | Zápis se schválením | **Postaveno 2026-10-02** podle §5.1 (bez MCP, `--permission-prompt-tool stdio`): `opora_write.py` s testem, `approvals.py` + `approval_book.py`, `initialize` po startu, `approval` / `approval_resolved`, `waiting_approval`, zamítnutí po 10 min, `POST /api/assistant/approvals/{id}`, `ApprovalCard` a „Čeká na vás“. Testy (falešné CLI): zamítnutý zápis nic nezmění, allow vrátí původní input, timeout zamítne, `Edit` zamítne backend bez UI, dvojí rozhodnutí 409, 409 skriptu = `conflict` a kód 3. **Živě ověřeno 2026-10-02:** povolený `/api/node-spec` se objevil na kartě (revize 0 → 1) a 409 vede k novému čtení |
| 3 | Session na kartě | `nodeId` v registru, vazba session ↔ karta (nový návrh), otevření session z karty |

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

Ověření fáze 2 (2026-10-01, haiku, mimo `.claude`):

- `--permission-mode default --permission-prompts host` žádný `control_request` nepošle. Dotaz zamítne jako `system/permission_denied` a soubor nevznikne.
- `--permission-mode default --permission-prompt-tool stdio` s úvodním `initialize` pošle `control_request` `can_use_tool` (`tool_name: "Bash"`, `input.command`, `permission_suggestions`, `blocked_path`, `tool_use_id`). Odpověď `allow` s `updatedInput` příkaz provede (složka vznikla). `deny` ho zamítne (`permission_denials` v `result`).
- Cesta pod `~/.claude` je pro CLI citlivá: zápis tam zamítne `safetyCheck` ještě před dotazem.

Živý test fáze 2 (2026-10-02, Sonnet, náhledová instance 8791, lokální projekt):

- **Čtení bez dotazu:** `opora_read.py search` a `node-spec` pustil backend sám (`approvals.is_read`). Skript četl instanci 8791 přes `OPORA_BASE_URL`. `search "prihlaseni"` našel kartu „Přihlášení“ i bez diakritiky.
- **Zápis se schválením:** `opora_write.py /api/node-spec` přepnul session do `waiting_approval`. Karta schválení v UI ukázala cestu, kartu a shrnutí payloadu. Po kliknutí na Povolit se spec zapsal a revize se zvedla z 0 na 1.
- **Nalezená chyba, opravena:** Git Bash (MSYS) přepsal argument `/api/node-spec` na `C:/Program Files/Git/api/node-spec` a skript zápis odmítl. `opora_write.route_of` takovou cestu vrátí na `/api/…` ještě před kontrolou allowlistu.
- **Obcházení zamítnuto:** příkaz s předponou `MSYS_NO_PATHCONV=1` backend zamítl sám, bez UI.

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
- Uzavřeno: proces dostane `OPORA_BASE_URL` vlastní instance (§13.1).

## 13. Plán: asistent pro plán a zadání aplikace (návrh 2026-10-01, kroky 1, 2 a 4 hotové)

Cíl: asistent rychle pochopí projekt, najde správný podklad, navrhne plán jako strom karet a zapíše zadání. Směr mu nedává odhad, ale podklad, který jde ověřit.

**Vrstva orientace.** Opora už má podklady, které stačí asistentovi zpřístupnit, protože se nemusí znovu stavět:

| Podklad | Na co | Dnes v Opoře | Asistent k němu |
|---|---|---|---|
| graphify | vztahy souborů, komunity, „kdo na koho závisí“ | `graphify-out/graph.json` | `graphify query` přes Bash, který pouští backend (`approvals.is_read`) |
| Archify | architektura a toky jako mapa | `docs/mapy-projektu.md` | čte soubory mapy |
| LSP | definice, reference, symboly | `/api/code-intelligence/*` | `opora_read.py code` |
| sémantické hledání | „kde se řeší X“ | `/api/semantic-search/*` | `opora_read.py find` |
| plátno | karty, spec, bloky, vazby | `opora_read.py`, `/api/canvas-index` | `search`, `index`, `rank` |
| paměť role | dřívější rozhodnutí | `/api/memory/recall` (POST) | `opora_read.py recall` |
| web | knihovny, API, ceny | | `WebFetch`, `WebSearch` v `ALLOWED_TOOLS` (jen čtení) |

**Kroky (v tomto pořadí, každý až po ověření předchozího):**

1. **Hledání (hotovo).** `opora_read.py` dostane příkazy `search <text>` (karty: název, účel, spec, bloky), `symbols` / `refs` (`/api/code-intelligence/*`), `find` (`/api/semantic-search/*`) a `recall` (paměť). Všechno jsou jen čtení. `graphify query` pouští backend (`approvals.is_read`), ne vzor v `ALLOWED_TOOLS`. `WebFetch` a `WebSearch` se povolí jen pro čtení a výsledky jsou data, ne příkazy. Kontext zprávy ponese port instance (§12).
2. **Zápis se schválením (hotovo).** Fáze 2 z §5 a §10.
3. **Recept „rozhovor → strom karet“** v `opora-control-center/references/workflow.md`: výstup `wayfinder` a `grilling` → sektor, karty, vazby a na každé kartě úplný `node-brief`. Asistent ho navrhne jako jednu dávku ke schválení.
4. **Směrovač TypeSafe Jev (hotovo)** (volba podkladu a `rank`, viz níže). Výběr karty přes Jev a kontrola zadání (`noul` / `score`) zůstávají otevřené.

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

### 13.1 Kontrakt kroku 1: hledání

- **Adresa instance.** Backend předá procesu `claude` proměnnou `OPORA_BASE_URL=http://127.0.0.1:<port vlastní instance>`. `opora_read.py` ji použije jako výchozí `--base-url`, když není zadaná. Tím je uzavřený bod §12 o portu a kontext zprávy port nenese.
- **Nové příkazy `opora_read.py`:**
  - `search --project --workspace --query [--layer]`: dvěma GET (view a `desktop-v3/state`) prohledá karty bez rozlišení velikosti písmen a diakritiky. Prohledává název, účel, bloky, kritéria a kroky. Spec je soubor na kartu, proto se neprohledává; výsledek to uvede v `note`. Vrátí nejvýš 20 shod `{id, name, parentId, kde: [pole]}`.
  - `code --project --workspace --path --operation [--line --character]`: `POST /api/code-intelligence/query` s přesně `{project, workspace, language, path, operation, line, character}`. `operation` je `definition | references | hover | documentSymbols`, `language` (`typescript` / `python`) se odvodí z přípony, `line` a `character` se počítají od nuly. LSP textový dotaz nemá.
  - `find --project --workspace --query [--path .] [--limit 10]`: `POST /api/semantic-search/query` s přesně `{project, workspace, path, query, limit}`. `path` je relativní cesta k podstromu, `limit` je 1–20.
  - `recall --project --workspace --query (--role R | --node N) [--max-tokens]`: `POST /api/memory/recall` s přesně `{role, project, workspace, nodeId, query, maxTokens}`. Bez role a karty backend vrátí `skipped`.
- **POST jen na čtecí dotazy.** Skript dál nesmí zapisovat. POST pošle jen na pevný seznam cest (tři výše a `/api/rlm/rank` z §13.3), s `Content-Type: application/json` a `Origin` podle base. Na jinou cestu POST nepošle (test). Payload odpovídá backendu a neodhaduje se.
- Testy skriptu leží vedle něj a `uv run pytest backend` je nesbírá. Spouští se `uv run pytest .claude/skills/opora-control-center/scripts`.
- **Nástroje asistenta.** `ALLOWED_TOOLS` je `Read,Glob,Grep,Skill,WebFetch,WebSearch,Agent`. `graphify query` a `opora_read.py` pouští přes Bash jen backend (`approvals.is_read`). `WebFetch` a `WebSearch` nejsou v `DISALLOWED_TOOLS` ani v `DENY`. Zápis (`Edit`, `NotebookEdit`, jiný Bash, `PowerShell`) zůstává zakázaný; `Write` pustí backend jen do adresáře konceptů session (§5.1).
- **Skill.** `SKILL.md` a `references/api.md` popíšou nové příkazy a pořadí hledání: plátno `search` → `find` / `code` → graphify → Archify → `recall` → web.

### 13.2 Kontrakt Jev v1: volba podkladu

- `backend/integrations/typesafe_client.py`: `evaluate(state, questions, *, key, timeout=3.0, post=…)` → `answers` nebo `None`. Bez klíče, při chybě HTTP (401, 422, 429, 529), při timeoutu nebo neplatné odpovědi vrátí `None` a nic nevyhodí. Model je `jev-latest`, endpoint `https://api.typesafe.ai/v1/systemone`.
- **Klíč** se bere z nastavení aplikace (jednou pro aplikaci) nebo z proměnné `TYPESAFE_API_KEY` backendu. Do `child_env` procesu `claude` se nepředá, `child_env` ho odstraní stejně jako `ANTHROPIC_API_KEY`.
  - Uložení: `AppSettings.typesafe_key()` / `set_typesafe_key()` (`app_settings`, klíč `typesafe.apiKey`). Uložený klíč přebíjí prostředí.
  - `POST /api/assistant/jev-key {key: text | null}` → `{jev: {configured}}` klíč uloží nebo smaže. Klíč se nikdy nevrací. Jen loopback jako celé `/api/assistant/*`.
  - `GET /api/assistant/status` nese `jev: {configured}`.
  - Poskytovatel (`typesafe` | `celeris`) z `[jev] provider` v `opora.local.toml` (výchozí `typesafe`, neznámá hodnota = `typesafe` + varování v logu). Klíč Celeris: `POST /api/assistant/jev-key {key, provider: "celeris"}` (`app_settings` `celeris.apiKey`, záloha `CELERIS_API_KEY`); `status.jev` nese i `provider` a `keys: {typesafe, celeris}` (jen booleany). Povolení kontroly bran: `GET|POST /api/assistant/jev-gate-check {project, provider, allowed}` (zápis jen člověk). Viz [schranka-neurony.md](schranka-neurony.md) §7, §9 bod 10.
  - Klíč se čte při každé zprávě, takže zapnutí platí bez restartu. Směrovač má tvrdou mez 4 s mimo zámek session; při jejím překročení jde do telemetrie `router: {skipped: "timeout"}`.
- **Směrovač** `backend/claude_code/assistant/router.py`: před každou zprávou, která nezačíná `/`, jedno volání:
  - `state = {request: text zprávy (nejvýš 4000 znaků), environment, selectedCount}`,
  - `questions.source`: `choice` nad `canvas, find, code, graphify, archify, memory, web`,
  - `questions.needs_lookup`: `noul` „Potřebuje odpověď dohledat podklad v projektu?“.
- **Do kontextu** se přidá `hint: {sources: [až 2 s pravděpodobností ≥ 0.2], needsLookup: 0–1}`. Klíč `hint` smí vyplnit jen backend. Když ho pošle UI, validace ho odmítne. V textu pro model je hint údaj: „Relevantní podklad: … Ignoruj, pokud neodpovídá dotazu.“
- **Telemetrie:** výsledek a doba volání do událostí session jako `status` s polem `router`. Bez obsahu zprávy.
- Výběr karty a kontrola zadání (`noul` / `score`) přijdou s fází 2, kde mají kam ukázat varování.

### 13.3 Kontrakt RLM: rekurzivní hledání

Vzor [Recursive Language Models](https://arxiv.org/abs/2512.24601) (Zhang, Kraska, Khattab, MIT): velký kontext se nevkládá do promptu. Model ho drží jako proměnnou v prostředí, nahlíží do něj po kouscích, hledá v něm a dílčí otázky posílá levnějším podvoláním. Opora to dělá bez spouštění libovolného kódu, ze tří dílů:

1. **Korpus jako proměnná.** Plátno je rozdělené na oddíly (karty). Kód a dokumentaci už pokrývají `Glob`, `Grep` a `Read` po řádcích.
   - `opora_read.py index --project --workspace [--layer]`: seznam oddílů bez obsahu `{id, name, parentId, kind, chars}`, kde `chars` je velikost textu karty (účel, bloky, kritéria, kroky). Model z něj vidí tvar korpusu dřív, než cokoli načte.
   - Nahlédnutí do jednoho oddílu je stávající `node-brief` / `node-text` a hledání napříč korpusem je `search` z §13.1.
2. **Levné podvolání: řazení oddílů přes Jev.** `opora_read.py rank --project --workspace --query [--layer] [--top 10]`.
   - Skript sestaví kandidáty z indexu (id → název a prvních 300 znaků textu karty, nejvýš 255) a pošle `POST /api/rlm/rank {project, workspace, query, candidates: [{id, text}], top}`.
   - Backend (`backend/api/editor/rlm_routes.py`, logika `backend/claude_code/assistant/rlm_rank.py`, jen loopback) zavolá Jev `choice` s `criteria = {id: text}`. Vrátí `{status: "ok", ranked: [{id, p}]}` seřazené podle pravděpodobnosti, nejvýš `top`.
   - Bez klíče nebo při poruše Jev vrátí `{status: "unavailable"}` a model pokračuje bodem 3. Klíč zůstává v backendu, do procesu `claude` se nedostane.
3. **Rekurze: subagenti.** `Agent` (dříve `Task`) je v `ALLOWED_TOOLS`. Kořenový model rozdělí otázku po oddílech nebo složkách a každý kus předá subagentovi (`Explore`, levnější model). Subagent má stejná oprávnění jen pro čtení a vrací zhuštěné nálezy s odkazy `soubor:řádek` nebo `id karty`. Kořen nálezy jen skládá a celé oddíly nečte.

**Postup ve skillu** (`references/rlm.md`): `index` → `rank` (nebo `search`) → přečíst jen 2–5 nejlepších oddílů → kde nestačí, rozdělit a předat subagentům → složit odpověď s odkazy na zdroj. Co nejde doložit odkazem, je otázka pro člověka, ne závěr.

**Hotovo, když:**
- `index` a `rank` mají testy s falešným HTTP,
- `/api/rlm/rank` má test s falešným Jev (ok, bez klíče, porucha) a přes tunel vrací 403,
- `Agent` je v `ALLOWED_TOOLS` (test).
