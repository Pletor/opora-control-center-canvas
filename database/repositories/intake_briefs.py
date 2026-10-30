"""Řádky `intake_briefs` = spis výslechu požadavku (docs/navrhy/2026-10-30-vyslech-srdce.md §6).

Jeden řádek na požadavek (`requirement_id`). Situaci skládá determinismus, syntézu a otázky zapisuje srdce
(`opora_heart.py brief` / `ask`); stav `clear` smí nastavit jen kód, který ověřil kritéria jasna (§4).
JSON sloupce (`situation`, `research`, `synthesis`, `questions`) se čtou jako Python hodnoty. Čtení vstupů
požadavku (`entries_of`) tu je kvůli spouštěči výslechu: zakládající vstup rozhoduje, zda výslech běží.
Transakci vlastní volající."""
import json

COLUMNS = ("requirement_id", "workspace_id", "status", "situation", "research", "synthesis", "questions", "rounds",
           "cost_usd", "updated_at")
KEYS = ("requirementId", "workspaceId", "status", "situation", "research", "synthesis", "questions", "rounds",
        "costUsd", "updatedAt")
JSON_KEYS = {"situation": {}, "research": [], "synthesis": None, "questions": []}
SELECT = "SELECT " + ",".join(COLUMNS) + " FROM intake_briefs"


def public(row):
    if row is None:
        return None
    brief = dict(zip(KEYS, tuple(row)))
    for key, empty in JSON_KEYS.items():
        brief[key] = json.loads(brief[key]) if brief[key] else empty
    return brief


def _stored(brief):
    return tuple(json.dumps(brief.get(key), ensure_ascii=False) if key in JSON_KEYS and brief.get(key) is not None
                 else brief.get(key) for key in KEYS)


class IntakeBriefs:
    def __init__(self, db):
        self.db = db

    def get(self, requirement_id):
        return public(self.db.execute(SELECT + " WHERE requirement_id=?", (requirement_id,)).fetchone())

    def of_workspace(self, workspace):
        """`{requirementId: spis}` prostoru (pro `GET /api/intake`)."""
        rows = self.db.execute(SELECT + " WHERE workspace_id=?", (workspace,)).fetchall()
        return {item["requirementId"]: item for item in map(public, rows)}

    def save(self, brief):
        """Vloží nebo celý přepíše spis `{camelCase klíče}` (JSON sloupce jako Python hodnoty)."""
        values = {"situation": {}, "research": [], "questions": [], "rounds": 0, **brief}
        self.db.execute(f"INSERT OR REPLACE INTO intake_briefs({','.join(COLUMNS)})"
                        f" VALUES({','.join('?' for _ in COLUMNS)})", _stored(values))

    def entries_of(self, requirement_id):
        """Vstupy navázané na požadavek od nejstaršího: `[{id, text, verdict, createdAt}]`."""
        rows = self.db.execute("SELECT id, text, verdict, created_at FROM intake_entries WHERE requirement_id=?"
                               " ORDER BY created_at, rowid", (requirement_id,)).fetchall()
        return [{"id": row[0], "text": row[1], "verdict": row[2], "createdAt": row[3]} for row in rows]
