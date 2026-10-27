# Studio: technický model domény

Backend vrstvy MODEL Studia (`docs/studio.md` §4). Etapa S4: úložiště a API, simulace běží v prohlížeči (S5).

- `studio_model.py` – čtení a uložení modelu `opora.studio-model/1` jedné domény s optimistickou revizí
  (`read_model`, `write_model`). Validace hlídá jen tvar a limity (≤ 1000 uzlů, ≤ 5000 hran, tělo ≤ 1 MiB,
  jedinečná id, hrana na existující uzly, `type` hrany z 12 datových typů portu); typy komponent, porty a role
  backend nevaliduje, katalog žije ve frontendu (`frontend/project/studio/model/`). `binding.nodeId` musí být
  uzel přijatého grafu projektu (jinak 422). Jiná revize v zápisu = 409. Graf se jen čte, nikdy nepíše.
- Data: tabulka `studio_models` v `project.sqlite` (`database/schema/studio_model_schema.py`,
  `database/repositories/studio_models.py`), jedna aktuální verze na doménu, bez historie.
- Router: `backend/api/project/studio_model_routes.py` (`GET/PUT /api/studio/model?project=&domain=`).

Test: `test_studio_model.py` (`uv run pytest backend/project/studio`).
