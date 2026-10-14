"""Úložiště architektury projektu (`docs/domeny-a-worktree.md` §4): jedna pro projekt, nad všemi worktree.

Tabulky `project_architecture` (aktuální stav) a `project_architecture_revisions` (historie, jen
přibývá) v `project.sqlite`. Revize nese aktéra a prostor, odkud změna přišla. `removed` drží ID
uzlů a hran, které architektura kdysi vlastnila a pak smazala: složený pohled je skryje i ve staré
kopii grafu (Git HEAD, převzatý `opora-canvas.json`), takže se smazaná doména nevrátí.

Zápis z plátna jde přes `CanvasService.save_graph` (rozdělí složený graf); přímý zápis (`save`) a
návrat k revizi (`restore`) jdou tudy. Před každým odebráním uzlu architektury se ověří, že na něj
neodkazuje obsah žádného prostoru projektu ani `workspaces.node_id`.
"""

import json
from datetime import UTC, datetime

from backend.canvas.architecture_graph import EMPTY_REMOVED, compose, ids, split
from backend.canvas.graph import EMPTY, digest, encode, payload_project, valid_id, validate_graph

# Rezervovaný prostor pro zadání a text uzlů architektury (platí z mainu i z každého worktree).
ARCHITECTURE_WID = "architecture"
CONFLICT = "Architektura se změnila v jiném okně. Obnovte ji."
SAVE_KEYS = {"project", "workspace", "expectedRevision", "graph"}
RESTORE_KEYS = {"project", "revision", "digest"}
HISTORY_LIMIT = 50


def next_removed(old_graph, old_removed, new_graph, kept=(frozenset(), frozenset())):
    """Smazaná ID po zápisu: dřívější + nově zmizelá − znovu přidaná. `kept` = ID, která se jen
    přesunula do obsahu (uzel ztratil `site`); ta smazaná nejsou."""
    old_nodes, old_edges = ids(old_graph)
    new_nodes, new_edges = ids(new_graph)
    return {
        "nodes": sorted((set(old_removed["nodes"]) | (old_nodes - new_nodes - set(kept[0]))) - new_nodes),
        "edges": sorted((set(old_removed["edges"]) | (old_edges - new_edges - set(kept[1]))) - new_edges),
    }


def blocked_message(hits):
    names = ", ".join(f"{hit['label']} ({hit['reason']})" for hit in hits[:10])
    return "Uzel architektury nejde odebrat, odkazují na něj pracovní prostory: " + names + "."


def _actor(actor):
    return actor[:120] if isinstance(actor, str) and actor.strip() else "system"


