"""Záznam činnosti: každý zápis do aplikace s původcem (člověk / agent). Kontrakt: docs/zaznam-cinnosti.md.

Agent se hlásí hlavičkou `X-Opora-Actor: agent; name=<jméno>`. Člověkem je jen požadavek
s relačním dokladem UI (`backend/app/human_session.py`); bez hlavičky i bez dokladu je
původce `unknown` a lidské akce mu server odmítne (upgrade-opora #29).
Tabulka `activity_log` leží v registry.sqlite (schéma database/schema/project_schema.py).
"""

import json
import re

from backend.canvas.canvas_service import now

ACTORS = ("human", "agent", "unknown")


class HumanRequired(Exception):
    """Akce patří člověku v UI; `actor` je skutečný původce požadavku (agent / unknown)."""

    def __init__(self, actor, message):
        super().__init__(message)
        self.actor = actor


def require_human(actor, message):
    """Jen člověk v UI, i při plné autonomii: výjimky docs/plna-autonomie-agenta.md §4."""
    if actor != "human":
        raise HumanRequired(actor, message)


def require_authority(actor, message):
    """Brána „jen člověk“: člověk, nebo agent v projektu s plnou autonomií (docs/plna-autonomie-agenta.md §2)."""
    from backend.canvas.authority import acts_as_human
    if not acts_as_human(actor):
        raise HumanRequired(actor, message)


AGENT_NAME = re.compile(r"^[\w .:()\-]{1,80}$")
NODE_KEYS = ("nodeId", "node", "sectorId")
MAX_LIMIT = 500
DEFAULT_LIMIT = 100
MAX_SUMMARY = 400
MAX_ROWS = 50_000
# Akce agenta díky plné autonomii: značka na konci `summary` (bez změny schématu tabulky).
AUTONOMY_MARK = "autonomy=full"


def parse_actor(header):
    """(`actor`, `agent`) z hlavičky X-Opora-Actor; neplatná nebo chybějící = `unknown`, nikdy člověk."""
    if not header:
        return "unknown", ""
    kind, _, rest = header.partition(";")
    if kind.strip().lower() != "agent":
        return "unknown", ""
    name = "agent"
    key, _, value = rest.strip().partition("=")
    if key.strip().lower() == "name" and AGENT_NAME.match(value.strip()):
        name = value.strip()
    return "agent", name


def describe(body, query):
    """Projekt, prostor, karty a krátký popis z těla JSON a query; nic z obsahu textů."""
    try:
        payload = json.loads(body) if body else {}
    except (ValueError, UnicodeDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    project = payload.get("project") or query.get("project") or ""
    workspace = payload.get("workspace") or query.get("workspace") or ""
    nodes = [payload[key] for key in NODE_KEYS if isinstance(payload.get(key), str) and payload[key]]
    parts = [",".join(sorted(key for key in payload if key not in ("project", "workspace")))]
    if isinstance(payload.get("plan"), dict):
        from backend.canvas.canvas_plan_summary import plan_summary
        parts.append(plan_summary(payload["plan"]))
        extensions = payload["plan"].get("extend", [])
        if isinstance(extensions, list):
            nodes.extend(item["node"][1:] for item in extensions if isinstance(item, dict)
                         and isinstance(item.get("node"), str) and item["node"].startswith("@"))
    op = payload.get("op")
    if isinstance(op, dict) and isinstance(op.get("kind"), str):
        parts.append("op=" + op["kind"])
    output = payload.get("output")
    if isinstance(output, dict) and isinstance(output.get("done"), dict):
        parts.append("done.proposed=" + str(bool(output["done"].get("proposed"))).lower())
        if "confirmed" in output["done"]:
            parts.append("done.confirmed=" + str(bool(output["done"]["confirmed"])).lower())
    return {
        "project": project if isinstance(project, str) else "",
        "workspace": workspace if isinstance(workspace, str) else "",
        "nodeIds": nodes,
        "summary": " ".join(part for part in parts if part)[:MAX_SUMMARY],
    }


class ActivityLog:
    def __init__(self, service):
        self.service = service

    def record(self, *, actor, agent, method, path, described, status, autonomy=False):
        if autonomy:
            described = {**described, "summary": (described["summary"][:MAX_SUMMARY - len(AUTONOMY_MARK) - 1]
                                                  + " " + AUTONOMY_MARK).strip()}
        elif described["summary"].split(" ")[-1:] == [AUTONOMY_MARK]:
            # Klíč těla se značkou se nesmí vydávat za akci z plné autonomie.
            described = {**described, "summary": described["summary"][:MAX_SUMMARY - 2] + " ~"}
        with self.service.registry_lock:
            self.service.db.execute(
                "INSERT INTO activity_log(at,actor,agent,method,path,project_id,workspace_id,node_ids,status,summary)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (now(), actor, agent, method, path, described["project"], described["workspace"],
                 json.dumps(described["nodeIds"]), status, described["summary"]),
            )
            # Retence: drží posledních MAX_ROWS záznamů, aby smyčka agenta nenafoukla registr (#41).
            self.service.db.execute(
                "DELETE FROM activity_log WHERE id <= (SELECT MAX(id) FROM activity_log) - ?", (MAX_ROWS,))
            self.service.db.commit()

    def list(self, *, project="", workspace="", actor="", node_id="", limit=DEFAULT_LIMIT, before=None):
        if actor and actor not in ACTORS:
            raise ValueError("actor musí být human, agent nebo unknown.")
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit musí být 1–{MAX_LIMIT}.")
        where, args = [], []
        for column, value in (("project_id", project), ("workspace_id", workspace), ("actor", actor)):
            if value:
                where.append(f"{column}=?")
                args.append(value)
        if node_id:
            # `%` a `_` v ID jsou doslovné znaky, ne zástupné (upgrade-opora #41).
            escaped = node_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where.append("node_ids LIKE ? ESCAPE '\\'")
            args.append(f'%"{escaped}"%')
        if before is not None:
            where.append("id<?")
            args.append(before)
        sql = "SELECT * FROM activity_log" + (" WHERE " + " AND ".join(where) if where else "")
        with self.service.registry_lock:
            rows = self.service.db.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit + 1)).fetchall()
        entries = [_entry(row) for row in rows[:limit]]
        return {"entries": entries, "nextBefore": entries[-1]["id"] if len(rows) > limit else None}


def _entry(row):
    return {
        "id": row["id"], "at": row["at"], "actor": row["actor"], "agent": row["agent"],
        "method": row["method"], "path": row["path"], "project": row["project_id"],
        "workspace": row["workspace_id"], "nodeIds": json.loads(row["node_ids"]),
        "status": row["status"], "summary": row["summary"],
        "autonomy": "full" if row["summary"].split(" ")[-1:] == [AUTONOMY_MARK] else None,
    }
