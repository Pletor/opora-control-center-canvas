"""Řádky `gate_sessions` (docs/brain-gate.md §2, §5): jedna relace pracovníka nebo srdce na token; transakci vlastní volající."""
import json

COLUMNS = ("id", "project_id", "workspace_id", "role", "worker_name", "worker_meta", "token_hash", "created_at",
           "expires_at", "revoked_at")


def _record(row):
    if row is None:
        return None
    value = dict(zip(COLUMNS, tuple(row)))
    value["worker_meta"] = json.loads(value["worker_meta"])
    return value


class GateSessionStore:
    def __init__(self, db):
        self.db = db

    def insert(self, session):
        """Uloží jednu relaci; zapisuje se jen otisk tokenu, nikdy token sám."""
        self.db.execute("INSERT INTO gate_sessions(" + ",".join(COLUMNS) + ") VALUES(" + ",".join("?" * len(COLUMNS))
                        + ")", (session["id"], session["project_id"], session["workspace_id"], session["role"],
                                session["worker_name"],
                                json.dumps(session["worker_meta"], ensure_ascii=False, sort_keys=True),
                                session["token_hash"], session["created_at"], session.get("expires_at"),
                                session.get("revoked_at")))

    def get(self, session_id):
        return _record(self.db.execute("SELECT " + ",".join(COLUMNS) + " FROM gate_sessions WHERE id=?",
                                       (session_id,)).fetchone())

    def by_hash(self, token_hash):
        """Relace k otisku tokenu (platná i neplatná), nebo None."""
        return _record(self.db.execute("SELECT " + ",".join(COLUMNS) + " FROM gate_sessions WHERE token_hash=?",
                                       (token_hash,)).fetchone())

    def revoke(self, session_id, at):
        """Jednou označí relaci za zneplatněnou; True, když ji zneplatnilo právě toto volání."""
        cursor = self.db.execute("UPDATE gate_sessions SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                                 (at, session_id))
        return cursor.rowcount == 1
