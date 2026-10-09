"""Activity metadata belongs to the same transaction as the claim or accepted output."""

import json

from backend.project.workspace.workspace_sources import relative_path


def validate_touched(value):
    if not isinstance(value, list) or len(value) > 500:
        raise ValueError("touched musí být seznam nejvýše 500 relativních cest z git diff.")
    seen = set()
    for path in value:
        relative_path(path)
        if not path or path in seen:
            raise ValueError("touched vyžaduje neprázdné jedinečné relativní cesty.")
        seen.add(path)


def record_activity(db, project, workspace, node_id, agent, stamp, *, claimed=False, touched=None):
    old = db.execute("SELECT started_at,touched FROM card_work_activity WHERE project_id=? AND workspace_id=? AND node_id=?",
                     (project, workspace, node_id)).fetchone()
    started = stamp if claimed else old["started_at"] if old else None
    paths = json.dumps(touched, ensure_ascii=False) if touched is not None else None if claimed or old is None else old["touched"]
    db.execute("INSERT OR REPLACE INTO card_work_activity VALUES(?,?,?,?,?,?,?)",
               (project, workspace, node_id, agent, started, stamp, paths))
