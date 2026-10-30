"""Řádky `intake_requirements` (požadavky vstupní brány, docs/navrhy/2026-10-30-metriky-a-spoustece.md §5).

Požadavek zakládá srdce (`opora_heart.py intake --requirement new`); víc vstupů se na jeden požadavek jen naváže
(`intake_entries.requirement_id`). Odložený požadavek (`deferred`) nese podmínku otevření `open_condition`
(ID milníku). Stav tu nikdo automaticky nepřepíná, o otevření rozhodne srdce. Transakci vlastní volající."""

COLUMNS = ("id", "workspace_id", "area_id", "milestone_id", "title", "status", "open_condition", "supersedes",
           "created_at")
KEYS = ("id", "workspaceId", "areaId", "milestoneId", "title", "status", "openCondition", "supersedes", "createdAt")
SELECT = "SELECT " + ",".join(COLUMNS) + " FROM intake_requirements"


def public(row):
    return None if row is None else dict(zip(KEYS, tuple(row)))


class IntakeRequirements:
    def __init__(self, db):
        self.db = db

    def insert(self, requirement):
        """Vloží požadavek `{camelCase klíče}`."""
        self.db.execute(f"INSERT INTO intake_requirements({','.join(COLUMNS)}) VALUES({','.join('?' for _ in COLUMNS)})",
                        tuple(requirement.get(key) for key in KEYS))

    def get(self, requirement_id):
        return public(self.db.execute(SELECT + " WHERE id=?", (requirement_id,)).fetchone())

    def list(self, workspace, statuses=None):
        """Požadavky prostoru od nejstaršího; `statuses` zúží stavy."""
        condition, parameters = "workspace_id=?", [workspace]
        if statuses:
            condition += f" AND status IN ({','.join('?' for _ in statuses)})"
            parameters += list(statuses)
        rows = self.db.execute(SELECT + f" WHERE {condition} ORDER BY created_at, rowid", parameters).fetchall()
        return [public(row) for row in rows]

    def deferred_until(self, workspace, condition):
        """Odložené požadavky prostoru s podmínkou otevření `condition` (ID milníku), od nejstaršího."""
        rows = self.db.execute(SELECT + " WHERE workspace_id=? AND status='deferred' AND open_condition=?"
                               " ORDER BY created_at, rowid", (workspace, condition)).fetchall()
        return [public(row) for row in rows]
