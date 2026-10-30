"""Řádky `intake_entries` a `intake_entries_fts` (vstupní brána, docs/navrhy/2026-10-30-vstupni-brana.md §5).

Vstup je neměnný: repozitář ho jen vloží (spolu s řádkem FTS5) a čte. Stanovisko a otisk počítá
`backend/brain_opora/determinism/intake.py`. Transakci vlastní volající."""

COLUMNS = ("id", "workspace_id", "source", "source_ref", "text", "fingerprint", "created_at", "verdict", "layer",
           "area_id", "milestone_id", "requirement_id", "confidence", "reason", "cost_usd", "jev_calls")
KEYS = ("id", "workspaceId", "source", "sourceRef", "text", "fingerprint", "createdAt", "verdict", "layer",
        "areaId", "milestoneId", "requirementId", "confidence", "reason", "costUsd", "jevCalls")
SELECT = "SELECT " + ",".join(COLUMNS) + " FROM intake_entries"


def public(row):
    """Vstup v podobě API (`camelCase`)."""
    return None if row is None else dict(zip(KEYS, tuple(row)))


class IntakeEntries:
    def __init__(self, db):
        self.db = db

    def insert(self, entry):
        """Vloží vstup `{camelCase klíče}` a jeho text do FTS5."""
        self.db.execute(f"INSERT INTO intake_entries({','.join(COLUMNS)}) VALUES({','.join('?' for _ in COLUMNS)})",
                        tuple(entry.get(key) for key in KEYS))
        self.db.execute("INSERT INTO intake_entries_fts(text, entry_id, workspace_id) VALUES(?,?,?)",
                        (entry["text"], entry["id"], entry["workspaceId"]))

    def get(self, entry_id):
        return public(self.db.execute(SELECT + " WHERE id=?", (entry_id,)).fetchone())

    def first_with(self, workspace, fingerprint):
        """Nejstarší vstup prostoru se stejným otiskem, nebo None."""
        return public(self.db.execute(SELECT + " WHERE workspace_id=? AND fingerprint=? ORDER BY created_at, rowid"
                                      " LIMIT 1", (workspace, fingerprint)).fetchone())

    def by_source(self, source, source_ref):
        """Vstup zapsaný ze zdroje `source` s odkazem `source_ref` (lístek, fragment), nebo None."""
        return public(self.db.execute(SELECT + " WHERE source=? AND source_ref=? ORDER BY created_at DESC, rowid DESC"
                                      " LIMIT 1", (source, source_ref)).fetchone())

    def similar(self, workspace, query, exclude, until, limit=3):
        """ID nejbližších vstupů prostoru podle bm25 (`query` je výraz FTS5), nejvýš `limit`, bez `exclude`
        a bez vstupů novějších než `until`."""
        rows = self.db.execute(
            "SELECT f.entry_id FROM intake_entries_fts f JOIN intake_entries e ON e.id = f.entry_id"
            " WHERE intake_entries_fts MATCH ? AND f.workspace_id=? AND f.entry_id<>? AND e.created_at<=?"
            " ORDER BY bm25(intake_entries_fts), e.created_at DESC LIMIT ?",
            (query, workspace, exclude, until, limit)).fetchall()
        return [row[0] for row in rows]

    def recent(self, workspace, limit, verdicts=None):
        """Posledních `limit` vstupů prostoru od nejnovějšího; `verdicts` zúží stanoviska."""
        condition, parameters = "workspace_id=?", [workspace]
        if verdicts:
            condition += f" AND verdict IN ({','.join('?' for _ in verdicts)})"
            parameters += list(verdicts)
        rows = self.db.execute(SELECT + f" WHERE {condition} ORDER BY created_at DESC, rowid DESC LIMIT ?",
                               (*parameters, limit)).fetchall()
        return [public(row) for row in rows]

    def counts(self, workspace):
        """`{stanovisko: počet}` vstupů prostoru."""
        return dict(self.db.execute("SELECT verdict, COUNT(*) FROM intake_entries WHERE workspace_id=?"
                                    " GROUP BY verdict", (workspace,)).fetchall())
