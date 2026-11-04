"""Záznam činnosti: každý zápis do aplikace s původcem (člověk / agent). Kontrakt: docs/zaznam-cinnosti.md.

Agent se hlásí hlavičkou `X-Opora-Actor: agent; name=<jméno>`. Člověkem je jen požadavek
s relačním dokladem UI (`backend/app/human_session.py`); bez hlavičky i bez dokladu je
původce `unknown` a lidské akce mu server odmítne (upgrade-opora #29).
Tabulka `activity_log` leží v registry.sqlite (schéma database/schema/project_schema.py).
"""

import json
import re
from datetime import UTC, datetime

from backend.canvas.activity_labels import SEPARATOR, body_label, clean, unique
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
# Poslední změna na uzel: kolik nejnovějších úspěšných zápisů prostoru se projde (jeden dotaz na plátno).
LATEST_SCAN = 2000
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


COMMIT = re.compile(r"[0-9a-f]{7,64}")


def note(request, node_ids=(), label=""):
    """Routa doplní záznamu, co zná až při zápisu: ID nových uzlů, uzly přijatého návrhu, rozdíl architektury.

    Middleware ho přidá v `describe(..., hint=...)` k tomu, co dá tělo; selhání tu nikdy neshodí zápis."""
    hint = getattr(request.state, "activity_hint", None) or {"nodeIds": [], "label": ""}
    hint = {**hint, "nodeIds": [*hint["nodeIds"], *node_ids], "label": label or hint["label"]}
    request.state.activity_hint = hint


def note_scope(request, project, workspace):
    """Projekt a prostor zápisu, který je nemá v těle ani v query (brána je bere z relace)."""
    hint = getattr(request.state, "activity_hint", None) or {"nodeIds": [], "label": ""}
    request.state.activity_hint = {**hint, "scope": {"project": project, "workspace": workspace}}


def note_from(request, trace):
    """`note` z `trace() -> (label, nodeIds)`, které čte uložená data; chyba stopy nikdy neshodí hotový zápis."""
    try:
        label, nodes = trace()
    except Exception:  # noqa: BLE001 - záznam činnosti je doplněk, zápis už proběhl
        return
    note(request, nodes, label)


