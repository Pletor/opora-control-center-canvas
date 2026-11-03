# Izolace ramen A/B – ověřené flagy `claude` (2.1.312)

Zdroj: `claude --help` a `claude -p --help` spuštěné 2026-10-28 (`claude --version` → `2.1.312 (Claude Code)`).
Oba výpisy mají stejné volby; `-p --help` jen vynechá podpříkazy. Níže jsou jen věci, které help skutečně uvádí
(citace doslova), plus tři sondy parseru bez volání modelu. Nic dalšího se nepředpokládá.

## Co help říká

| flag | citace z `claude --help` | použití v evalu |
|---|---|---|
| `--safe-mode` | „Start with all customizations (CLAUDE.md, skills, installed plugins, hooks, MCP servers, custom commands and agents, output styles, workflows, custom themes, keybindings, and more) disabled … Admin-managed (policy) settings still apply. Auth, model selection, built-in tools and plugins, and permissions work normally. Sets CLAUDE_CODE_SAFE_MODE=1.“ | **A i B** – hlavní izolace; přihlášení předplatným dál funguje |
| `--bare` | „Minimal mode: skip hooks …, LSP, plugin sync, attribution, auto-memory, background prefetches, keychain reads, and CLAUDE.md auto-discovery … Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read).“ | **nepoužito** – nečte OAuth, tedy nejde pod předplatným (pravidlo repa „předplatné, ne API“) |
| `--setting-sources <sources>` | „Comma-separated list of setting sources to load (user, project, local).“ | nepoužito – help neříká, zda řídí i skilly a CLAUDE.md; `--safe-mode` to říká výslovně |
| `--disable-slash-commands` | „Disable all skills and commands“ | záloha pro B, kdyby se nejelo v `--safe-mode` |
| `--strict-mcp-config` | „Only use MCP servers from --mcp-config, ignoring all other MCP configurations“ | **A i B** (bez `--mcp-config` → žádné MCP) |
| `--mcp-config <configs...>` | „Load MCP servers from JSON files or strings (space-separated)“ | nepředává se |
| `--allowedTools` / `--disallowedTools` | „Comma or space-separated list of tool names to allow/deny (e.g. "Bash(git *) Edit")“ | povolené: soubory + `npm/npx/node/git/python/uv/ls/cat/mkdir`; zakázané `WebFetch WebSearch` |
| `--tools <tools...>` | „Use "" to disable all tools, "default" to use the default set, or specify tool names“ | soudce: `--tools ""` |
| `--append-system-prompt <prompt>` | „Append a system prompt to the default system prompt“ | – |
| `--append-system-prompt-file` | uvedeno jen v textu `--bare`: „Explicitly provide context via: --system-prompt[-file], --append-system-prompt[-file], --add-dir …“ | **A**: kontext OPORY + text skillu (soubor, ne argv) |
| `--system-prompt <prompt>` | „System prompt to use for the session“ | soudce |
| `--add-dir <directories...>` | „Additional directories to allow tool access to“ | **A**: kopie skillu a `journey_run*.py` |
| `--output-format` | „Output format (only works with --print): "text" (default), "json" (single result), or "stream-json" (realtime streaming)“ | agent `stream-json`, soudce `json` |
| `--verbose` | „Override verbose mode setting from config“ | předává se se `stream-json` (help neříká, zda je nutné) |
| `--json-schema <schema>` | „JSON Schema for structured output validation (only works with --print).“ | soudce |
| `--permission-mode <mode>` | choices „acceptEdits, auto, bypassPermissions, manual, dontAsk, plan“ | `acceptEdits` |
| `--permission-prompts <target>` | „"none" (nobody: anything that would prompt is denied automatically; the permission mode still decides everything else)“ | `none` – nic nečeká na člověka, zamítnutí se počítají (`perm_denials`) |
| `--no-session-persistence` | „sessions will not be saved to disk and cannot be resumed (only works with --print)“ | A i B i soudce |
| `--model <model>` | „Provide an alias for the latest model (e.g. 'fable', 'opus', or 'sonnet') or a model's full name.“ | agent `opus` (volitelné), soudce `sonnet` |
| `--restricted` | „removes the built-in tools that run commands or code … unless --tools names them, and ignores user, project and local settings files … Also confines the file tools to the working directories (--add-dir included), refuses bypassPermissions …“ | nepoužito (souhra se `--safe-mode` v helpu není); kandidát na zpevnění proti čtení zlatých dat |
| `-p, --print` | „The workspace trust dialog is skipped when Claude is run in non-interactive mode … Settings files that fail validation are silently ignored in this mode“ | pracovní kopie je čerstvá, mimo repozitáře |
| `--max-budget-usd` | „Maximum dollar amount to spend on API calls (only works with --print)“ | nepoužito – týká se API, ne předplatného |
| `--max-turns` | **v helpu není** | nepoužito; strop dělá runner (wall-clock) |
| `CLAUDE_CONFIG_DIR` | **v helpu není** | nepoužito, neověřeno |

