"""Řádky `intake_entries` a `intake_entries_fts` (vstupní brána, docs/navrhy/2026-10-30-vstupni-brana.md §5).

Věta vstupu je neměnná: text, otisk, zdroj a čas se po vložení (spolu s řádkem FTS5) nemění. Měnit se smí jen
stanovisko (`verdict`, `layer`, `area_id`, `confidence`, `reason`, `jev_calls`): zapíše ho Jev (řez 2,
`backend/brain_opora/decision/intake.py`) nebo srdce (`backend/brain_opora/determinism/intake.py`, `confirm`).
Srdce smí vstup navázat na požadavek (`set_requirement`, docs/navrhy/2026-10-30-metriky-a-spoustece.md §5).
Transakci vlastní volající."""

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

    def recent(self, workspace, limit, verdicts=None, layers=None):
        """Posledních `limit` vstupů prostoru od nejnovějšího; `verdicts` zúží stanoviska, `layers` vrstvy."""
        condition, parameters = "workspace_id=?", [workspace]
        for column, values in (("verdict", verdicts), ("layer", layers)):
            if values:
                condition += f" AND {column} IN ({','.join('?' for _ in values)})"
                parameters += list(values)
        rows = self.db.execute(SELECT + f" WHERE {condition} ORDER BY created_at DESC, rowid DESC LIMIT ?",
                               (*parameters, limit)).fetchall()
        return [public(row) for row in rows]

    def counts(self, workspace):
        """`{stanovisko: počet}` vstupů prostoru."""
        return dict(self.db.execute("SELECT verdict, COUNT(*) FROM intake_entries WHERE workspace_id=?"
                                    " GROUP BY verdict", (workspace,)).fetchall())

    def unclassified(self, workspace, limit, since, first=()):
        """Vstupy prostoru `pending` zapsané od `since` (ISO), na které se Jev ještě neptal (`jev_calls` 0) a které srdce
        nerozhodlo; nejdřív ID z `first` (vstupy dávky) v jejich pořadí, pak nejnovější. Nejvýš `limit`."""
        rows = [public(row) for row in self.db.execute(
            SELECT + " WHERE workspace_id=? AND verdict='pending' AND layer<>'heart' AND jev_calls=0 AND created_at>=?"
            " ORDER BY created_at DESC, rowid DESC", (workspace, since)).fetchall()]
        rank = {entry_id: position for position, entry_id in enumerate(first)}
        rows.sort(key=lambda row: rank.get(row["id"], len(rank)))
        return rows[:max(limit, 0)]

    def jev_calls_on(self, day):
        """Součet volání Jevu u vstupů projektu zapsaných v UTC den `day` (`YYYY-MM-DD`)."""
        return int(self.db.execute("SELECT COALESCE(SUM(jev_calls), 0) FROM intake_entries"
                                   " WHERE substr(created_at,1,10)=?", (day,)).fetchone()[0])

    def set_verdict(self, entry_id, *, verdict, layer, reason, area_id=None, confidence=None, jev_calls=None,
                    only_pending=False):
        """Zapíše stanovisko vstupu; `jev_calls` None = beze změny, `only_pending` = jen vstup `pending`, který srdce
        ještě nerozhodlo (Jev nepřepíše srdce, které mezitím rozhodlo). Vrací True, když se řádek změnil."""
        condition = " AND verdict='pending' AND layer<>'heart'" if only_pending else ""
        cursor = self.db.execute(
            "UPDATE intake_entries SET verdict=?, layer=?, reason=?, area_id=COALESCE(?, area_id), confidence=?,"
            " jev_calls=COALESCE(?, jev_calls) WHERE id=?" + condition,
            (verdict, layer, reason, area_id, confidence, jev_calls, entry_id))
        return cursor.rowcount == 1

    def set_requirement(self, entry_id, requirement_id, milestone_id=None):
        """Naváže vstup na požadavek (a na milník; None = beze změny). True, když se řádek změnil."""
        cursor = self.db.execute("UPDATE intake_entries SET requirement_id=?, milestone_id=COALESCE(?, milestone_id)"
                                 " WHERE id=?", (requirement_id, milestone_id, entry_id))
        return cursor.rowcount == 1