def describe(body, query, path="", hint=None):
    """Projekt, prostor, karty a krátký popis z těla JSON a query; nic z obsahu textů.

    `path` končící `/local-merge` dá popisu `local_merge commit=<sha>` (docs/lokalni-slouceni.md §2).
    Zápis, který mění karty, má na začátku `summary` čitelný popisek oddělený `SEPARATOR`
    (`activity_labels.py`); `hint` je doplněk routy z `note`."""
    try:
        payload = json.loads(body) if body else {}
    except (ValueError, UnicodeDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    scope = (hint or {}).get("scope") or {}  # brána: projekt a prostor nese relace, ne tělo
    # Toky (/api/flow) nesou projekt jako `project_id`; zeď brány ho musí vidět stejně jako `project`.
    project = (payload.get("project") or payload.get("project_id") or query.get("project")
               or scope.get("project") or "")
    workspace = payload.get("workspace") or query.get("workspace") or scope.get("workspace") or ""
    nodes = [payload[key] for key in NODE_KEYS if isinstance(payload.get(key), str) and payload[key]]
    parts = [",".join(sorted(key for key in payload if key not in ("project", "workspace")))]
    plan_text = ""
    if isinstance(payload.get("plan"), dict):
        from backend.canvas.canvas_plan_summary import plan_summary
        plan_text = plan_summary(payload["plan"])
        parts.append(plan_text)
        extensions = payload["plan"].get("extend", [])
        if isinstance(extensions, list):
            nodes.extend(item["node"][1:] for item in extensions if isinstance(item, dict)
                         and isinstance(item.get("node"), str) and item["node"].startswith("@"))
    if path.endswith("/local-merge"):
        commit = payload.get("commit")
        parts.insert(0, "local_merge" + (" commit=" + commit if isinstance(commit, str) and COMMIT.fullmatch(commit)
                                         else ""))
    op = payload.get("op")
    if isinstance(op, dict) and isinstance(op.get("kind"), str):
        parts.append("op=" + op["kind"])
    output = payload.get("output")
    if isinstance(output, dict) and isinstance(output.get("done"), dict):
        parts.append("done.proposed=" + str(bool(output["done"].get("proposed"))).lower())
        if "confirmed" in output["done"]:
            parts.append("done.confirmed=" + str(bool(output["done"]["confirmed"])).lower())
    label, touched = body_label(path, payload)
    if plan_text and label.endswith(plan_text):
        parts.remove(plan_text)  # souhrn dávky už nese popisek celý
    if hint:
        touched = [*touched, *hint.get("nodeIds", ())]
        label = clean(hint["label"]) if hint.get("label") else label
    technical = " ".join(part for part in parts if part).replace("|", "/")
    return {
        "project": project if isinstance(project, str) else "",
        "workspace": workspace if isinstance(workspace, str) else "",
        "nodeIds": unique([*nodes, *touched]),
        "summary": SEPARATOR.join(part for part in (label, technical) if part)[:MAX_SUMMARY],
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

    def list(self, *, project="", workspace="", actor="", node_id="", limit=DEFAULT_LIMIT, before=None, agent="",
             since="", until=""):
        """Nejnovější první. `agent` = přesné jméno agenta (`heart`); `since` / `until` = časy ISO 8601 (i se `Z`),
        rozsah `since <= at <= until` (kroky jedné dávky srdce, docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md)."""
        if actor and actor not in ACTORS:
            raise ValueError("actor musí být human, agent nebo unknown.")
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit musí být 1–{MAX_LIMIT}.")
        where, args = [], []
        columns = (("project_id", project), ("workspace_id", workspace), ("actor", actor), ("agent", agent))
        for column, value in columns:
            if value:
                where.append(f"{column}=?")
                args.append(value)
        for bound, value in ((">=", since), ("<=", until)):
            if value:
                where.append(f"at{bound}?")
                args.append(_moment(value))
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


    def latest_by_node(self, *, project, workspace=""):
        """`{nodeId: {at, actor, agent, label, path}}`: nejnovější úspěšný zápis s uzlem, z posledních `LATEST_SCAN`
        zápisů projektu (a prostoru) s `nodeIds`. Jen čtení, bez změny schématu."""
        if not project:
            raise ValueError("Chybí project.")
        where, args = ["project_id=?", "node_ids<>'[]'", "status BETWEEN 200 AND 299"], [project]
        if workspace:
            where.append("workspace_id=?")
            args.append(workspace)
        sql = ("SELECT at,actor,agent,path,node_ids,summary FROM activity_log WHERE " + " AND ".join(where)
               + " ORDER BY id DESC LIMIT ?")
        with self.service.registry_lock:
            rows = self.service.db.execute(sql, (*args, LATEST_SCAN)).fetchall()
        latest = {}
        for row in rows:
            for node in json.loads(row["node_ids"]):
                if isinstance(node, str) and node not in latest:
                    latest[node] = {"at": row["at"], "actor": row["actor"], "agent": row["agent"],
                                    "label": entry_label(row["summary"]), "path": row["path"]}
        return latest


def entry_label(summary):
    """Čitelný popisek zápisu: část `summary` před `SEPARATOR`, jinak technický popis (zkrácený)."""
    head, sep, _ = summary.partition(SEPARATOR)
    text = head if sep else summary.removesuffix(AUTONOMY_MARK)
    return clean(text)


def _moment(value):
    """Čas ISO 8601 v tvaru sloupce `at` (`datetime.isoformat()` v UTC), aby šel porovnat jako řetězec."""
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("since / until musí být čas ISO 8601.") from None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def _entry(row):
    return {
        "id": row["id"], "at": row["at"], "actor": row["actor"], "agent": row["agent"],
        "method": row["method"], "path": row["path"], "project": row["project_id"],
        "workspace": row["workspace_id"], "nodeIds": json.loads(row["node_ids"]),
        "status": row["status"], "summary": row["summary"], "label": entry_label(row["summary"]),
        "autonomy": "full" if row["summary"].split(" ")[-1:] == [AUTONOMY_MARK] else None,
    }
