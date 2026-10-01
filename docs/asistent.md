# Asistent: chat s Claude Code přímo v OPOŘE

Uživatel nemusí psát jen do terminálu ve VS Code. V aplikaci otevře okno s asistentem, který čte plátno, vede ho skilly `grill-me` (`grilling`), `wayfinder` a `opora-control-center` a na požádání připraví zadání pro model. Asistent je Claude Code spuštěný aplikací pod uživatelovým předplatným. Aplikace přitom nevolá API.

Stav: **kontrakt schválen** (2026-10-01), kód zatím neexistuje. Kontrakt karty zůstává v [karta-pro-agenty.md](karta-pro-agenty.md), předání modelům v [predani-modelum.md](predani-modelum.md), pipeline v [workflow-opora.md](workflow-opora.md).

## 1. Změna pravidla „aplikace model nespouští“

Do 2026-10-01 aplikace spouštěla model jen pro aktualizaci mapy Archify ([mapy-projektu.md](mapy-projektu.md)). Od tohoto kontraktu jsou místa dvě:

1. Archify: automatika, Sonnet, bez člověka.
2. Asistent: chat, který spouští **jen člověk** zprávou v okně asistenta.

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

- **cwd** je originální složka projektu (lokální projekt) nebo hlavní pracovní strom git projektu. Proto se načte CLAUDE.md projektu a jeho `.claude/skills`.
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
  { id, projectId, title, model, claudeSessionId, createdAt, updatedAt,
    state: "idle" | "running" | "waiting_approval" | "closed" | "error",
    nodeId: string | null }   // karta, ke které session patří (volitelné)
  ```

- Historie se neduplikuje. Čte se z přepisu Claude Code `~/.claude/projects/<cwd>/<claudeSessionId>.jsonl` stávajícím parserem (`backend/live_run/node_session_sources.py`).
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
  - `Read(**/.env)`, `Read(**/*.pem)`, `Read(**/*.key)`, tedy stejný deny seznam jako u Archify.
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

  Backend kontext vloží před text zprávy jako `<opora_context>…</opora_context>`. Je to údaj, ne pokyn.
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
| POST | `/api/assistant/sessions` | `{project, title?, model?}` | založí session, proces vznikne až s první zprávou |
| POST | `/api/assistant/sessions/{id}/messages` | `{text, context}` | zařadí zprávu, vrátí 202. Během běžícího tahu 409 |
| GET | `/api/assistant/sessions/{id}/events` | `after=<seq>` | **SSE** stream událostí, po výpadku se naváže od `after` |
| GET | `/api/assistant/sessions/{id}/transcript` | | historie z JSONL přepisu |
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

- Tlačítko **Asistent** je v pravém rohu horní lišty za `LOKÁLNĚ · port` (`frontend/layout/top-bar/components/TopBar.tsx`). Je vidět ve všech prostředích (projekt, editor, live run).
- Klik otevře panel vpravo nad plátnem. Panel obsahuje:
  - záložky session a tlačítko „Nová session“,
  - seznam zpráv se streamovaným textem,
  - řádky volání nástrojů (sbalené, název a krátký souhrn),
  - karty schválení „Povolit / Zamítnout“ s náhledem zápisu (fáze 2),
  - pole pro zprávu a tlačítko Stop.
- Dílky: `AssistantButton`, `AssistantPanel` (rodič, drží spojení a stav), `SessionTabs`, `MessageList`, `ToolCallRow`, `ApprovalCard`, `Composer`.
- Logika bez Reactu:
  - `logic/assistant-events.ts` skládá události SSE do stavu konverzace (test `assistant-events.test.ts`),
  - `logic/assistant-api.ts` volá endpointy.
- Výchozí model a šířka panelu se ukládají jednou pro aplikaci (Nastavení → Obecné), nikdy per projekt.
- Když `status.available` je `false`, panel řekne, že `claude` není nainstalovaný nebo přihlášený, a nabídne příkaz `claude` k přihlášení v terminálu.

## 10. Fáze a ověření

| Fáze | Obsah | Hotovo, když |
|---|---|---|
| 0 | Ověření | Ruční běh `claude -p` se stream-json pod předplatným potvrdí tvar událostí, `--include-partial-messages`, vzor `Bash(...)` v `--allowedTools` a `--resume` s novou zprávou. Výsledek se zapíše sem do §11 |
| 1 | Čti a naváděj | Tlačítko, panel, víc session, SSE, `--resume`, kontext plátna, skilly. Žádný zápis. Testy: `pytest` správce session (falešný proces), `assistant-events.test.ts`. `uv run pytest backend`, `npm test`, `npm run build` |
| 2 | Zápis se schválením | MCP `approve`, karty schválení, zápis karty a zadání podle §7. Test: zamítnutý zápis nic nezmění, 409 vede k novému čtení |
| 3 | Session na kartě | `nodeId` v registru, `node-sessions/bind`, otevření session z karty |

Další fáze se staví, až předchozí ukáže skutečnou potřebu.

## 11. Neověřeno / otevřené

- [neověřeno] Přesná pole událostí stream-json a jestli CLI přijímá v jednom procesu víc zpráv po sobě. Záložní postup je jeden proces na tah s `--resume`.
- [neověřeno] Vzor `Bash(python *opora_read.py*)` v `--allowedTools` pod Windows. Kdyby nefungoval, fáze 1 přejde rovnou na čtecí MCP nástroje.
- [neověřeno] Přerušení tahu bez zabití procesu (`control_request` interrupt). Fáze 1 proces zabíjí.
- Hooky uživatele jsou v asistentovi vypnuté (`disableAllHooks`), stejně jako u Archify. Zapnout je lze jen rozhodnutím zapsaným sem.
