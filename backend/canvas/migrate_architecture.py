"""Migrace architektury z grafů prostorů do `project_architecture` (`docs/domeny-a-worktree.md` §5).

Zdroje: lokální/prázdný projekt `drafts.graph`; Git projekt `HEAD:opora-canvas.json` (jen čtením)
a graf každého pracovního prostoru přes stejné čtení jako běžný pohled (data plátna, jinak starý
`opora-canvas.json` v kořeni worktree). Výběr je `split` z B1: uzly se `site`, jejich předkové a
hrany mezi nimi; ID zůstávají.

Nic se neslučuje. Projekt se přeskočí a vrátí `conflicts[]`, když má stejné ID v různých zdrojích
jiný obsah, když je uzel jinde obsahem, když stejný host patří různým ID, nebo když se poslední
revize zadání či textu uzlu mezi prostory liší.

Fáze (stav v tabulce `architecture_migrations`): backup → architecture (revize 1) → docs (kopie
`node_spec_revisions` a `node_text_revisions` i s historií pod `wid = "architecture"`) → strip
(uzly architektury pryč z grafů prostorů) → done. Opakované spuštění pokračuje od poslední
nedokončené fáze; hotová migrace nedělá nic. Existuje-li architektura, kterou nezaložila tato
migrace, nedělá nic také. `dry_run` jen vrátí report. Návrat: `migrate_architecture_backup.down`.

Ruční spuštění: `uv run python -m backend.canvas.migrate_architecture --data <kořen dat> --project <id>`
(bez `--apply` jen report; `--down <záloha>` vrátí stav).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from backend.canvas.architecture_graph import EMPTY_REMOVED, check_shape, compose, split
from backend.canvas.graph import encode, payload_project, validate_graph
from backend.canvas.migrate_architecture_backup import down as restore_backup
from backend.canvas.migrate_architecture_backup import new_backup_id, now, seal, take_backup
from backend.canvas.project_architecture import ARCHITECTURE_WID
from backend.canvas.site_metadata import host_key
from backend.canvas.workspace_graph import read_graph_file, write_workspace_graph
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority

ACTOR = "system"
LABEL = "migrace"
PHASES = ("backup", "architecture", "docs", "strip", "done")
DOCS = (("spec", "node_spec_revisions", "fields"), ("text", "node_text_revisions", "text"))
PUBLIC = ("project", "phase", "dryRun", "message", "moved", "conflicts", "docs", "strip", "sources", "backup")


def _local(service, pid):
    return pid == "draft" or service.project_hub.source_info(service.row("projects", pid))["sourceKind"] != "git"


def read_sources(service, pid):
    """[{workspace, origin, graph | error}] v pořadí: draft, nebo main a pak prostory podle ID."""
    if _local(service, pid):
        return [{"workspace": "draft", "origin": "draft", "graph": service._draft_graph(pid)[0]}]
    items = []
    for wid in ["main", *(row["id"] for row in service.workspaces(pid))]:
        try:
            location, _project = service.location(pid, wid)
            raw, origin = service._git_content_raw(pid, wid, location)
            graph = check_shape(json.loads(raw)) if raw else None
            items.append({"workspace": wid, "origin": origin, "graph": graph})
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            items.append({"workspace": wid, "origin": None, "graph": None, "error": str(error)})
    return items


def _same(left, right):
    def norm(item):
        return {**item, "x": round(item["x"]), "y": round(item["y"])} if "x" in item and "y" in item else item

    return norm(left) == norm(right)


def _conflict(reason, item_id, sources, message):
    return {"id": item_id, "reason": reason, "sources": sources, "message": message}


def _collect(sources, conflicts):
    """Sjednocení architektury ze všech zdrojů: {typ: {id: {item, sources}}} a konflikty obsahu."""
    found = {"nodes": {}, "edges": {}}
    for source in sources:
        arch, _content = split(source["graph"])
        for key in ("nodes", "edges"):
            for item in arch[key]:
                entry = found[key].setdefault(item["id"], {"item": item, "sources": []})
                if not _same(entry["item"], item):
                    first = entry["sources"][0]["workspace"]
                    conflicts.append(_conflict("content", item["id"], [first, source["workspace"]],
                                               f"{'Uzel' if key == 'nodes' else 'Vazba'} {item['id']} má v prostorech "
                                               f"{first} a {source['workspace']} rozdílný obsah."))
                entry["sources"].append({"workspace": source["workspace"], "origin": source["origin"]})
    for source in sources:
        _arch, content = split(source["graph"])
        for key in ("nodes", "edges"):
            for item in content[key]:
                entry = found[key].get(item["id"])
                if entry is not None:
                    conflicts.append(_conflict("kind", item["id"], [entry["sources"][0]["workspace"], source["workspace"]],
                                               f"{item['id']} je v prostoru {entry['sources'][0]['workspace']} architekturou, "
                                               f"v prostoru {source['workspace']} obsahem."))
    hosts = {}
    for source in sources:
        for node in split(source["graph"])[0]["nodes"]:
            for environment in (node.get("site") or {}).get("environments") or []:
                try:
                    key = host_key(environment.get("host"))
                except (ValueError, AttributeError):
                    continue
                hosts.setdefault(key, {})[node["id"]] = source["workspace"]
    for key, owners in hosts.items():
        if len(owners) > 1:
            host = key[0] if key[1] is None else f"{key[0]}:{key[1]}"
            conflicts.append(_conflict("host", host, sorted(set(owners.values())),
                                       f"Host {host} mají v různých prostorech různé uzly ({', '.join(sorted(owners))})."))
    return found


def _strip(graph, moved):
    return {"nodes": [n for n in graph["nodes"] if n["id"] not in moved["nodes"]],
            "edges": [e for e in graph["edges"] if e["id"] not in moved["edges"]]}


def _strip_action(source):
    if source["origin"] in ("draft", "data", "sqlite"):
        return "stripped"
    if source["origin"] == "git":
        return "read-only"  # HEAD se nemění; kopie skryje složený pohled
    return "legacy"  # opora-canvas.json ve worktree se nepíše; kopie skryje složený pohled


def _doc_rows(db, table, column, scope):
    return db.execute(f"SELECT revision,{column},saved_at FROM {table} WHERE project_id=? AND workspace_id=? "
                      "AND node_id=? ORDER BY revision", scope).fetchall()


def _latest(kind, rows):
    return json.loads(rows[-1][1]) if kind == "spec" else rows[-1][1]


def _docs(service, pid, sources, node_ids, conflicts):
    """Plán kopie zadání a textu: od každého uzlu jeden zdroj, shodné kopie jen jako původ."""
    wids = [source["workspace"] for source in sources]
    plan = []
    with service.reading(pid):
        db = service.db_for(pid)
        for kind, table, column in DOCS:
            noun = "Zadání" if kind == "spec" else "Text"
            for node_id in node_ids:
                copies = [(wid, rows) for wid in wids if (rows := _doc_rows(db, table, column, (pid, wid, node_id)))]
                if not copies:
                    continue
                chosen, history = copies[0]
                differ = [wid for wid, rows in copies[1:] if _latest(kind, rows) != _latest(kind, history)]
                if differ:
                    conflicts.append(_conflict(kind, node_id, [chosen, *differ],
                                               f"{noun} uzlu {node_id} se liší mezi prostory {', '.join([chosen, *differ])}."))
                    continue
                existing = _doc_rows(db, table, column, (pid, ARCHITECTURE_WID, node_id))
                if existing and _latest(kind, existing) != _latest(kind, history):
                    conflicts.append(_conflict(kind, node_id, [ARCHITECTURE_WID, chosen],
                                               f"{noun} uzlu {node_id} už pod architekturou existuje a je jiné."))
                    continue
                plan.append({"nodeId": node_id, "kind": kind, "from": chosen, "revisions": len(history),
                             "identicalIn": [wid for wid, _rows in copies[1:]],
                             **({"skipped": "already"} if existing else {})})
    return plan


def plan(service, pid):
    """Report migrace bez zápisu: co se přesune, odkud, kopie dokumentů, konflikty."""
    all_sources = read_sources(service, pid)
    conflicts = [_conflict("unreadable", source["workspace"], [source["workspace"]],
                           f"Graf prostoru {source['workspace']} nejde přečíst: {source['error']}")
                 for source in all_sources if "error" in source]
    sources = [source for source in all_sources if source["graph"] is not None]
    found = _collect(sources, conflicts)
    architecture = {key: [entry["item"] for entry in found[key].values()] for key in ("nodes", "edges")}
    moved_ids = {key: set(found[key]) for key in ("nodes", "edges")}
    moved = [{"id": item_id, "type": key[:-1], "name": str(entry["item"].get("name", "")), "sources": entry["sources"]}
             for key in ("nodes", "edges") for item_id, entry in found[key].items()]
    strip = [{"workspace": source["workspace"], "origin": source["origin"], "action": _strip_action(source),
              "nodes": len(split(source["graph"])[0]["nodes"])}
             for source in sources if split(source["graph"])[0]["nodes"]]
    if moved and not conflicts:
        try:
            validate_graph(architecture)
            for source in sources:
                legacy = source["origin"] in ("git", "legacy")
                validate_graph(compose(architecture, EMPTY_REMOVED, _strip(source["graph"], moved_ids), legacy=legacy)[0])
        except ValueError as error:
            conflicts.append(_conflict("invalid", "", [], f"Graf po migraci by nebyl platný: {error}"))
    docs = _docs(service, pid, all_sources, list(found["nodes"]), conflicts) if moved else []
    return {
        "project": pid, "moved": moved, "conflicts": conflicts, "docs": docs, "strip": strip,
        "sources": [{"workspace": s["workspace"], "origin": s["origin"],
                     "nodes": len(split(s["graph"])[0]["nodes"]) if s["graph"] else 0} for s in all_sources],
        "backup": None, "architecture": architecture,
    }


def _state(service, pid):
    with service.reading(pid):
        row = service.db_for(pid).execute(
            "SELECT phase,backup_id,report FROM architecture_migrations WHERE project_id=?", (pid,)
        ).fetchone()
    return None if row is None else {"phase": row[0], "backup": row[1], "report": json.loads(row[2])}


def _set_phase(db, pid, phase, report):
    db.execute("UPDATE architecture_migrations SET phase=?,report=?,finished_at=? WHERE project_id=?",
               (phase, encode(report), now() if phase == "done" else None, pid))


def _write_architecture(service, pid, report):
    with service.lock_for(pid):
        db = service.db_for(pid)
        with db:
            service.architecture.write(db, pid, report["architecture"], 0, ACTOR, LABEL)
            _set_phase(db, pid, "architecture", report)


def _copy_docs(service, pid, report):
    with service.lock_for(pid):
        db = service.db_for(pid)
        with db:
            for entry in report["docs"]:
                table, column = {kind: (table, column) for kind, table, column in DOCS}[entry["kind"]]
                if entry.get("skipped"):
                    continue
                scope = (pid, ARCHITECTURE_WID, entry["nodeId"])
                if db.execute(f"SELECT 1 FROM {table} WHERE project_id=? AND workspace_id=? AND node_id=?", scope).fetchone():
                    entry["skipped"] = "already"  # mezitím vzniklo pod architekturou (pokračování po pádu)
                    continue
                db.execute(f"INSERT INTO {table}(project_id,workspace_id,node_id,revision,{column},saved_at) "
                           f"SELECT project_id,?,node_id,revision,{column},saved_at FROM {table} "
                           "WHERE project_id=? AND workspace_id=? AND node_id=?",
                           (ARCHITECTURE_WID, pid, entry["from"], entry["nodeId"]))
            _set_phase(db, pid, "docs", report)


def _strip_workspaces(service, pid, report):
    moved = {key: {item["id"] for item in report["moved"] if item["type"] == key[:-1]} for key in ("nodes", "edges")}
    targets = {item["workspace"] for item in report["strip"] if item["action"] == "stripped"}
    with service.lock_for(pid):
        db = service.db_for(pid)
        with db:
            db.execute("BEGIN IMMEDIATE")
            if "draft" in targets:
                graph = json.loads(db.execute("SELECT graph FROM drafts WHERE id=?", (pid,)).fetchone()[0])
                db.execute("UPDATE drafts SET graph=? WHERE id=?", (encode(_strip(graph, moved)), pid))
            for wid in sorted(targets - {"draft"}):
                authority = WorkspaceGraphAuthority(db, pid, wid)
                stored = authority.read()
                if stored is not None:
                    authority.write(_strip(stored["graph"], moved), stored["revision"])
                    continue
                path = service.graph_file(pid, wid)
                raw = read_graph_file(path)
                if raw is None:
                    continue
                stripped = encode(_strip(json.loads(raw), moved))
                if stripped != raw:
                    write_workspace_graph(path, stripped)
            _set_phase(db, pid, "strip", report)


def _finish(service, pid, report):
    seal(service, pid, report["backup"])
    with service.lock_for(pid):
        db = service.db_for(pid)
        with db:
            _set_phase(db, pid, "done", report)


STEPS = {"architecture": _write_architecture, "docs": _copy_docs, "strip": _strip_workspaces, "done": _finish}


def _public(report, phase, dry_run, message):
    return {**{key: report.get(key) for key in PUBLIC}, "phase": phase, "dryRun": dry_run, "message": message}


def migrate(service, project, dry_run=True):
    """Report (dry_run) nebo provedení migrace architektury jednoho projektu; vrací {moved, conflicts, backup, phase, …}."""
    pid = payload_project({"project": project})
    with service.graph_lock_for(pid):
        state = _state(service, pid)
        if state is not None and state["phase"] == "done":
            return _public(state["report"], "done", dry_run, "Migrace architektury už proběhla; nic se nemění.")
        if state is None:
            revision = service.architecture.read(pid)["revision"]
            if revision >= 1:
                return _public({"project": pid, "moved": [], "conflicts": []}, "skipped", dry_run,
                               f"Architektura projektu už existuje (revize {revision}) a nezaložila ji migrace; nic se nemění.")
            report = plan(service, pid)
            if report["conflicts"]:
                return _public(report, "conflicts", dry_run, "Projekt se přeskočil: zdroje se neshodují, nic se neslučuje.")
            if not report["moved"]:
                return _public(report, "empty", dry_run, "Grafy prostorů nemají žádné domény ani stránky; není co migrovat.")
            if dry_run:
                return _public(report, "dry-run", True, "Náhled migrace; nic se nezapsalo.")
            report["backup"] = new_backup_id()
            git_workspaces = [s["workspace"] for s in report["sources"] if s["workspace"] not in ("main", "draft")]
            take_backup(service, pid, git_workspaces, report["backup"])
            with service.lock_for(pid):
                db = service.db_for(pid)
                with db:
                    db.execute("INSERT INTO architecture_migrations VALUES(?,?,?,?,?,?)",
                               (pid, "backup", report["backup"], now(), None, encode(report)))
            phase = "backup"
        else:
            report, phase = state["report"], state["phase"]
            if dry_run:
                return _public(report, phase, True, f"Migrace stojí po fázi {phase}; spuštění bez dryRun ji dokončí.")
        for step in PHASES[PHASES.index(phase) + 1:]:
            STEPS[step](service, pid, report)
        return _public(report, "done", False, "Architektura je převedená; záloha: " + report["backup"] + ".")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrace architektury projektu (docs/domeny-a-worktree.md §5).")
    parser.add_argument("--data", required=True, help="kořen dat aplikace (složka s registry.sqlite)")
    parser.add_argument("--project", required=True)
    parser.add_argument("--apply", action="store_true", help="provést migraci (bez něj jen report)")
    parser.add_argument("--down", metavar="BACKUP", help="vrátit projekt ze zálohy migrace")
    parser.add_argument("--force", action="store_true", help="s --down: vrátit i přes pozdější změny")
    args = parser.parse_args(argv)
    from backend.canvas.canvas_service import CanvasService

    service = CanvasService(Path(args.data))
    try:
        result = (restore_backup(service, args.project, args.down, force=args.force) if args.down
                  else migrate(service, args.project, dry_run=not args.apply))
    finally:
        service.close()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
