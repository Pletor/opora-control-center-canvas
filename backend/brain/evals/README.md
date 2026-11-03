# Evaly procesu srdce

Sondy a evaly celého procesu (srdce ↔ brána ↔ dělník), přesunuté z `.claude/hillclimb/` (kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4). Liší se od evalů skillů: ty jsou v pluginu Brainu (`<plugin>/evals/`) a pouští je `claude plugin eval` přes `backend/brain/evaluate.py`.

V gitu jsou jen skripty a vstupy. Výsledky (`results*.json`, `raw/`, `traces/`, `artifacts/`, složky běhů) hlídá `.gitignore` a zůstávají lokálně vedle skriptu. Sondy spouštějí skutečné modely pod předplatným a stojí peníze. Přepis sond na tickety přijde až po dostavbě, některé scénáře proto ještě volají starý tvar brány.

Spouští se z kořene repa (`<repo>`):

- `heart-flow/`: sonda toku mozku oběma směry (srdce → brána → pracovník a zpět), scénáře F / R / X / O, cena 0,2–0,7 USD.
  - `uv run --project <repo> python backend/brain/evals/heart-flow/probe.py --run r1 [--scenarios F1,F2,...,REAL]`
  - `... probe.py --run o1 --scenarios O1 --variant cards|tasks [--rounds 4] [--git-poll 30]` (scénáře O, `orch.py`, server `orch_serve.py`)
  - `... probe.py --table` vypíše srovnání O1 z `results.json`.
  - `jev_eval.py build|run` je offline test rozhodovací vrstvy Jev nad událostmi brány (`jev_events.json`, klíč `OPORA_JEV_KEY`).
- `opora-vs-bare/`: OPORA proti holému terminálu nad šablonou `templates/T0` (případy `cases.md`, specifikace `specs.py`, izolace `isolation.md`, podrobný postup `README.md`).
  - `python run_eval.py --variant <v> --arm AB --cases C01 --dry-run`, pak ostrý běh s `--approve-harness`; hodnocení `python grade.py judge --variant <v>`.
  - `multi/`: eval o víc sezeních (`SCENAR.md`), `python -B multi/run_multi.py --variant m1 --arms A,B,C,E --reps 2 --dry-run`.
- `research-desk/`: eval výzkumného stolu srdce (V0 / V1 / V2, 9 scénářů): `uv run --project <repo> python backend/brain/evals/research-desk/eval.py --run e1 [--variants V0,V1,V2]`.

Čisté pomocníky mají testy (`heart-flow/test_orch.py`, `opora-vs-bare/multi/test_*.py`). Běží v `uv run pytest backend/brain/evals`, bez modelu a bez sítě.
