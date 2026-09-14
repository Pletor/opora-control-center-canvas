"""Vazby skutečných sessions (Hermes, Claude) na uzel a jejich bezpečné sledování.

Router žije v `backend/api/live_run/node_session_routes.py` a skládá ho `backend/app/factory.py`.

Router nic nespouští: GET jen čte zdroje, POST jen uloží explicitně potvrzenou
vazbu po ověření existence session ve zdroji. Síťové a souborové čtení zdrojů
nikdy neprobíhá pod `service.lock`; zápis drží pořadí `graph_lock` -> `lock`.
"""

import json
import uuid
from datetime import UTC, datetime

from backend.canvas.graph import valid_id
from backend.live_run.node_session_sources import (
    SourceError,
    valid_lane,
    valid_session_id,
)

LIMIT = 100
TITLE_LIMIT = 200
SOURCES = ("hermes", "claude")
ROLES = ("orchestrator", "worker")
BIND_FIELDS = {
    "project", "workspace", "nodeId", "source", "sessionId", "runId",
    "role", "title", "parentSessionId", "confirmed",
}
SOURCE_LABELS = {
    "hermes": "Hermes API (metriky za celou session)",
    "claude": "Claude lane (stream-json, poslední result)",
}
EMPTY_METRICS = {"inputTokens": None, "outputTokens": None, "costUsd": None}


def _now():
    return datetime.now(UTC)


def _clean_title(value):
    if not isinstance(value, str):
        return None
    title = value.strip()
    if not 1 <= len(title) <= TITLE_LIMIT or any(ord(ch) < 32 for ch in title):
        return None
    return title


