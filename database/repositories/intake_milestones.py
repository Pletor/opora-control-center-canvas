"""Řádky `intake_milestones` (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5).

Srdce milník navrhne (`proposed`), člověk ho aktivuje nebo zamítne. Aktivní je v oblasti nejvýš jeden (unikátní
index `intake_milestones_one_active`): `activate` nejdřív nahradí dosavadní aktivní (`superseded`, řádek zůstává
jako historie). Zamítnutý návrh je také `superseded`. Kritéria jsou JSON `[{id, text, cards[]}]`; splnění se
počítá z plátna, neukládá se. Transakci vlastní volající."""
import json

COLUMNS = ("id", "workspace_id", "area_id", "title", "criteria", "status", "created_at")
KEYS = ("id", "workspaceId", "areaId", "title", "criteria", "status", "createdAt")
SELECT = "SELECT " + ",".join(COLUMNS) + " FROM intake_milestones"


def public(row):
    if row is None:
        return None
    milestone = dict(zip(KEYS, tuple(row)))
    return {**milestone, "criteria": json.loads(milestone["criteria"] or "[]")}


class IntakeMilestones:
    def __init__(self, db):
        self.db = db

    def insert(self, milestone):
        """Vloží milník `{camelCase klíče}`; `criteria` je seznam, uloží se jako JSON."""
        values = {**milestone, "criteria": json.dumps(milestone.get("criteria") or [], ensure_ascii=False)}
        self.db.execute(f"INSERT INTO intake_milestones({','.join(COLUMNS)}) VALUES({','.join('?' for _ in COLUMNS)})",
                        tuple(values.get(key) for key in KEYS))

    def get(self, milestone_id):
        return public(self.db.execute(SELECT + " WHERE id=?", (milestone_id,)).fetchone())

    def list(self, workspace=None, statuses=None):
        """Milníky prostoru (None = všech prostorů) od nejstaršího; `statuses` zúží stavy."""
        condition, parameters = "1=1", []
        if workspace is not None:
            condition, parameters = "workspace_id=?", [workspace]
        if statuses:
            condition += f" AND status IN ({','.join('?' for _ in statuses)})"
            parameters += list(statuses)
        rows = self.db.execute(SELECT + f" WHERE {condition} ORDER BY created_at, rowid", parameters).fetchall()
        return [public(row) for row in rows]

    def active(self, workspace, area):
        """Aktivní milník oblasti, nebo None."""
        return public(self.db.execute(SELECT + " WHERE workspace_id=? AND area_id=? AND status='active'",
                                      (workspace, area)).fetchone())

    def activate(self, milestone_id):
        """Navržený milník → `active`, dosavadní aktivní milník oblasti → `superseded`.
        Vrací `(True, ID nahrazeného nebo None)`; `(False, None)`, když milník není `proposed`."""
        milestone = self.get(milestone_id)
        if milestone is None or milestone["status"] != "proposed":
            return False, None
        previous = self.active(milestone["workspaceId"], milestone["areaId"])
        if previous is not None:
            self.db.execute("UPDATE intake_milestones SET status='superseded' WHERE id=?", (previous["id"],))
        self.db.execute("UPDATE intake_milestones SET status='active' WHERE id=?", (milestone_id,))
        return True, previous["id"] if previous else None

    def reject(self, milestone_id):
        """Navržený nebo aktivní milník → `superseded` (zamítnutý zůstává v historii, oblast pak nemá aktivní milník);
        True, když se změnil."""
        cursor = self.db.execute("UPDATE intake_milestones SET status='superseded' WHERE id=? AND status IN ('proposed','active')",
                                 (milestone_id,))
        return cursor.rowcount == 1
