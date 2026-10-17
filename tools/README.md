Build a dev skripty. opora.py = jediný spouštěč aplikace podle opora.toml (`uv run opora`); copy-drawing-assets.mjs kopíruje fonty kreslení do dist/; serve-preview.py je starší ruční náhled nad kopií dat; opora_remote.ps1 je runbook vzdáleného přístupu (cloudflared quick tunnel + token, `docs/vzdaleny-pristup.md`).

`doc_check.py` projde markdown v repozitáři a ohlásí odkazy na cesty, které neexistují; `uv run python tools/doc_check.py` vrací nenulový kód, když nějaké najde.

`structure_check.py` projde `frontend/`, `backend/`, `database/` a `tools/` a ohlásí porušení pravidel umístění z `docs/pravidla-struktury.md` (šuplíky, testy vedle, routery v `api/`, názvy, README, délka souboru); `uv run python tools/structure_check.py` vypíše seznam.

`verify.py` je jeden příkaz brány (`npm run verify`): ruff, testy backendu, testy frontendu, ráčna nad počtem rozbitých odkazů v dokumentaci a ráčna nad porušeními struktury po pravidlech; obě smí jen klesat. `install_git_hooks.py` si na to ručně pověsí pre-commit hook; cizí hook nikdy nepřepíše.

`move_data_root.py` přesune datovou složku (i mimo repozitář) při zastaveném backendu: checkpoint SQLite, přesun, přepis uložených absolutních cest, `git worktree repair`, `[app] data` v `opora.local.toml`; `--dry-run` jen vypíše změny, záznam pro návrat je v `<nová>/move-data-root.log.json`.

`perf/` měřicí skripty výkonu plátna nad kopií dat (`perf/data_copy.py` ji vyrobí z `.data/production` do `.data/perf-copy`); popis v `perf/README.md`.
