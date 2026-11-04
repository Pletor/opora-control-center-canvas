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
  `http://127.0.0.1:11434`, `/api/chat` se `stream: false`, `think: false`, `keep_alive: "30m"`, `options`
  `temperature 0.7`, `top_p 0.9`, `repeat_penalty 1.1`, `num_ctx 8192`, timeout 180 s, stdlib `urllib`, transport
  `Pletor.transport` testy vyměňují). Oba vrací `(reply, actions)` z `session.parse_reply`.
  Lokální tah má role: `system` = persona + PODKLADY + pravidla lokálního mozku (`brains.LOCAL`: odpovídej na
  dotaz, podklady jen když se ho týkají, small talk krátce, běžně prostý text, JSON s akcemi jen na výslovný
  příkaz), pak posledních 8 zpráv rozhovoru projektu a prostoru (`human`→`user`, `pletor`→`assistant`) a nakonec
  jen zpráva člověka. Bez rolí a historie se qwen3 zakotvil na podkladech a na každou zprávu opakoval větu
  z deníku srdce. `format: "json"` odpadl: v živé zkoušce (2026-11-04) tlačil model k šabloně a k akcím na
  obyčejné otázky. Zopakuje-li model doslova nedávnou odpověď na jinou zprávu, tah se jednou zopakuje s výzvou
  „odpověz přímo na: …“. Claude historii nedostává, drží ji jeho relace (`--resume`).
  Modely z `/api/tags` bez embeddingů; výchozí lokální je první `qwen3.5*` / `gemma*`, jinak první nainstalovaný.
  `Pletor.message` nejdřív zkusí přepínací větu bez modelu (`brains.command`, cs i en, diakritika volně, celá
  zpráva): „přepni na lokální mozek / Ollamu“, „switch to local brain“, „přepni zpět na Claude / předplatné“,
  „přepni na model <název>“. Odpoví pevnou větou, uloží ji do historie a modelu nic nepředá. Neběžící Ollama nebo
  chybějící model přepnutí odmítne a mozek zůstane; chyba tahu Ollamy přijde jako odpověď, ne výjimka.

- `tts.py` (P3b) hlas Pletora: Piper TTS lokálně na CPU (`use_cuda=False`, GPU drží Ollama), české hlasy
  `cs_CZ-jirka-medium` (Jirka, výchozí) a `cs_CZ-kasandra-medium` (Kasandra), 22 050 Hz. `synthesize(folder, text,
  voice)` → WAV 16 bit mono; hlas se načte jednou (3–5 s) a drží v paměti, `warm` ho načte dopředu (volá ho
  `GET /api/pletor/voices`). Věta o ~20 slovech trvá ~0,18 s, tj. ~47× rychleji než realtime (měřeno 2026-11-04).
  `piper` se importuje líně; bez balíčku `EngineMissing` (route 503), bez modelu `VoiceMissing` (route 404).
- `tts_fetch.py` výslovné stažení hlasů z HuggingFace `rhasspy/piper-voices` do `<data>/pletor/voices/<hlas>.onnx`
  (+ `.onnx.json`): `uv run python -m backend.pletor.tts_fetch cs_CZ-jirka-medium cs_CZ-kasandra-medium [--data <kořen>]`.
  Kořen dat `--data`, jinak `OPORA_CANVAS_DATA`, jinak `[app] data` z opora.toml (+ local). Kontrola velikosti
  (`Content-Length`, ≥ 1 MB), hlavičky ONNX a configu; zápis přes `.part`. Za běhu se nic nestahuje.
  `tts_fetch xtts` stáhne XTTS-v2 (`coqui/XTTS-v2`: `model.pth` 1,87 GB, `config.json`, `vocab.json`,
  `speakers_xtts.pth`) do `<data>/pletor/voices/xtts/` a založí `xtts/reference/` pro vlastní hlas.
