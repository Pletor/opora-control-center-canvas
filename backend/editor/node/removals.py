import uuid
from datetime import UTC, datetime

from backend.canvas.graph import digest, encode, payload_project, valid_id
from backend.editor.node import removal_recovery

MAX_SELECTION = 500
# Agent smí smazat jen malý kus nehotové práce; víc, sektory, brány a uzavřené karty maže člověk (upgrade-opora #41).
AGENT_REMOVAL_LIMIT = 20


def selection_ids(target):
    """`target` výběru: čárkami spojený seznam 1..500 různých id uzlů."""
    ids = target.split(",") if isinstance(target, str) else []
    if not 1 <= len(ids) <= MAX_SELECTION or len(set(ids)) != len(ids) or not all(map(valid_id, ids)):
        raise ValueError("Neplatný výběr k odstranění.")
    return ids


def descendants(nodes, roots):
    """Cíle a všichni jejich potomci přes `parentId`."""
    children = {}
    for item in nodes:
        children.setdefault(item["parentId"], []).append(item["id"])
    removed, pending = set(), list(roots)
    while pending:
        item = pending.pop()
        if item not in removed:
            removed.add(item)
            pending.extend(children.get(item, []))
    return removed


class RemovalService:
    def __init__(self, canvas):
        self.canvas = canvas

    def archived(self, project):
        with self.canvas.registry_lock:
            return (
                self.canvas.db.execute(
                    "SELECT 1 FROM archived_projects WHERE project_id=?", (project,)
                ).fetchone()
                is not None
            )

    def project_plan(self, project, workspace, target):
        if project != target or workspace != "main":
            raise ValueError("Nesouhlasí rozsah odpojení projektu.")
        data = self.canvas.row("projects", project)
        with self.canvas.registry_lock:
            running = self.canvas.db.execute(
                "SELECT 1 FROM jobs WHERE project_id=? AND status IN ('queued','running') LIMIT 1",
                (project,),
            ).fetchone()
        if running:
            raise ValueError("Probíhá operace repozitáře. Odpojte ho až po jejím dokončení.")
        workspaces = self.canvas.workspaces(project)
        snapshot = {"project": data, "workspaces": workspaces}
        return snapshot, {
            "project": project,
            "workspace": "main",
            "target": project,
            "kind": "project",
            "label": data["name"],
            "workspaceCount": len(workspaces),
            "nodeIds": [],
            "nodeCount": 0,
            "edgeCount": 0,
            "digest": digest(snapshot),
        }

    def remove_project(self, payload):
        project = payload_project(payload)
        with self.canvas.git_lock, self.canvas.graph_lock_for(project), self.canvas.lock_for(project), self.canvas.registry_lock, self.canvas.db:
            self.canvas.db.execute("BEGIN IMMEDIATE")
            snapshot, preview = self.project_plan(
                payload["project"], payload["workspace"], payload["target"]
            )
            if payload["digest"] != preview["digest"]:
                raise ValueError("Projekt se změnil. Otevřete nový náhled odpojení.")
            self.canvas.db.execute(
                "INSERT INTO archived_projects VALUES(?,?,?)",
                (payload["project"], encode(snapshot), datetime.now(UTC).isoformat()),
            )
        # Odpojený projekt nesmí dál vracet nic z paměti čtení (graf, stav, verze).
        self.canvas.forget_project(payload["project"])
        return {"removedProject": payload["project"]}

    def plan(self, project, workspace, kind, target):
        current = self.canvas.view(project, workspace)
        graph = current["graph"]
        if kind not in ("node", "edge", "selection"):
            raise ValueError("Nepodporovaný typ odstranění.")
        if kind == "edge":
            selected = next((item for item in graph["edges"] if item["id"] == target), None)
            if selected is None:
                raise ValueError("Položka již v plátně neexistuje.")
            names = {n["id"]: n["name"] for n in graph["nodes"]}
            label = names[selected["source"]] + " → " + names[selected["target"]]
            removed = set()
        else:
            roots = selection_ids(target) if kind == "selection" else [target]
            by_id = {item["id"]: item for item in graph["nodes"]}
            if any(root not in by_id for root in roots):
                raise ValueError("Položka již v plátně neexistuje.")
            removed = descendants(graph["nodes"], roots)
            label = by_id[roots[0]]["name"] if len(roots) == 1 else f"{len(roots)} " + ("položky" if len(roots) < 5 else "položek")
        # Uzly architektury jsou společné všem prostorům projektu (docs/domeny-a-worktree.md §4):
        # na mainu jde odebrat jen architekturu a nikde ne tu, na kterou odkazuje jiný prostor.
        arch_nodes = self.canvas.architecture.node_ids(project)
        arch_edges = {e["id"] for e in self.canvas.architecture.read(project)["graph"]["edges"]}
        if current["readOnly"] and not (removed <= arch_nodes if kind != "edge" else target in arch_edges):
            raise ValueError("Main je pouze pro čtení. Přepněte do pracovního prostoru.")
        blocked = self.canvas.architecture_references(
            project, removed & arch_nodes, skip=workspace, hidden=arch_nodes - removed
        )
        remaining = {
            "nodes": [n for n in graph["nodes"] if n["id"] not in removed],
            "edges": [
                e
                for e in graph["edges"]
                if e["source"] not in removed
                and e["target"] not in removed
                and not (kind == "edge" and e["id"] == target)
            ],
        }
        from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
        with self.canvas.reading(project):
            stored_nodes = DesktopV3State(self.canvas).current(project, workspace)["state"]["nodes"]
        confirmed = sorted(n for n in removed if stored_nodes.get(n, {}).get("done", {}).get("confirmed"))
        preview = {
            "project": project,
            "workspace": workspace,
            "kind": kind,
            "target": target,
            "label": label,
            "confirmedNodeIds": confirmed,
            "nodeIds": sorted(removed),
            "nodeCount": len(removed),
            "edgeCount": len(graph["edges"]) - len(remaining["edges"]),
            "blockedBy": blocked,
            # Worktree ze skladiště odebrání neblokují; náhled je jen vyjmenuje (§13.3).
            "archivedWorktrees": self.canvas.archived_references(project, removed & arch_nodes),
            "digest": digest(
                {
                    "project": project,
                    "workspace": workspace,
                    "kind": kind,
                    "target": target,
                    "graph": current["digest"],
                }
            ),
        }
        return current, remaining, preview

    def preview(self, project, workspace, kind, target):
        if kind == "project":
            with self.canvas.registry_lock:
                return self.project_plan(project, workspace, target)[1]
        with self.canvas.reading(project):
            return self.plan(project, workspace, kind, target)[2]

    def guard(self, actor, current, remaining, preview):
        """Co smí smazat jen člověk: projekt, sektory, brány, uzavřené karty, vazby sektorů, víc než limit."""
        if actor in ("human", "system"):
            return
        from backend.canvas.activity_log import HumanRequired
        from backend.canvas.protected_fields import protected_changes
        if preview["kind"] == "project":
            raise HumanRequired(actor, "Projekt maže jen člověk v UI.")
        graph = current["graph"]
        kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
        gates = {n.get("gateNodeId") for n in graph["nodes"]} - {None}
        removed = set(preview["nodeIds"])
        reasons = []
        if any(kinds.get(n) == "sector" for n in removed):
            reasons.append("sektor")
        if removed & gates:
            reasons.append("brána sektoru")
        if preview.get("confirmedNodeIds"):
            reasons.append(f"uzavřené karty ({len(preview['confirmedNodeIds'])})")
        if len(removed) > AGENT_REMOVAL_LIMIT:
            reasons.append(f"víc než {AGENT_REMOVAL_LIMIT} uzlů")
        survivors = {"nodes": [n for n in graph["nodes"] if n["id"] not in removed],
                     "edges": [e for e in graph["edges"] if e["source"] not in removed and e["target"] not in removed]}
        if protected_changes(survivors, remaining):
            reasons.append("vazba mezi sektory")
        if reasons:
            raise HumanRequired(actor, "Tohle maže jen člověk v UI: " + ", ".join(reasons) + ".")

    def remove(self, payload, *, actor="system"):
        if (
            set(payload) != {"project", "workspace", "kind", "target", "digest", "confirmed"}
            or payload["confirmed"] is not True
        ):
            raise ValueError("Odstranění vyžaduje výslovné potvrzení náhledu.")
        if payload["kind"] == "project":
            self.guard(actor, None, None, {"kind": "project", "nodeIds": []})
            return self.remove_project(payload)
        project = payload["project"]
        with self.canvas.graph_lock_for(project):
            current, remaining, preview = self.plan(
                payload["project"], payload["workspace"], payload["kind"], payload["target"]
            )
            if payload["digest"] != preview["digest"]:
                raise ValueError("Plátno se změnilo. Otevřete nový náhled odstranění.")
            if preview["blockedBy"]:
                from backend.canvas.project_architecture import blocked_message
                raise ValueError(blocked_message(preview["blockedBy"]))
            self.guard(actor, current, remaining, preview)
            removed_edge_ids = {e["id"] for e in current["graph"]["edges"]} - {
                e["id"] for e in remaining["edges"]
            }
            # Snapshot i záznam obnovy předcházejí změně; jejich existence není důkazem mazání.
            recovery_id = uuid.uuid4().hex
            db = self.canvas.db_for(payload["project"])
            with self.canvas.lock_for(project), db:
                db.execute(
                    "INSERT INTO graph_recoveries VALUES(?,?,?,?,?)",
                    (
                        recovery_id,
                        payload["project"],
                        payload["workspace"],
                        encode(current["graph"]),
                        datetime.now(UTC).isoformat(),
                    ),
                )
                removal_recovery.capture(
                    self.canvas, db, recovery_id, payload["project"], payload["workspace"],
                    current["graph"], preview["nodeIds"], sorted(removed_edge_ids),
                )
            view = self.canvas.save_graph(
                payload["project"],
                payload["workspace"],
                remaining,
                current["digest"],
                allow_removal=True,
            )
            self.forget_workspaces(payload["project"], payload["workspace"], preview["nodeIds"])
            self.forget_state_entries(
                payload["project"], payload["workspace"], preview["nodeIds"], removed_edge_ids
            )
            return {"view": view, "nodeIds": preview["nodeIds"], "recoveryId": recovery_id}

    def restore(self, payload):
        """Krok zpět po smazání: vrátí uzly, vazby, stav Desktop v3 i prostor agenta (jednou)."""
        return removal_recovery.restore(self.canvas, payload)

    def forget_workspaces(self, project, workspace, node_ids):
        """Smazaná karta si bere svůj prostor agenta s sebou (docs/karta-pro-agenty.md).

        Import je až tady: `canvas_service` staví `RemovalService`, takže prostor agenta
        (přes `desktop_v3_state`) se na úrovni modulu importovat zpět nemůže."""
        from backend.editor.agent_memory.agent_workspace import AgentWorkspace

        store = AgentWorkspace(self.canvas)
        for node_id in node_ids:
            store.delete(project, workspace, node_id)

    def forget_state_entries(self, project, workspace, node_ids, edge_ids):
        """Smazaná karta i smazaná vazba si berou svůj obsah Desktop v3 stavu s sebou: bloky,
        pravidla, akce, materiály a uzavření karty (`state.nodes[id]`), zprávu agenta na vazbě
        (`state.edges[edgeId]`). Jinak by osiřelé karty a vazby v paměti jen rostly (viz nálezu
        oprava). Nahrané soubory podkladů zůstávají na disku beze změny — jejich úklid je mimo
        rozsah této opravy.

        Větev `onMet`/`onUnmet` druhu `node` v bloku jiné (přežívající) karty, která mířila na
        smazaný uzel, se vyprázdní stejně jako `_apply_remove` v `block_access.py` (`kind: "none"`)
        — jinak by uložení stavu spadlo na `check_node_branches`, protože graf už smazaný uzel nemá.

        Import je až tady ze stejného důvodu jako u `forget_workspaces`."""
        if not node_ids and not edge_ids:
            return
        from backend.editor.agent_memory.block_access import _default_branch
        from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

        store = DesktopV3State(self.canvas)
        with self.canvas.lock_for(project):
            current = store.current(project, workspace)
        state = current["state"]
        removed_nodes, removed_edges = set(node_ids), set(edge_ids)

        def clean(branch):
            if branch["kind"] == "node" and branch["targetId"] in removed_nodes:
                return _default_branch()
            return branch

        new_nodes = {}
        for node_id, node in state["nodes"].items():
            if node_id in removed_nodes:
                continue
            blocks = node.get("blocks")
            if blocks:
                node = {
                    **node,
                    "blocks": [
                        {
                            **block,
                            "state": {
                                **block["state"],
                                "onMet": clean(block["state"]["onMet"]),
                                "onUnmet": clean(block["state"]["onUnmet"]),
                            },
                        }
                        for block in blocks
                    ],
                }
            new_nodes[node_id] = node
        new_edges = {
            edge_id: report for edge_id, report in state["edges"].items() if edge_id not in removed_edges
        }
        new_state = {
            **state, "nodes": new_nodes, "edges": new_edges,
            "rules": [rule for rule in state["rules"]
                      if not (rule["scope"] == "node" and rule["target"] in removed_nodes)],
            "decisions": [item for item in state["decisions"] if item["nodeId"] not in removed_nodes],
        }
        if new_state == state:
            return
        store.save(
            {
                "project": project,
                "workspace": workspace,
                "expectedRevision": current["revision"],
                "state": new_state,
            }
        )
