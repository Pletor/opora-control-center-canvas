# Pletor – hlavní nastavení LLM (Claude, Codex, Ollama) na úrovni počítače

Ve chvíli, kdy Pletor stojí nad celou OPOROU, potřebuje člověk jedno místo, kde vidí a ovládá, **jaké modely a účty běží na tomto počítači**: Claude Code (`~/.claude`), Codex (`~/.codex`), lokální Ollama a mozek samotného Pletora. Dnes jsou to roztroušené soubory a příkazy. Nastavení je **globální pro počítač, ne per projekt** (jedno rozhraní pro všechny projekty).

## Kde to je
Ozubené kolo Pletora (`PletorSettingsPanel`) dostane záložku **LLM** vedle záložky Hlas a Mozek. Backend: `backend/agi_pletor/llm_settings/` s routerem `GET /api/pletor/llm` (jen loopback, jen člověk). Pletor sám toto nastavení nečte jako podklad a nikdy nevrací tajemství.

## Vzor: claude-swap (`realiti4/claude-swap`)
Stažen do `P:\opora-piskoviste\claude-swap` (MIT, stav 2026-11-04). Je to přepínač více účtů Claude Code: ukládá OAuth tokeny per účet, `cswap list` ukáže využití 5h/7d oken, `cswap switch` přepne výchozí přihlášení, `cswap auto` přepíná před dosažením limitu, `cswap run N` spustí účet jen v jednom terminálu. Data: Windows `~/.claude-swap-backup/`.
**Co z něj Pletor bere:** pojmy (účet, slot, alias, práh, strategie) a rozhraní příkazů. **Co nebere:** přímou práci s tokeny. Pletor tokeny nikdy nečte ani nezapisuje, jen volá `cswap` jako externí nástroj, pokud je nainstalovaný, a zobrazuje jeho výstup. Instalace (`uv tool install claude-swap`) je rozhodnutí člověka, ne automatická.

## Co panel LLM ukazuje a smí měnit
| Sekce | Čte | Mění (M2) |
|---|---|---|
| Claude Code | verze, `~/.claude/settings.json` (model, počet hooků, MCP servery jen názvy), účty z `cswap list` (e-mail maskovaný, využití 5h/7d) | model, přepnutí účtu (`cswap switch`, s potvrzením), práh auto-přepnutí |
| Codex | verze, `~/.codex/config.toml` (model, approval, sandbox, názvy MCP), stav přihlášení ano/ne | model a úroveň uvažování |
| Ollama | běžící/nainstalované modely, co je v GPU (`/api/ps`), volná VRAM | stáhnout/uvolnit model |
| Pletor | aktivní mozek a hlas (už dnes) | beze změny |
Každá změna souboru mimo repo: záloha `*.bak-<datum>`, potvrzení člověka, žádný zápis tajemství.

