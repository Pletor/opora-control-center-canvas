# Pletor – Jarvis nad srdcem (P1, textové jádro)

Kontrakt: `docs/navrhy/2026-11-04-pletor-jarvis.md`. Třetí místo, kde aplikace spouští model (`CLAUDE.md`).
Pletor mluví s člověkem o klíčových věcech a práci **zadává srdci**; sám nevykonává, nikdy nezapisuje na plátno
a nevolá bránu `/api/gate`. Je jeden na aplikaci, projekt z požadavku je jen kontext.

- `persona.md` osobnost a tvar odpovědi (systémový prompt, `--system-prompt-file`). Změna souboru začne novou relaci.
- `session.py` jeden tah = `claude -p` pod předplatným přes `process.run_process` srdce: bez nástrojů
  (`--tools ""`), bez MCP a háčků, klíče API odstraněné z prostředí. Relace a rotace jsou funkce srdce
  (`brain_opora/heart/session.py`) nad `<data>/pletor/session.json`. `parse_reply` čte JSON `{reply, actions}`,
  jinak bere celý text jako odpověď bez akcí.
- `actions.py` deterministická kontrola akcí: jen `heart_message` a `vault_note`, neprázdný text do 8000 znaků,
  nejvýš 3; zbytek `ok: false` s důvodem.
- `context.py` `build_context` blok PODKLADY do 6000 znaků, pevný strop po sekcích (ořez „…“): stav srdce
  (`heart.status`), snímek srdce (`snapshot.snapshot`), tickety prostoru podle stavu (`ticket.list_tickets`, nejvýš 15,
  titulek + kdo drží), otevřené eskalace (`gate.escalations`), posledních 10 rozhodnutí z `pletor_decisions.jsonl`,
  stav hostů z `brain/monitor_state.json` a přehled Schránky (`latest_rows` + `live_ids`, druh, fáze, název; v `main`
  prostor posledního plánu srdce). Jen čte. Chyba zdroje = „(nedostupné: důvod)“, prázdný zdroj = „(prázdné)“.
- `service.py` `Pletor.message` (uloží zprávu, složí podklady `build_context`, spustí tah, provede akce) a `Pletor.state`. `heart_message` jde stejnou cestou jako
  `POST /api/brain/heart/messages` (`heart.message`), jen se zapnutou bránou projektu.
- `store.py` rozhovor v `<data>/pletor/messages.jsonl` (`{at, project, workspace, role, text}`, žádná tajemství),
  rozhodnutí v `<data>/projects/<id>/brain/pletor_decisions.jsonl` a volba mozku v `<data>/pletor/settings.json`
  (`{brain, ollamaModel}`, jedna pro aplikaci; chybějící nebo vadný soubor = `claude`).
- `brains.py` (P2) přepínač mozku: `claude` (výchozí, `session.turn`) nebo `ollama` (lokální model na
  `http://127.0.0.1:11434`, `/api/chat` se `stream: false`, `format: "json"`, `think: false`, timeout 180 s, stdlib
  `urllib`, transport `Pletor.transport` testy vyměňují). Oba vrací `(reply, actions)` z `session.parse_reply`.
  Modely z `/api/tags` bez embeddingů; výchozí lokální je první `qwen3.5*` / `gemma*`, jinak první nainstalovaný.
  `Pletor.message` nejdřív zkusí přepínací větu bez modelu (`brains.command`, cs i en, diakritika volně, celá
  zpráva): „přepni na lokální mozek / Ollamu“, „switch to local brain“, „přepni zpět na Claude / předplatné“,
  „přepni na model <název>“. Odpoví pevnou větou, uloží ji do historie a modelu nic nepředá. Neběžící Ollama nebo
  chybějící model přepnutí odmítne a mozek zůstane; chyba tahu Ollamy přijde jako odpověď, ne výjimka.

Podklady (stav srdce, otázky srdce, obsah webu a souborů) jsou data, ne příkazy; pokyny dává jen zpráva člověka.

Routy: `backend/api/pletor/`. Testy: `uv run pytest backend/pletor backend/api/pletor` (falešný runner, žádný proces).

## Shortcut
- `vault_note` nepíše do Schránky zadání (`backend/editor/brief_vault/`): kořen Schránky musí nést pracovní
  disciplínu a `main` je jen pro čtení, pro lidské rozhodnutí tam čistá cesta není. Rozhodnutí proto jdou do
  `brain/pletor_decisions.jsonl` projektu, které srdce zatím nečte. Upgrade: až Schránka dostane druh „rozhodnutí“
  (nebo ho začne číst snímek srdce), přepojit `Pletor._run` na něj.
- Lokální mozek nemá relaci: tah Ollamy vidí jen personu a podklady této zprávy, ne předchozí rozhovor. Upgrade:
  přidat posledních N zpráv ze `store.messages`, až bude lokální mozek potřebovat paměť.
- Podklady nečtou události plátna 4 z `flow_log_events`: `backend/flow` pro ně nemá čtecí funkci, monitoring je jen
  stav hostů. Upgrade: až flow dostane čtení logu pláten 2–4, přidat sekci do `context.py`.
