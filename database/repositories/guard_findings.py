"""Přístup k tabulce `guard_findings` (nálezy strážců, `docs/strazci.md` §3); transakci vlastní volající."""
import json

COLUMNS = "key,guard,rule,severity,message,node_id,payload,first_seen,last_seen,resolved_at"
SEVERITY_ORDER = "CASE severity WHEN 'block' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END"


def _row(row):
    value = dict(zip(COLUMNS.split(","), row))
    payload = json.loads(value.pop("payload") or "{}")
    return {"key": value["key"], "guard": value["guard"], "rule": value["rule"], "severity": value["severity"],
            "message": value["message"], "nodeId": value["node_id"], **payload,
            "firstSeen": value["first_seen"], "lastSeen": value["last_seen"], "resolvedAt": value["resolved_at"]}


class GuardFindings:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def open_keys(self, guard):
        """{key} otevřených nálezů jednoho strážce."""
        rows = self.db.execute("SELECT key FROM guard_findings WHERE project_id=? AND guard=? AND resolved_at IS NULL",
                               (self.project, guard)).fetchall()
        return {row[0] for row in rows}

    def has_any(self, guard):
        """Má strážce v projektu aspoň jeden záznam (otevřený i vyřešený)? Ne = první běh."""
        return self.db.execute("SELECT 1 FROM guard_findings WHERE project_id=? AND guard=? LIMIT 1",
                               (self.project, guard)).fetchone() is not None

    def upsert_new(self, finding, payload, at):
        """Nový nález, nebo znovu otevřený dřív vyřešený (stejný `key`): `first_seen` začíná znovu."""
        self.db.execute(
            "INSERT INTO guard_findings(key,project_id,guard,rule,severity,message,node_id,payload,first_seen,last_seen,"
            "resolved_at) VALUES(?,?,?,?,?,?,?,?,?,?,NULL) ON CONFLICT(key) DO UPDATE SET project_id=excluded.project_id,"
            " guard=excluded.guard, rule=excluded.rule, severity=excluded.severity, message=excluded.message,"
            " node_id=excluded.node_id, payload=excluded.payload, first_seen=excluded.first_seen,"
            " last_seen=excluded.last_seen, resolved_at=NULL",
            (finding["key"], self.project, finding["guard"], finding["rule"], finding["severity"], finding["message"],
             finding.get("nodeId"), json.dumps(payload, ensure_ascii=False, sort_keys=True), at, at))

    def touch(self, finding, payload, at):
        """Trvající nález: `last_seen` a aktuální znění; událost se nevydává."""
        self.db.execute("UPDATE guard_findings SET last_seen=?, severity=?, message=?, node_id=?, payload=?"
                        " WHERE project_id=? AND key=?",
                        (at, finding["severity"], finding["message"], finding.get("nodeId"),
                         json.dumps(payload, ensure_ascii=False, sort_keys=True), self.project, finding["key"]))

    def resolve(self, key, at):
        self.db.execute("UPDATE guard_findings SET resolved_at=? WHERE project_id=? AND key=? AND resolved_at IS NULL",
                        (at, self.project, key))

    def prune(self, cutoff):
        """Smaže vyřešené nálezy vyřešené před `cutoff` (ISO text)."""
        self.db.execute("DELETE FROM guard_findings WHERE project_id=? AND resolved_at IS NOT NULL AND resolved_at<?",
                        (self.project, cutoff))

    def counts(self):
        """{guard: {severity: počet}} otevřených nálezů."""
        rows = self.db.execute("SELECT guard,severity,COUNT(*) FROM guard_findings WHERE project_id=?"
                               " AND resolved_at IS NULL GROUP BY guard,severity", (self.project,)).fetchall()
        result = {}
        for guard, severity, count in rows:
            result.setdefault(guard, {})[severity] = count
        return result

    def list(self, *, node=None, open_only=True, limit=500):
        """Nálezy projektu: block první, pak warn a info, uvnitř podle `last_seen` od nejnovějšího."""
        condition, parameters = "project_id=?", [self.project]
        if node is not None:
            condition, parameters = condition + " AND node_id=?", [*parameters, node]
        if open_only:
            condition += " AND resolved_at IS NULL"
        rows = self.db.execute(f"SELECT {COLUMNS} FROM guard_findings WHERE {condition}"
                               f" ORDER BY resolved_at IS NOT NULL, {SEVERITY_ORDER}, last_seen DESC, key LIMIT ?",
                               (*parameters, limit)).fetchall()
        return [_row(row) for row in rows]