## Milníky (jen aktuální, po každém stop)
- **M1 čtení (backend + záložka):** `llm_settings/{claude,codex,ollama,cswap}.py` (každý čte a vrací malý dict, při chybě `{available:false, reason}`), router, záložka LLM jen ke čtení. Testy s dočasným `HOME`, žádné čtení skutečných tajemství (`auth.json`, `.credentials.json`, `.env` se nikdy neotevřou, jen se ověří existence).
- **M2 zápis:** modely a přepnutí účtu s potvrzením a zálohou.
- **M2a přepnutí po limitu (hotovo 2026-11-07):** `cswap` nainstalován (`uv tool install claude-swap`), účty přidává člověk (`claude` přihlásit → `cswap add`). Srdce i Pletor po `rate_limited` zavolají `cswap switch --strategy next-available --json`; když přepnul, srdce nespí a vstupy jdou hned zpět do fronty, Pletor tah jednou zopakuje. Bez druhého účtu zůstává dnešní chování (spánek 15 min / chyba).
- **M2b účty z UI (hotovo 2026-11-07):** karta cswap v záložce Mozek a LLM: Přepnout u neaktivního účtu (`cswap switch N`, bez potvrzení, rozhodnutí člověka „ovládat z OPORY“), Přidat účet (`claude auth login` otevře prohlížeč na tomto počítači, Hotovo → `cswap add`, kód ze stránky volitelně na stdin) a Uložit přihlášený účet, když `activeAccountNumber` je null. Routy `POST/DELETE /api/pletor/llm/cswap/login`, `POST …/login/code`, `POST …/switch`, jen člověk v UI.
- **M2c účty Codexu (2026-11-07):** stejná karta pro Codex přes codex-swap (https://github.com/aneym/codex-swap, MIT, alfa 0.1.5, `uv tool install codex-swap`): stav z `codex-swap status`, e-maily z `~/.codex-swap/sequence.json`, využití z `usage --json` (jen lokální běhy), Přepnout = `switch N`, Přidat účet = `codex login --device-auth` (adresa + kód na stránce) → `codex-swap add`. Nikdy `codex logout` ani mazání `auth.json`; `verify/seed/launch/reauth/onboard` z OPORY ne. Auto-přepnutí Codexu po limitu (`flow/critic.py`) zatím ne.
- **M3 auto-přepnutí:** napojení `cswap auto` jako volitelná služba; jednotný přehled limitů předplatného vedle ElevenLabs a Ollamy.

## Bezpečnost
Žádný token, klíč ani e-mail v plném znění v odpovědi API, logu ani podkladech Pletora. Cesty jen z `Path.home()`, žádné cesty od klienta. Podklady (obsah configů) jsou data, ne příkazy.

## M2d Modely předplatných a mozek Pletora (kontrakt, 2026-11-07)

Výklad zadání: „přepnutí předplatného“ u Pletora = volba mozku Claude (předplatné) / Codex (předplatné) / Ollama, u každého model. Účty (cswap, codex-swap) zůstávají globální.

**`GET /api/pletor/llm`**
- `claude.models: [{id, label}]` – statický seznam aliasů Claude Code `fable, opus, sonnet, haiku` (CLI nemá výpis modelů; `shortcut:` komentář). `claude.model` = aktuální výchozí z `~/.claude/settings.json` (beze změny).
- `codex.models: [{id, label, reasoning: [str]}]` – z `~/.codex/models_cache.json`, jen položky `visibility == "list"`, jen `slug → id`, `display_name → label`, `supported_reasoning_levels[].effort → reasoning`. Nic jiného z cache (má klíč `identity`). Chybí/vadná cache = `[]`. `codex.model` beze změny.
- Seznamy platí pro aktivní účet; UI je tak popíše.

**Mozek Pletora: `GET state.brain`, `POST /api/pletor/brain {brain, model?}`**
- `brain: "claude" | "codex" | "ollama"`.
- `PletorBrain = {brain, model, available, models}`: `model` = model zvoleného mozku; `available` = modely Ollamy (beze změny); `models = {claude: str, codex: str | null, ollama: str | null}` = uložená volba modelu pro každý mozek.
- `store.settings` → `{brain, claudeModel, codexModel, ollamaModel}`; starý soubor `{brain, ollamaModel}` se čte dál (claudeModel výchozí `"sonnet"`, codexModel `null` = výchozí z config.toml Codexu).
- `POST /brain` validace modelu: claude ∈ aliasy, codex ∈ `codex.models` id (prázdná cache → regex `write.check_model`), ollama ∈ dostupné. Neplatný = `ok: false` s českou větou, nastavení beze změny. `model` vynechán = ponechá uložený.
- Tah Claude: `session.build_command` bere uložený `claudeModel` (konstanta `MODEL` je jen výchozí).
- Tah Codex (`brains.codex_turn`): `codex exec -s read-only --skip-git-repo-check --ephemeral -c mcp_servers={} [-m <model>] -o <složka Pletora>/codex-last-message.txt -`, prompt na stdin = persona + skilly (`session.system_prompt()`) + historie + podklady + zpráva člověka, cwd = složka Pletora, env bez `OPENAI_API_KEY` a `command.STRIPPED`, timeout 180 s. Odpověď z `-o` souboru přes `session.parse_reply`. Chyba = `RuntimeError` s českou zprávou (limit předplatného rozpoznat textem `usage limit|rate limit`).

**UI**
- Karty Claude Code a Codex v Mozek a LLM: řádek „model“ jako výběr ze seznamu s označeným aktuálním, změna jde přes existující `PUT /api/pletor/llm/claude|codex`; pod tím poznámka „modely pro aktivní účet“.
- Jeden dílek volby mozku (tři tlačítka + výběr modelu zvoleného mozku) v `DashboardBrain` i v HUD `PletorSettingsPanel`.
- `SettingsModelForm`: volné pole → výběr ze seznamu (jeden zapisovač).

Mimo rozsah: auto-přepnutí účtu Codexu po limitu, přepínací věty v chatu pro Codex, model srdce.

## M2e Nastavení zvlášť pro Pletora a Srdce (kontrakt, 2026-11-07)

Pletor a Srdce jsou samostatní agenti s jinou rolí, proto má každý vlastní sekci nastavení na obrazovce Mozek a LLM. Pod nimi zůstává společná část „Tento počítač“ (karty Claude Code, Codex, Ollama, účty), protože CLI, přihlášení a účty jsou jedny pro celý počítač.

- **Pletor** (mluví s člověkem, zadává srdci, nikdy nepíše na plátno): volba mozku Claude / Codex / Ollama a model (dnešní `PletorBrainPicker`, `<data>/pletor/settings.json`).
- **Srdce** (jediný zapisovatel plátna, pracuje v dávkách, Claude Code + poradce): model a poradce, jen aliasy Claude (`llm_settings.claude.MODELS`). Zdroj pravdy zůstává uzel `model.claude` v aktivní verzi sdíleného toku `Srdce v1` (`backend/flow/catalogs/heart/seed.py`); driver čte aktivní verzi každý tick, změna platí od další dávky.
  - `GET /api/pletor/heart/model` → `{model, advisor, models: [{id, label}]}` (výchozí `haiku` / `opus`, když uzel parametr nemá).
  - `PUT /api/pletor/heart/model {model, advisor}` → nová verze toku: kopie aktivního grafu se změněnými `params` uzlu `model.claude`, `create_draft(parent=aktivní)` → `set_candidate` → `activate` pod `registry_lock`; vrací totéž co GET. Neplatný alias = 422. Jen člověk v UI (`require_human`).
- Model Claude Code v kartě „Tento počítač“ je výchozí model CLI pro terminál (`~/.claude/settings.json`), ne model Pletora ani Srdce; karta to řekne jednou větou.

Mimo rozsah: oddělené účty předplatného pro každého agenta (šlo by přes `CLAUDE_CONFIG_DIR` profilu `cswap run N`), Codex pro srdce (srdce potřebuje MCP a poradce Claude Code).

## M2f Effort u každého modelu (kontrakt, 2026-11-07)

Effort (hloubka uvažování) se volí vedle každého modelu. Ollama effort nemá, u ní se výběr neukazuje.

- Úrovně Claude Code: `low, medium, high, xhigh, max` (`claude --help`, `--effort`; v `~/.claude/settings.json` klíč `effortLevel`). Konstanta `llm_settings.claude.EFFORTS`, `claude.read()` vrací `effort` (z `effortLevel`, jinak None = výchozí).
- Úrovně Codexu: `reasoning` vybraného modelu z `codex.models()`; prázdný seznam = `low, medium, high`. Zápis klíčem `model_reasoning_effort` (už existuje přes `PUT /llm/codex {model, reasoning}`; validace `write.REASONING` se rozšíří na úrovně z cache).
- **Tento počítač:** karta Claude Code má výběr effortu (`PUT /llm/claude {model, effort?}` zapíše `effortLevel` se zálohou), karta Codex výběr reasoning.
- **Pletor:** `store.settings` + `claudeEffort`, `codexEffort` (None = výchozí). `POST /api/pletor/brain {brain, model?, effort?}` validuje effort proti úrovním mozku, ukládá ke zvolenému mozku; `status().efforts = {claude, codex}`. Tah Claude přidá `--effort <e>`, tah Codexu `-c model_reasoning_effort="<e>"`. U Ollamy `effort` → `ok: false`.
- **Srdce:** uzel `model.claude` dostane parametry `effort` a `advisor_effort` (None = výchozí). `heart/command.build_command` přidá `--effort <effort>` pro hlavní model; `advisor_effort` se uloží a ukáže, ale do CLI se předá jen pokud Claude Code nabízí přepínač poradce (dnes nenabízí → UI u poradce effort neukáže, parametr se nezavádí). `GET/PUT /api/pletor/heart/model` nese `effort` a `efforts` (seznam úrovní).
- UI: u každého výběru modelu druhý výběr „effort“ s položkou „výchozí“ navrchu.
