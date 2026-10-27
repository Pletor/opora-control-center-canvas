"""Přístup k tabulce `journey_runs` (append-only doklady přehrání cest); transakci vlastní volající."""
import json


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
