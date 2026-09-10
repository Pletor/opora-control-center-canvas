"""Kontrolovaný SQLite snapshot + porovnání před/po deploy, bez obsahu do logu."""
import hashlib
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
PRIMARY = ROOT.parent.parent
DB = PRIMARY / ".data/production/canvas.sqlite"
EVIDENCE = ROOT / ".opora/workunits/WU-CANVAS-COMPLETION"


def visible_project_ids(db):
    """Stejný filtr jako bootstrap; archivované řádky zůstávají v plné záloze."""
    return sorted(row[0] for row in db.execute(
        "SELECT id FROM projects WHERE id NOT IN (SELECT project_id FROM archived_projects)"
    ))


def snapshot(db):
    result = {}
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise ValueError("Unexpected table identifier")
        rows = db.execute(f'SELECT * FROM "{name}"').fetchall()
        data = sorted(json.dumps(row, sort_keys=True, ensure_ascii=True) for row in rows)
        result[name] = {"rows": len(rows), "sha256": hashlib.sha256("\n".join(data).encode()).hexdigest()}
    return result


if __name__ == "__main__":
    if not DB.is_file():
        raise FileNotFoundError("Expected production DB missing; never create an empty replacement")
    with urlopen("http://127.0.0.1:8740/api/bootstrap", timeout=10) as response:
        projects = sorted(p["id"] for p in json.load(response)["projects"])
    with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True) as source:
        ids = sorted(row[0] for row in source.execute("SELECT id FROM projects"))
        visible_ids = visible_project_ids(source)
        assert visible_ids == projects, "Live projects do not match visible production projects"
        tables = snapshot(source)
        if sys.argv[1] == "backup":
            backup = DB.parent.parent / "backups" / ("canvas-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".sqlite")
            backup.parent.mkdir(exist_ok=True)
            with sqlite3.connect(backup) as destination:
                source.backup(destination)
                assert destination.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            record = {"database": str(DB), "backup": str(backup), "projects": ids, "visibleProjects": visible_ids, "tables": tables}
            (EVIDENCE / "production-before.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        elif sys.argv[1] == "verify":
            before = json.loads((EVIDENCE / "production-before.json").read_text(encoding="utf-8"))
            unchanged = all(tables.get(name) == value for name, value in before["tables"].items())
            assert unchanged and before["projects"] == ids, "Original production tables changed"
            assert before.get("visibleProjects", before["projects"]) == visible_ids, "Visible production projects changed"
            record = {"database": str(DB), "projects": ids, "visibleProjects": visible_ids, "originalTablesUnchanged": unchanged, "tables": tables}
            (EVIDENCE / "production-after.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        else:
            raise ValueError("Use backup or verify")
    print(json.dumps({"database": str(DB), "projectIds": ids, "tableCount": len(tables), "mode": sys.argv[1]}))