## Sondy parseru (bez volání modelu, prázdný stdin)

```
$ claude -p --bogus-flag-xyz < /dev/null
Error: unknown option '--bogus-flag-xyz'                       # parser neznámé volby odmítá
$ claude -p --append-system-prompt-file nonexistent-file.txt < /dev/null
Error: Append system prompt file not found: C:\Users\Admin\nonexistent-file.txt   # volba existuje a čte soubor
$ claude -p --max-turns 3 < /dev/null
Error: Input must be provided either through stdin or as a prompt argument when using --print   # skrytá volba je přijata
```

Celé sady flagů ramene A i soudce (níže) prošly parserem až k téže hlášce „Input must be provided…“, tedy bez
chyby voleb. Hláška zároveň potvrzuje, že `-p` bere zadání i ze stdin (soudce ho tak dostává).

## Příkazy

Společné pro A i B (pracovní adresář `C:\oe\<varianta>-<rameno>-<případ>-r<k>\w`, prostředí bez
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` a všech `OPORA_*`; zadání hned za `-p`, aby ho variadické
`--allowedTools`/`--add-dir` nepozřely):

```
claude -p "<záměr + společná patička>" --safe-mode --strict-mcp-config --no-session-persistence
  --output-format stream-json --verbose --model opus
  --permission-mode acceptEdits --permission-prompts none
  --allowedTools Read Edit Write Glob Grep TodoWrite "Bash(npm *)" "Bash(npx *)" "Bash(node *)" "Bash(git *)"
                 "Bash(python *)" "Bash(uv *)" "Bash(ls *)" "Bash(cat *)" "Bash(mkdir *)"
                 "PowerShell(npm *)" "PowerShell(npx *)" "PowerShell(node *)" "PowerShell(git *)" "PowerShell(python *)"
  --disallowedTools WebFetch WebSearch
```

Rameno A navíc (a jen tohle):

```
  --append-system-prompt-file C:\oe\…\opora-context.md      # „Base directory for this skill“ + adresa, projekt, workspace + SKILL.md
  --add-dir C:\oe\…\skill\opora-control-center C:\oe\…\opora-tools
  env: OPORA_BASE_URL=http://127.0.0.1:<port izolované OPORY>, OPORA_AGENT_NAME=eval-agent
```

Izolovaná OPORA: `uv run --project <repo> python opora_backend.py --data C:\oe\…\d --repo C:\oe\…\w
--port <volný> --ready-file … --autonomy-log …\autonomy.json` – `create_app` nad dočasnými daty, pracovní smyčky
vypnuté, `.env` ani `opora.local.toml` se nečtou, port 8740 a cesta s `opora-data` odmítnuty. Harness jako člověk
(`ui_secret` jen v procesu backendu) založí `POST /api/local-project` **prázdný** projekt (prostor `draft`, 0 uzlů,
0 akcí v agent-state) a zavolá `grant_autonomy(client, project)`. Seed se agentovi A nedává: `seeds/<případ>.json`
čte jen `grade.py` (`gold_graph` → plán přehrání cesty); kontext A ze zlaté mapy nic nebere a `GOLD_LEAK` hlídá
volání nástrojů. Git worktree OPORY se nepoužívá: na dlouhé cestě padal (`fatal: '$GIT_DIR' too big`).

### Autonomie agenta v rameni A (rozhodnutí 2026-10-28)

Agent musí OPORU ovládat sám, bez člověka. Cesta: projektový přepínač **plná autonomie agentů**
(`docs/plna-autonomie-agenta.md`, staví se v backendu). Harness ho jednou zapne jako člověk při startu izolované
OPORY (`opora_backend.grant_autonomy`); agent cookie člověka nikdy nedostane a v záznamu činnosti zůstává
původcem `agent`. **Dokud přepínač v backendu není**, `grant_autonomy` jen zjistí, zda ho backend zná, a vrátí
`status: "todo"` (TODO v kódu); kontext A pak autonomii neslibuje a `meta.autonomy` v `results.jsonl` to ukáže.
Automatický schvalovatel (vlákno, které by jako člověk přijímalo návrhy) se nestaví – nahrazuje ho přepínač.

Lidské brány, na které agent A při stavbě C01 z prázdného projektu narazí (ověřeno sondou nad dočasnými daty,
TestClient s hlavičkou `X-Opora-Actor: agent; name=eval-agent`; ✓ = agent smí už dnes):
1. ✓ `POST /api/canvas-plan` – sektor/aplikace, stránka se `site`, karty s `checks`, `spec`, `card.section` (200).
2. ✓ `POST /api/oporahub/changesets` – návrh `fields.steps` (200).
3. ✗ `POST /api/oporahub/baselines` – první přijetí základu (403 „Přijetí zadání vyžaduje člověka v UI.“);
   bez něj agent-state nenabídne `claim`.
4. ✗ `POST /api/oporahub/changesets/{id}/accept` – přijetí kroků (403); po přijetí je `claim` `ready`.
5. ✗ `POST /api/oporahub/graph-proposals/{id}/accept`, `content-changes/{id}/accept` – přijetí návrhů grafu
   a obsahu (stejné `require_human` / `by.kind == "human"`).
6. ✗ akce `review` (kontrola nahlášeného výsledku) a `close_card` = `done.confirmed` přes `/api/desktop-v3/state`
   (agent smí jen navrhnout `done`); `POST /api/desktop-v3/confirm-proposals`.
7. ✗ `POST /api/desktop-v3/autonomy` – svěření autonomie sektoru (403); starší cesta autonomního uzavření navíc
   chce evidence `review` + `merge` s URL.
8. ✗ schválení pravidel z dávky agenta (`/api/desktop-v3/rule-review`), `execution-budgets`, `review-policy`,
   `review-jobs/decisions`, `review-preview/confirm`, `design-mode` – jen pokud by na ně agent šel.
9. Mimo lidské brány, ale blokuje „hotovo“ i při plné autonomii: definice hotovo hub karty chce `gate_ready`,
   `merged` a `plan_written_back`; ty plní jen odkaz PR (`/executions/{id}/pull-request`, posílá agent-office)
   a GitHub. Lokální projekt evalu bez origin/GitHubu je nesplní → `close_card` hub karty nevznikne.

Rozdíl A − B = text skillu a kontext OPORY v system promptu, kopie skriptů skillu a běžící OPORA (prázdný projekt).
Odchylka od produkce: v `--safe-mode` se skilly nenačítají, proto skill jde jako doplněk system promptu (je
v kontextu celý od začátku, ne až po aktivaci); `references/*.md` si agent čte sám přes `--add-dir`.

## Jak ověřit, že B OPORU nevidí (NESPOUŠTĚNO – stojí zprávy z předplatného)

Automaticky při každém ostrém běhu (zdarma, v `run_eval.py`):
1. Událost `system/init` ze stream-json: pokud `skills`, `plugins`, `mcp_servers`, `slash_commands` nebo `agents`
   ramene B obsahují „opora“ → pokus jde do `errors.jsonl` jako `contamination`, ne do skóre.
2. Volání nástrojů ramene B se prohledají na `opora_*.py`, `OPORA_BASE_URL`, `:8740`, `node-brief`, `agent-state`,
   `opora-control-center`; obou ramen na `hillclimb`, `opora-vs-bare`, `cases.md`, `test_journey_plan`, `seeds/C..`.
3. `meta.api_key_source` a `meta.init_skills` jsou na každém řádku – první řádek pilotu je potřeba přečíst.

Jednorázový kontrolní běh před pilotem (po schválení, ~2 krátké zprávy na rameno, `--model sonnet` stačí):
```
cd C:\oe\control-B\w   (kopie T0)
claude -p "Odpověz jen JSON: {skills:[názvy skillů, které máš], mcp:[MCP servery], env:hodnota OPORA_BASE_URL nebo null, graphify: zda ti tvé instrukce zmiňují graphify (ano/ne), opora: zda znáš skill opora-control-center (ano/ne)}" <společné flagy B>
```
Očekávání B: `skills` bez opora, `mcp` prázdné, `env` null, `graphify: ne` (uživatelský `~/.claude/CLAUDE.md`
graphify zmiňuje – kanárek, že se nenačetl), `opora: ne`; v `system/init` žádná opora. Stejný dotaz pro A
(se flagy A): `env` = adresa izolované OPORY, `opora: ano` (doplněk system promptu prošel i v `--safe-mode`),
`graphify: ne`. Rozdíl v jiném bodě = izolace nedrží, pilot nespouštět.
