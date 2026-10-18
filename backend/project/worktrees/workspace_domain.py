"""Worktree patří jedné doméně architektury (docs/domeny-a-worktree.md §6).

`require_domain` hlídá založení i přeřazení: `nodeId` musí být uzel architektury projektu se
`site.kind == "application"`. Přeřazení (`PATCH /api/workspaces/{wid}`) mění jen `workspaces.node_id`;
Git worktree, větev ani data prostoru se nehýbou.
"""

from backend.canvas.graph import payload_project, valid_id

REBIND_KEYS = {"project", "nodeId"}


def domain_ids(graph):
    """ID domén v grafu architektury (uzly se `site.kind == "application"`)."""
    return {
        node["id"]
        for node in graph["nodes"]
        if isinstance(node.get("site"), dict) and node["site"].get("kind") == "application"
    }


def require_domain(service, pid, node_id):
    if not valid_id(node_id) or node_id not in domain_ids(service.architecture.read(pid)["graph"]):
        raise ValueError("Worktree musí patřit doméně z architektury projektu. Vyberte doménu.")


def rebind(service, wid, payload):
    """Přiřadí existující worktree k doméně; vrací řádek `workspaces`."""
    if not isinstance(payload, dict) or set(payload) != REBIND_KEYS:
        raise ValueError("Neplatný formát přiřazení worktree (project, nodeId).")
    pid = payload_project(payload)
    if not valid_id(wid):
        raise ValueError("Neplatný identifikátor.")
    require_domain(service, pid, payload["nodeId"])
    with service.registry_lock:
        row = service.row("workspaces", wid)
        if row["project_id"] != pid:
            raise ValueError("Pracovní prostor patří jinému projektu.")
        if service.db.execute("SELECT 1 FROM archived_workspaces WHERE id=?", (wid,)).fetchone():
            raise ValueError("Worktree je ve skladišti; ze skladiště jde jen číst.")
        service.db.execute("UPDATE workspaces SET node_id=? WHERE id=?", (payload["nodeId"], wid))
        service.db.commit()
        return service.row("workspaces", wid)
