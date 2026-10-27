"""Přístup k tabulce `studio_models` (technický model domény Studia); transakci vlastní volající."""
import json


class StudioModelStore:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def get(self, domain):
        """(revize, model, updated_at) aktuální verze modelu domény, nebo None, když model ještě nikdo neuložil."""
        row = self.db.execute(
            "SELECT revision, model, updated_at FROM studio_models WHERE project_id=? AND domain_id=?",
            (self.project, domain)).fetchone()
        return (row[0], json.loads(row[1]), row[2]) if row else None

    def put(self, domain, revision, model, updated_at):
        """Zapíše verzi `revision` modelu domény (předchozí verze se přepíše)."""
        self.db.execute(
            "INSERT INTO studio_models(project_id,domain_id,revision,model,updated_at) VALUES(?,?,?,?,?)"
            " ON CONFLICT(project_id,domain_id) DO UPDATE SET revision=excluded.revision, model=excluded.model,"
            " updated_at=excluded.updated_at",
            (self.project, domain, revision, json.dumps(model, ensure_ascii=False), updated_at))
