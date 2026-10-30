Schránka zadání pro prostředí Editor: doslovné a verzované fragmenty zadání, jejich rozdělení, brány cyklu a karty z fragmentů (docs/navrh-schranka-zadani.md, docs/schranka-neurony.md, docs/schranka-bunka.md). Router je v `backend/api/editor/brief_vault_routes.py` a `brief_vault_check_routes.py`.

- `brief_vault.py` vstup a zápisové operace (nový fragment `brief` / `question` zapíše i vstup vstupní brány, `backend/brain_opora/determinism/intake.py`; `apply(..., intake=False)` ho vynechá, používá ho zrcadlo výslechu `brain_opora/determinism/brief_vault_link.py`), `brief_vault_model.py` tvar revize, `brief_vault_read.py` a `brief_vault_tree.py` čtení a strom.
- `brief_vault_split.py` rozdělení bez ztráty textu, `brief_vault_develop.py` a `brief_vault_details.py` výzkum a upřesnění.
- `brief_vault_gates.py`, `brief_vault_gate_rules.py`, `brief_vault_proposals.py`, `brief_vault_next.py` brány cyklu a fronta práce; `brief_vault_check.py` poradní kontrola přes Jev, `brief_vault_mirror.py` Zrcadlo.
- `brief_vault_plan*.py`, `brief_vault_placement.py`, `brief_vault_refs.py`, `brief_vault_marks.py` plán struktury, karty a odkazy karet na fragmenty.
- `brief_vault_cell.py` spustitelná buňka, `brief_vault_lessons.py` a `brief_vault_disciplines.py` poučení a disciplíny.
