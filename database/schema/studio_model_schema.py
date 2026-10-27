"""Technický model domény Studia (`docs/studio.md` §4); vlastník `backend/project/studio/studio_model.py`.

Jeden řádek = aktuální verze modelu jedné domény projektu. `revision` roste o 1 s každým uložením (optimistická
revize, jiná revize v zápisu = 409); celý model `opora.studio-model/1` leží v `model` (JSON). Historie se nevede:
model je pracovní definice, ne doklad.
"""
TABLES = ("studio_models",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS studio_models(
    project_id TEXT NOT NULL, domain_id TEXT NOT NULL, revision INTEGER NOT NULL,
    model TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY(project_id, domain_id));
"""
