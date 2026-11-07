"""Merge log služby (docs/navrhy/2026-11-06-linie-rebrand.md §5a): `<data>/projects/<p>/linie/merge_log.json`.

Záznam `{op, started, finished}`: `started {op, ticket, repo, source_sha, target, target_sha_before, mode, by, at}` se
zapíše před gitem, `finished {op, result_sha, ok, at}` po ověření výsledku v gitu. `axis` z něj čte osu `integration`:
dokončený `ok` = `merged`, `started` bez `finished` = `unconfirmed` („operace zahájena, výsledek neověřen“). Záznam se
nikdy nedopočítává z historie gitu.
"""
from pathlib import Path

from backend.agi_pletor.linie import jsonfile


def _path(data_root, project):
    return Path(data_root) / "projects" / project / "linie" / "merge_log.json"


def read(data_root, project):
    found = jsonfile.read(_path(data_root, project), [])
    return [e for e in found if isinstance(e, dict) and e.get("op")] if isinstance(found, list) else []


def find(entries, op=None, source=None, target=None):
    """Záznam se stejným `op`; bez `op` poslední pro dvojici `source → target`, který je hotový `ok` nebo neověřený
    (neúspěšný pokus nový merge nebrzdí)."""
    if op:
        return next((e for e in entries if e["op"] == op), None)
    pair = [e for e in entries if (e["started"]["source_sha"], e["started"]["target"]) == (source, target)
            and (e.get("finished") is None or e["finished"].get("ok"))]
    return pair[-1] if pair else None


def start(data_root, project, started):
    entry = {"op": started["op"], "started": started, "finished": None}
    jsonfile.update(_path(data_root, project), [], lambda entries: [*entries, entry])
    return entry


def finish(data_root, project, op, result_sha, ok, at):
    done = {"op": op, "result_sha": result_sha, "ok": ok, "at": at}
    jsonfile.update(_path(data_root, project), [],
                    lambda entries: [{**e, "finished": done} if e.get("op") == op else e for e in entries])
    return done


def axis(entries, ticket_id):
    """Osa `integration` úkolu z logu, nebo None (log o úkolu nic neví – to samo nic nedokazuje)."""
    mine = [e for e in entries if e["started"].get("ticket") == ticket_id]
    done = [e for e in mine if (e.get("finished") or {}).get("ok")]
    entry = done[-1] if done else (mine[-1] if mine and mine[-1].get("finished") is None else None)
    if entry is None:
        return None
    started, finished = entry["started"], entry.get("finished")
    return {"state": "merged" if finished else "unconfirmed", "target": started["target"],
            "sha": (finished or {}).get("result_sha"), "at": (finished or started)["at"], "mode": started.get("mode"),
            "op": entry["op"], "src": "merge log"}
