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
- **M3 auto-přepnutí:** napojení `cswap auto` jako volitelná služba; jednotný přehled limitů předplatného vedle ElevenLabs a Ollamy.

## Bezpečnost
Žádný token, klíč ani e-mail v plném znění v odpovědi API, logu ani podkladech Pletora. Cesty jen z `Path.home()`, žádné cesty od klienta. Podklady (obsah configů) jsou data, ne příkazy.