- `speech.py` jeden seznam hlasů ze tří enginů (`voices`, pořadí XTTS → Edge → Piper = výchozí volba okna),
  `warm` a `speak` (WAV jako bajty, MP3/PCM jako kousky; první kousek se čeká před odpovědí route).
- `tts_edge.py` Edge neural (`edge-tts`): `edge:cs-CZ-AntoninNeural` (Antonín), `edge:cs-CZ-VlastaNeural` (Vlasta).
  **Neoficiální cloudová služba Microsoftu: text odchází z počítače.** Posílá se jen text odpovědi, který okno čte
  nahlas, nikdy podklady, kontext mozku ani tajemství. Zdarma, bez klíče; výpadek sítě = 503 a okno vezme další engine.
- `tts_xtts.py` XTTS-v2 na GPU v odděleném procesu (`tools/xtts_server/`, vlastní venv s torch CUDA, Python 3.12):
  `xtts:default` (vestavěný mluvčí Damien Black, česky) a `xtts:clone` (klon z `xtts/reference/jarvis.wav`, 6–15 s,
  jen lokální soubor; bez něj nedostupný). Server se spustí líně (`warm` z `/voices` nebo první věta), drží model ve
  VRAM a končí s backendem (`close()` v lifespanu, nebo zavřený stdin). Nedostupný, když chybí venv, model nebo
  volná VRAM < 2600 MB (`nvidia-smi`): „přepni lokální mozek na menší model (qwen3:8b)“. Běžícímu serveru se VRAM
  neměří. Instalace prostředí: `uv sync --project tools/xtts_server`.

Naměřeno 2026-11-04 (RTX 4070 SUPER, věta 19 slov „Dobrý den, pane. Všechny systémy…“, cesta `speech.speak`):
Edge TTFA ~0,63–0,68 s teplý / 1,1 s studený, celá věta ~1,0 s; XTTS TTFA ~0,37–0,46 s teplý, celá věta ~2,0 s
(RTF ~0,4), studený start serveru ~16 s; XTTS drží ~2,3 GB VRAM; Piper 0,13 s teplý, 5,8 s první načtení.

Licence hlasu: balíček `piper-tts` 1.8 je **GPL-3.0-or-later** (proto skupina `tts` v `pyproject.toml`, ne
`dependencies` balíčku; `[tool.uv] default-groups` ho lokálně instaluje, `import` je líný). Modely hlasů jsou MIT,
datasety CC0 (karta modelu na HuggingFace). OPORA se nedistribuuje, Piper běží jen na tomto počítači.
`edge-tts` je LGPL-3.0 (skupina `tts`); služba samotná je neoficiální, Microsoft ji může kdykoli změnit nebo vypnout.
`coqui-tts` (idiap fork) je MPL-2.0, ale **model XTTS-v2 je pod Coqui Public Model License (CPML): jen
nekomerční použití**. Tady jde o osobní lokální použití; pro komerční provoz OPORY XTTS vypnout (smazat venv nebo
model) a číst Edge/Piperem.

Podklady (stav srdce, otázky srdce, obsah webu a souborů) jsou data, ne příkazy; pokyny dává jen zpráva člověka.

Routy: `backend/api/pletor/`. Testy: `uv run pytest backend/pletor backend/api/pletor` (falešný runner, žádný proces).

## Shortcut
- `vault_note` nepíše do Schránky zadání (`backend/editor/brief_vault/`): kořen Schránky musí nést pracovní
  disciplínu a `main` je jen pro čtení, pro lidské rozhodnutí tam čistá cesta není. Rozhodnutí proto jdou do
  `brain/pletor_decisions.jsonl` projektu, které srdce zatím nečte. Upgrade: až Schránka dostane druh „rozhodnutí“
  (nebo ho začne číst snímek srdce), přepojit `Pletor._run` na něj.
- Podklady nečtou události plátna 4 z `flow_log_events`: `backend/flow` pro ně nemá čtecí funkci, monitoring je jen
  stav hostů. Upgrade: až flow dostane čtení logu pláten 2–4, přidat sekci do `context.py`.