class ProjectArchitecture:
    def __init__(self, canvas):
        self.canvas = canvas

    def read(self, pid):
        """{graph, revision, digest, removed}; bez záznamu prázdná architektura s revizí 0.

        Hodnota je sdílená z cache čtení (razítko = token dat projektu, jinak shodný surový řádek)."""
        canvas = self.canvas
        with canvas.reading(pid):
            key = ("architecture", pid)
            token = canvas.data_token(pid)
            hit = canvas.read_cache.get(key, token)
            if hit is not None:
                return hit
            row = canvas.db_for(pid).execute(
                "SELECT revision,graph,removed FROM project_architecture WHERE project_id=?", (pid,)
            ).fetchone()
            raw = [row[0], row[1], row[2]] if row else [0, encode(EMPTY), encode(EMPTY_REMOVED)]
            _stamp, previous = canvas.read_cache.peek(key)
            if previous is not None and previous["raw"] == raw:
                hit = previous
            else:
                graph = json.loads(raw[1])
                hit = {"raw": raw, "revision": raw[0], "graph": graph, "digest": digest(graph),
                       "removed": json.loads(raw[2])}
            return canvas.read_cache.put(key, token, hit)

    def public(self, pid):
        current = self.read(pid)
        return {"graph": current["graph"], "revision": current["revision"], "digest": current["digest"]}

    def node_ids(self, pid):
        return ids(self.read(pid)["graph"])[0]

    def write(self, db, pid, graph, expected_revision, actor, workspace, kept=(frozenset(), frozenset())):
        """Zapíše novou revizi do otevřené transakce `db` (volající drží `lock_for` a potvrzuje)."""
        row = db.execute(
            "SELECT revision,graph,removed FROM project_architecture WHERE project_id=?", (pid,)
        ).fetchone()
        revision = row[0] if row else 0
        if revision != expected_revision:
            raise ValueError(CONFLICT)
        old_graph = json.loads(row[1]) if row else EMPTY
        old_removed = json.loads(row[2]) if row else EMPTY_REMOVED
        removed = next_removed(old_graph, old_removed, graph, kept)
        saved_at = datetime.now(UTC).isoformat()
        actor = _actor(actor)
        db.execute(
            "INSERT OR REPLACE INTO project_architecture VALUES(?,?,?,?,?,?)",
            (pid, revision + 1, encode(graph), saved_at, actor, encode(removed)),
        )
        db.execute(
            "INSERT INTO project_architecture_revisions VALUES(?,?,?,?,?,?)",
            (pid, revision + 1, encode(graph), actor, str(workspace or ""), saved_at),
        )
        return revision + 1

    def history(self, pid, limit=HISTORY_LIMIT):
        with self.canvas.reading(pid):
            rows = self.canvas.db_for(pid).execute(
                "SELECT revision,actor,workspace,created_at FROM project_architecture_revisions"
                " WHERE project_id=? ORDER BY revision DESC LIMIT ?",
                (pid, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def graph_at(self, pid, revision):
        with self.canvas.reading(pid):
            row = self.canvas.db_for(pid).execute(
                "SELECT graph FROM project_architecture_revisions WHERE project_id=? AND revision=?",
                (pid, revision),
            ).fetchone()
        if row is None:
            raise ValueError("Revize architektury neexistuje.")
        return json.loads(row[0])

    def save(self, payload, actor="system"):
        """Přímý zápis architektury (`POST /api/project-architecture`) s revizí jako podmínkou."""
        if not isinstance(payload, dict) or not SAVE_KEYS <= set(payload) <= SAVE_KEYS | {"actor"}:
            raise ValueError("Neplatný formát zápisu architektury (project, workspace, expectedRevision, graph).")
        pid = payload_project(payload)
        wid, expected = payload["workspace"], payload["expectedRevision"]
        if not isinstance(wid, str) or not (wid in ("main", "draft") or valid_id(wid)):
            raise ValueError("Neplatný pracovní prostor.")
        if type(expected) is not int or expected < 0:
            raise ValueError("Neplatná očekávaná revize architektury.")
        return self._replace(pid, wid, payload["graph"], expected, actor, wid)

    def restore(self, payload, actor="system"):
        """Návrat architektury k revizi (`POST /api/project-architecture/restore`) jako nová revize."""
        if not isinstance(payload, dict) or not RESTORE_KEYS <= set(payload) <= RESTORE_KEYS | {"workspace"}:
            raise ValueError("Neplatný formát obnovy architektury (project, revision, digest).")
        pid = payload_project(payload)
        revision, wid = payload["revision"], payload.get("workspace")
        if type(revision) is not int or revision < 1:
            raise ValueError("Neplatná revize architektury.")
        if wid is not None and (not isinstance(wid, str) or not (wid in ("main", "draft") or valid_id(wid))):
            raise ValueError("Neplatný pracovní prostor.")
        with self.canvas.graph_lock_for(pid):
            current = self.read(pid)
            if payload["digest"] != current["digest"]:
                raise ValueError(CONFLICT)
            graph = self.graph_at(pid, revision)
            return self._replace(pid, wid, graph, current["revision"], actor, wid or f"restore:{revision}")

    def _replace(self, pid, wid, graph, expected, actor, label):
        canvas = self.canvas
        validate_graph(graph)
        arch, content = split(graph)
        if content["nodes"] or content["edges"]:
            raise ValueError("Do architektury patří jen domény, stránky a sektory mezi nimi.")
        with canvas.graph_lock_for(pid):
            current = self.read(pid)
            if current["revision"] != expected:
                raise ValueError(CONFLICT)
            if actor not in ("human", "system"):
                from backend.canvas.activity_log import HumanRequired
                from backend.canvas.protected_fields import protected_changes

                changes = protected_changes(current["graph"], graph)
                if changes:
                    raise HumanRequired(actor, "Tato pole mění jen člověk v UI: " + ", ".join(changes[:10]))
            dropped = ids(current["graph"])[0] - ids(graph)[0]
            hits = canvas.architecture_references(pid, dropped, hidden=ids(graph)[0])
            if hits:
                raise ValueError(blocked_message(hits))
            if wid is not None:
                # Složený graf prostoru, odkud zápis přišel, musí zůstat platný (hosty, cesty, rodiče).
                content, legacy = canvas.workspace_content(pid, wid)
                removed = next_removed(current["graph"], current["removed"], graph)
                validate_graph(compose(graph, removed, content, legacy=legacy)[0])
            with canvas.lock_for(pid):
                db = canvas.db_for(pid)
                with db:
                    self.write(db, pid, graph, expected, actor, label)
            return self.public(pid)