class NodeSessions:
    def __init__(self, service, *, hermes, claude, clock=None):
        self.service = service
        self.adapters = {"hermes": hermes, "claude": claude}
        self.clock = clock or _now

    # --- validace ---------------------------------------------------------

    @staticmethod
    def _validate_scope(pid, wid, node_id=None, *, node_required=False):
        if not valid_id(pid) or not valid_id(wid):
            raise ValueError("Neplatný projekt nebo pracovní prostor.")
        if (node_required or node_id is not None) and not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")

    def _validate_payload(self, payload):
        if not isinstance(payload, dict) or set(payload) != BIND_FIELDS:
            raise ValueError("Neplatný formát vazby session.")
        if payload["confirmed"] is not True:
            raise ValueError("Vazba session vyžaduje explicitní potvrzení.")
        self._validate_scope(payload["project"], payload["workspace"], payload["nodeId"], node_required=True)
        source = payload["source"]
        if source not in SOURCES:
            raise ValueError("Neznámý zdroj session.")
        if not valid_session_id(payload["sessionId"]):
            raise ValueError("Neplatný identifikátor session.")
        if source == "hermes" and payload["runId"] is not None:
            raise ValueError("Hermes session nemá identifikátor běhu (runId musí být null).")
        if source == "claude" and not valid_lane(payload["runId"]):
            raise ValueError("Claude session vyžaduje runId jako název lane.")
        if payload["role"] not in ROLES:
            raise ValueError("Neplatná role session.")
        title = _clean_title(payload["title"])
        if title is None:
            raise ValueError("Neplatný název session.")
        parent = payload["parentSessionId"]
        if parent is not None and (not valid_session_id(parent) or parent == payload["sessionId"]):
            raise ValueError("Neplatná nadřazená session.")
        return title

    def _live_node(self, pid, wid, node_id, *, for_write):
        view = self.service.view(pid, wid)
        if for_write and view["readOnly"]:
            raise ValueError("Main je pouze pro čtení. Vazbu session nelze uložit.")
        node = next((n for n in view["graph"]["nodes"] if n["id"] == node_id), None)
        if node is None:
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        return node

    # --- zápis ------------------------------------------------------------

    def bind(self, payload):
        title = self._validate_payload(payload)
        pid, wid, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        source, session_id, run_id = payload["source"], payload["sessionId"], payload["runId"]
        # Levná kontrola rozsahu před čtením zdroje; závazná kontrola proběhne znovu pod zámkem.
        self._live_node(pid, wid, node_id, for_write=True)
        existing = self._find(pid, wid, source, session_id)
        if existing is not None:
            self._check_same(existing, payload, title)
            return self._session(existing, self._node_names(pid, wid))
        # Čtení zdroje (síť/soubory) mimo všechny zámky.
        try:
            adapter = self.adapters[source]
            evidence = adapter.verify(session_id) if source == "hermes" else adapter.verify(run_id, session_id)
        except SourceError as exc:
            raise ValueError(f"Session nelze ověřit ve zdroji: {exc}") from None
        bound_at = self.clock().isoformat()
        row_id = uuid.uuid4().hex
        with self.service.graph_lock:
            self._live_node(pid, wid, node_id, for_write=True)
            db = self.service.db_for(pid)
            with self.service.lock, db:
                db.execute("BEGIN IMMEDIATE")
                existing = self._find(pid, wid, source, session_id)
                if existing is None:
                    db.execute(
                        "INSERT INTO node_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL)",
                        (row_id, pid, wid, node_id, source, session_id, run_id, payload["role"], title,
                         payload["parentSessionId"], bound_at, bound_at, int(evidence["baselineCursor"])),
                    )
        if existing is not None:
            self._check_same(existing, payload, title)
            return self._session(existing, self._node_names(pid, wid))
        with self.service.lock:
            row = dict(self.service.db_for(pid).execute("SELECT * FROM node_sessions WHERE id=?", (row_id,)).fetchone())
        return self._session(row, self._node_names(pid, wid))

    def _find(self, pid, wid, source, session_id):
        with self.service.lock:
            row = self.service.db_for(pid).execute(
                "SELECT * FROM node_sessions WHERE project_id=? AND workspace_id=? AND source=? AND session_id=? AND closed_at IS NULL",
                (pid, wid, source, session_id),
            ).fetchone()
        return dict(row) if row is not None else None

    @staticmethod
    def _check_same(row, payload, title):
        same = (
            row["node_id"] == payload["nodeId"]
            and row["run_id"] == payload["runId"]
            and row["role"] == payload["role"]
            and row["title"] == title
            and row["parent_session_id"] == payload["parentSessionId"]
        )
        if not same:
            raise ValueError("Session už je v tomto pracovním prostoru navázaná s jinými údaji; vazbu nelze přepsat.")

    # --- čtení ------------------------------------------------------------

    def _node_names(self, pid, wid):
        view = self.service.view(pid, wid)
        return {n["id"]: n.get("name") or "" for n in view["graph"]["nodes"]}

    def list(self, pid, wid, node_id=None):
        self._validate_scope(pid, wid, node_id)
        names = self._node_names(pid, wid)
        if node_id is not None and node_id not in names:
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        query = "SELECT * FROM node_sessions WHERE project_id=? AND workspace_id=?"
        params = [pid, wid]
        if node_id is not None:
            query += " AND node_id=?"
            params.append(node_id)
        query += " ORDER BY bound_at DESC, id LIMIT ?"
        params.append(LIMIT + 1)
        with self.service.lock:
            rows = [dict(r) for r in self.service.db_for(pid).execute(query, params).fetchall()]
        # Zdroje se čtou až po uvolnění zámku; jeden vadný zdroj neskryje ostatní řádky.
        sessions = [self._session(row, names) for row in rows[:LIMIT]]
        return {
            "project": pid,
            "workspace": wid,
            "nodeId": node_id,
            "sessions": sessions,
            "limit": LIMIT,
            "truncated": len(rows) > LIMIT,
        }

    def _observe(self, row):
        adapter = self.adapters[row["source"]]
        now = self.clock()
        baseline = {
            "baseline_cursor": row["baseline_cursor"],
            "baseline_at": datetime.fromisoformat(row["baseline_at"]),
            "now": now,
        }
        try:
            if row["source"] == "hermes":
                return adapter.observe(row["session_id"], **baseline)
            return adapter.observe(row["run_id"], row["session_id"], **baseline)
        except SourceError as exc:
            reason = f"Zdroj nedostupný: {exc}"
        except Exception:  # noqa: BLE001 - vadný zdroj nesmí shodit ani skrýt ostatní vazby.
            reason = "Zdroj nedostupný: vrátil neočekávaná data."
        return {"sourceAvailable": False, "status": "unknown", "statusReason": reason, "model": None,
                "events": [], "lastActivityAt": None, "metrics": dict(EMPTY_METRICS)}

    def _session(self, row, names):
        if row.get("closed_at"):
            return json.loads(row["closed_snapshot"])
        observed = self._observe(row)
        # Uzavření může doběhnout během síťového čtení: nevracet novou aktivitu
        # do již uzavřeného přiřazení ani z dříve zahájeného GET.
        with self.service.lock:
            closed = self.service.db_for(row["project_id"]).execute(
                "SELECT closed_snapshot FROM node_sessions WHERE id=? AND closed_at IS NOT NULL",
                (row["id"],),
            ).fetchone()
        if closed is not None:
            return json.loads(closed["closed_snapshot"])
        return {
            "id": row["id"],
            "source": row["source"],
            "sessionId": row["session_id"],
            "parentSessionId": row["parent_session_id"],
            "role": row["role"],
            "title": row["title"],
            "project": row["project_id"],
            "workspace": row["workspace_id"],
            "nodeId": row["node_id"],
            "nodeName": names.get(row["node_id"], ""),
            "model": observed["model"],
            "status": observed["status"],
            "statusReason": observed["statusReason"],
            "sourceAvailable": observed["sourceAvailable"],
            "lastActivityAt": observed["lastActivityAt"],
            "boundAt": row["bound_at"],
            "closedAt": None,
            "events": observed["events"],
            "metrics": observed["metrics"],
            "sourceLabel": SOURCE_LABELS[row["source"]],
        }
