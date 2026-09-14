import uuid
from datetime import UTC, datetime

from backend.canvas.graph import digest, encode


class RemovalService:
    def __init__(self, canvas):
        self.canvas = canvas

    def archived(self, project):
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
        if self.canvas.db.execute(
            "SELECT 1 FROM jobs WHERE project_id=? AND status IN ('queued','running') LIMIT 1",
            (project,),
        ).fetchone():
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
        with self.canvas.git_lock, self.canvas.graph_lock, self.canvas.lock, self.canvas.db:
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
        return {"removedProject": payload["project"]}

    def plan(self, project, workspace, kind, target):
        current = self.canvas.view(project, workspace)
        if current["readOnly"]:
            raise ValueError("Main je pouze pro čtení. Přepněte do pracovního prostoru.")
        graph = current["graph"]
        if kind not in ("node", "edge"):
            raise ValueError("Nepodporovaný typ odstranění.")
        items = graph["nodes"] if kind == "node" else graph["edges"]
        selected = next((item for item in items if item["id"] == target), None)
        if selected is None:
            raise ValueError("Položka již v plátně neexistuje.")
        removed = set()
        if kind == "node":
            children = {}
            for item in graph["nodes"]:
                children.setdefault(item["parentId"], []).append(item["id"])
            pending = [target]
            while pending:
                item = pending.pop()
                if item not in removed:
                    removed.add(item)
                    pending.extend(children.get(item, []))
            label = selected["name"]
        else:
            names = {n["id"]: n["name"] for n in graph["nodes"]}
            label = names[selected["source"]] + " → " + names[selected["target"]]
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
        preview = {
            "project": project,
            "workspace": workspace,
            "kind": kind,
            "target": target,
            "label": label,
            "nodeIds": sorted(removed),
            "nodeCount": len(removed),
            "edgeCount": len(graph["edges"]) - len(remaining["edges"]),
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
            with self.canvas.lock:
                return self.project_plan(project, workspace, target)[1]
        with self.canvas.graph_lock:
            return self.plan(project, workspace, kind, target)[2]

    def remove(self, payload):
        if (
            set(payload) != {"project", "workspace", "kind", "target", "digest", "confirmed"}
            or payload["confirmed"] is not True
        ):
            raise ValueError("Odstranění vyžaduje výslovné potvrzení náhledu.")
        if payload["kind"] == "project":
            return self.remove_project(payload)
        with self.canvas.graph_lock:
            current, remaining, preview = self.plan(
                payload["project"], payload["workspace"], payload["kind"], payload["target"]
            )
            if payload["digest"] != preview["digest"]:
                raise ValueError("Plátno se změnilo. Otevřete nový náhled odstranění.")
            # Snapshot předchází změně; jeho existence není důkazem dokončeného mazání.
            db = self.canvas.db_for(payload["project"])
            with self.canvas.lock, db:
                db.execute(
                    "INSERT INTO graph_recoveries VALUES(?,?,?,?,?)",
                    (
                        uuid.uuid4().hex,
                        payload["project"],
                        payload["workspace"],
                        encode(current["graph"]),
                        datetime.now(UTC).isoformat(),
                    ),
                )
            view = self.canvas.save_graph(
                payload["project"],
                payload["workspace"],
                remaining,
                current["digest"],
                allow_removal=True,
            )
            return {"view": view, "nodeIds": preview["nodeIds"]}
