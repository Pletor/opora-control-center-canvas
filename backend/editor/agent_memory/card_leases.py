"""Expiring ownership; claims and renewals use conditional SQL writes.

Lease se vynucuje (upgrade-opora #35): zápis agenta na kartu, kterou drží jiný platný lease,
vyžaduje token v hlavičce `X-Opora-Lease`. Jeden vlastník drží nejvýš `MAX_PER_OWNER` karet,
člověk smí cizí lease uvolnit bez tokenu. Claim rovnou uloží snímek zadání (#36), takže
porovnání zadání pokrývá i práci, u které agent `assignment-snapshot` vynechal."""

import secrets
import time
from datetime import UTC, datetime

from backend.canvas.authority import acts_as_human
from backend.canvas.graph import valid_id
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.work_activity import record_activity, validate_touched
from backend.editor.agent_packet.sector_status import sector_blockers

MAX_PER_OWNER = 5


class CardLeases:
    def __init__(self, canvas):
        self.canvas = canvas

    def require(self, project, workspace, node_id, actor, token):
        """Zápis na kartu drženou platným lease smí jen držitel tokenu (nebo člověk)."""
        if actor == "human" or not all(isinstance(v, str) and valid_id(v) for v in (project, workspace, node_id)):
            return
        with self.canvas.reading(project):
            row = self.canvas.db_for(project).execute(
                "SELECT owner,token,expires_at FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=?",
                (project, workspace, node_id),
            ).fetchone()
        if row is not None and row["expires_at"] > time.time() and not (
                isinstance(token, str) and secrets.compare_digest(row["token"], token)):
            raise ValueError(f"Kartu drží {row['owner']}; zápis vyžaduje token převzetí v hlavičce X-Opora-Lease.")

    def summary(self, project, workspace):
        with self.canvas.reading(project):
            graph = self.canvas.view(project, workspace)["graph"]
            ids = {node["id"] for node in graph["nodes"]}
            stamp = time.time()
            rows = self.canvas.db_for(project).execute(
                "SELECT node_id,owner,expires_at FROM card_leases WHERE project_id=? AND workspace_id=?",
                (project, workspace),
            ).fetchall()
            return {"serverNow": stamp, "nodes": {row["node_id"]: {
                "owner": row["owner"], "expiresAt": row["expires_at"], "active": row["expires_at"] > stamp,
            } for row in rows if row["node_id"] in ids}}

    def apply(self, payload, *, actor="system"):
        common = {"project", "workspace", "nodeId", "op"}
        if not isinstance(payload, dict) or payload.get("op") not in ("claim", "heartbeat", "release"):
            raise ValueError("Převzetí vyžaduje op claim, heartbeat nebo release.")
        op = payload["op"]
        extra = {"owner", "ttlSeconds"} if op == "claim" else {"token", "ttlSeconds"} if op == "heartbeat" else {"token"}
        # Člověk uvolní zaseknuté nebo okupované převzetí i bez tokenu.
        # Plná autonomie (docs/plna-autonomie-agenta.md): agent smí převzetí uvolnit výslovně jako člověk;
        # běžný zápis cizí převzetí neobchází (`require`), převzetí je koordinace, ne oprávnění.
        forced = op == "release" and "token" not in payload and (actor == "human" or acts_as_human(actor))
        if forced:
            extra = set()
        if set(payload) - {"touched"} != common | extra or not all(valid_id(payload[k]) for k in ("project", "workspace", "nodeId")):
            raise ValueError("Neplatná pole nebo rozsah převzetí.")
        if "touched" in payload:
            validate_touched(payload["touched"])
        if op != "release" and (type(payload["ttlSeconds"]) is not int or not 30 <= payload["ttlSeconds"] <= 3600):
            raise ValueError("ttlSeconds musí být celé číslo od 30 do 3600.")
        if op == "claim":
            owner = payload["owner"]
            if not isinstance(owner, str) or not owner.strip() or len(owner) > 160 or any(ord(c) < 32 for c in owner):
                raise ValueError("Vlastník musí být neprázdný text do 160 znaků.")
        elif not forced and (not isinstance(payload["token"], str) or len(payload["token"]) != 64):
            raise ValueError("Neplatný token převzetí.")
        project, workspace, node_id = (payload[k] for k in ("project", "workspace", "nodeId"))
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            view = self.canvas.view(project, workspace)
            node = next((n for n in view["graph"]["nodes"] if n["id"] == node_id), None)
            if view["readOnly"] or node is None or node["kind"] not in ("node", "sector"):
                raise ValueError("Kartu v tomto rozsahu nelze převzít.")
            stored = DesktopV3State(self.canvas).read(project, workspace)["state"]
            if op != "release" and stored["nodes"].get(node_id, {}).get("done", {}).get("confirmed"):
                raise ValueError("Uzavřenou kartu nelze převzít ani prodloužit.")
            if op != "release" and sector_blockers(view["graph"], stored, node_id):
                raise ValueError("Kartu blokuje neověřený předchozí sektor.")
            stamp = time.time()
            expires = stamp + payload.get("ttlSeconds", 0)
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                if op in ("claim", "heartbeat"):
                    from backend.canvas.opora_execution_guard import legacy_lease
                    legacy_lease(db, project, workspace, node_id)
                if op == "claim":
                    held = db.execute(
                        "SELECT COUNT(*) FROM card_leases WHERE project_id=? AND workspace_id=? AND owner=? AND expires_at>? AND node_id<>?",
                        (project, workspace, owner.strip(), stamp, node_id),
                    ).fetchone()[0]
                    if held >= MAX_PER_OWNER:
                        raise ValueError(f"{owner.strip()} už drží {held} karet; nejdřív některou uvolněte.")
                    token = secrets.token_hex(32)
                    changed = db.execute(
                        "INSERT INTO card_leases VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,workspace_id,node_id)"
                        " DO UPDATE SET owner=excluded.owner,token=excluded.token,expires_at=excluded.expires_at"
                        " WHERE card_leases.expires_at<=?",
                        (project, workspace, node_id, owner.strip(), token, expires, stamp),
                    ).rowcount
                elif op == "heartbeat":
                    changed = db.execute(
                        "UPDATE card_leases SET expires_at=? WHERE project_id=? AND workspace_id=? AND node_id=? AND token=? AND expires_at>?",
                        (expires, project, workspace, node_id, payload["token"], stamp),
                    ).rowcount
                elif forced:
                    changed = db.execute(
                        "DELETE FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=?",
                        (project, workspace, node_id),
                    ).rowcount
                else:
                    changed = db.execute(
                        "DELETE FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=? AND token=?",
                        (project, workspace, node_id, payload["token"]),
                    ).rowcount
                if changed != 1:
                    raise ValueError("Kartu drží jiný agent, token nesouhlasí nebo převzetí vypršelo.")
                previous = db.execute("SELECT agent FROM card_work_activity WHERE project_id=? AND workspace_id=? AND node_id=?", (project, workspace, node_id)).fetchone()
                record_activity(db, project, workspace, node_id, owner.strip() if op == "claim" else previous["agent"] if previous else "",
                                datetime.fromtimestamp(stamp, UTC).isoformat(), claimed=op == "claim", touched=payload.get("touched"))
            snapshot = None
            if op == "claim":
                from backend.editor.agent_memory.assignment_snapshots import snapshot_assignment
                snapshot = snapshot_assignment(self.canvas, project, workspace, node_id)
            return {"nodeId": node_id, "op": op, "serverNow": stamp,
                    **({"expiresAt": expires} if op != "release" else {}),
                    **({"token": token, "assignment": {"id": snapshot["id"], "contextVersion": snapshot["contextVersion"]}}
                       if op == "claim" else {})}
