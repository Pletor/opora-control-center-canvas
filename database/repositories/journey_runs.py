"""Přístup k tabulkám `journey_runs` a `intent_runs` (append-only doklady přehrání cest a záměru stránky);
transakci vlastní volající."""
import json


class IntentRunStore:
    """Doklady přehrání záměru stránky (`intent_runs`)."""

    def __init__(self, db, project):
        self.db, self.project = db, project

    def insert(self, record, recorded_at):
        self.db.execute(
            "INSERT INTO intent_runs(project_id,page_id,workflow_version_id,digest,stale,record,recorded_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (self.project, record["pageId"], record["workflowVersionId"], record["digest"], int(record["stale"]),
             json.dumps(record, ensure_ascii=False), recorded_at))


class JourneyRunStore:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def insert(self, record, at_utc, recorded_at):
        """Zapíše jeden doklad; starší zůstávají beze změny."""
        self.db.execute(
            "INSERT INTO journey_runs(project_id,application_id,journey_id,at_utc,plan_digest,passed,record,recorded_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (self.project, record["applicationId"], record["journeyId"], at_utc, record["planDigest"],
             int(record["passed"]), json.dumps(record, ensure_ascii=False), recorded_at))

    def latest(self):
        """{(applicationId, journeyId): doklad} s posledním dokladem každé cesty podle `at` (při shodě později uložený)."""
        rows = self.db.execute(
            "SELECT record FROM journey_runs AS run WHERE project_id=? AND seq=("
            " SELECT seq FROM journey_runs WHERE project_id=run.project_id AND application_id=run.application_id"
            " AND journey_id=run.journey_id ORDER BY at_utc DESC, seq DESC LIMIT 1)",
            (self.project,)).fetchall()
        records = [json.loads(row[0]) for row in rows]
        return {(record["applicationId"], record["journeyId"]): record for record in records}

    def head(self):
        """Nejvyšší `seq` dokladu projektu (0 bez dokladu)."""
        return self.db.execute("SELECT COALESCE(MAX(seq), 0) FROM journey_runs WHERE project_id=?",
                               (self.project,)).fetchone()[0]

    def since(self, seq, limit):
        """[(seq, doklad)] uložené po `seq` v pořadí uložení."""
        rows = self.db.execute("SELECT seq, record FROM journey_runs WHERE project_id=? AND seq>? ORDER BY seq LIMIT ?",
                               (self.project, seq, limit)).fetchall()
        return [(row[0], json.loads(row[1])) for row in rows]

    def previous(self, application_id, journey_id, seq):
        """Doklad téže cesty uložený těsně před `seq`, nebo None."""
        row = self.db.execute("SELECT record FROM journey_runs WHERE project_id=? AND application_id=? AND journey_id=?"
                              " AND seq<? ORDER BY seq DESC LIMIT 1",
                              (self.project, application_id, journey_id, seq)).fetchone()
        return None if row is None else json.loads(row[0])
