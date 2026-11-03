"""Doklad přehrání záměru stránky `opora.intent-run/1` (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §6).

Stejně jako doklad cesty (`journey_runs.py`): Opora záměr nepřehrává a model nevolá, doklad ověří tvarem a uloží
jako neměnný záznam do `intent_runs` v `project.sqlite` (`verification: "agent-reported; not independently
verified"`).

- Tvar (chyba = `IntentRunInvalid`, HTTP 422): `{schema?, pageId, workflowVersionId, digest, nodes}`, jen známé
  klíče; `schema`, když je, `opora.intent-run/1`; `nodes` 1–100 položek `{nodeId, ok, reason?}`, `nodeId` z plánu
  verze dokladu, každý nejvýš jednou; `ok` je `true`, `false`, nebo `null` = neověřeno (pak `reason` povinný);
  `reason` ≤ 300 znaků. Verze musí patřit záměru stránky a `digest` musí být digest té verze.
- Stránka bez aktivní verze záměru je `IntentNotFound` (404).
- `stale` (vzor `lastRun.stale` cesty): `digest` dokladu se liší od digestu aktuální aktivní verze. Zastaralý
  doklad se uloží, ale srdce nebudí.
- `passed` se odvodí: žádný uzel nemá `ok: false` a každý krok plánu je `ok: true`.
- Každý neprošlý uzel (`ok: false`) aktuálního dokladu jde do logu pláten jako `intent.failed` (plátno 2, payload
  `{pageId, nodeId, reason, workflowVersionId}`) a probudí srdce (`backend/flow/canvas_log.py`).
"""

from datetime import UTC, datetime

from backend.flow.canvas_log import log_canvas
from backend.flow.workflows import FlowNotFound, get_version
from backend.project.architecture.intent_plan import active_version, plan_nodes, version_digest
from database.repositories.journey_runs import IntentRunStore

SCHEMA = "opora.intent-run/1"
VERIFICATION = "agent-reported; not independently verified"
KEYS = {"schema", "pageId", "workflowVersionId", "digest", "nodes"}
NODE_KEYS = {"nodeId", "ok", "reason"}


class IntentRunInvalid(ValueError):
    """Doklad nemá předepsaný tvar (HTTP 422)."""


def _text(value, name, limit, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value) <= limit:
        raise IntentRunInvalid(f"{name} musí být text o {minimum}–{limit} znacích.")
    return value


def _head(body):
    if not isinstance(body, dict):
        raise IntentRunInvalid("Doklad musí být objekt JSON.")
    unknown = sorted(set(body) - KEYS)
    if unknown:
        raise IntentRunInvalid(f"Neznámé klíče dokladu: {', '.join(unknown)}.")
    if body.get("schema", SCHEMA) != SCHEMA:
        raise IntentRunInvalid(f"schema musí být {SCHEMA}.")
    for key in ("pageId", "workflowVersionId", "digest"):
        _text(body.get(key), key, 200)
    nodes = body.get("nodes")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 100:
        raise IntentRunInvalid("nodes musí mít 1–100 položek.")
    for item in nodes:
        if not isinstance(item, dict) or set(item) - NODE_KEYS or not {"nodeId", "ok"} <= set(item):
            raise IntentRunInvalid("Uzel dokladu je {nodeId, ok, reason?}.")
        _text(item["nodeId"], "nodeId", 200)
        if item["ok"] not in (True, False, None):
            raise IntentRunInvalid("ok uzlu musí být true, false nebo null (neověřeno).")
        if "reason" in item or item["ok"] is None:
            _text(item.get("reason"), "reason", 300, minimum=0 if item["ok"] is not None else 1)
    return body


def validate_run(body, version, active):
    """Ověřený doklad proti verzi, kterou přehrál; `stale` proti aktivní verzi. Vrací záznam k uložení."""
    _head(body)
    if version["workflow_id"] != active["workflow_id"]:
        raise IntentRunInvalid("workflowVersionId nepatří záměru této stránky.")
    if body["digest"] != version_digest(version):
        raise IntentRunInvalid("digest neodpovídá verzi workflowVersionId.")
    planned = plan_nodes(version["graph"])
    known = {item["nodeId"] for item in planned}
    reported = [item["nodeId"] for item in body["nodes"]]
    if set(reported) - known:
        raise IntentRunInvalid(f"Uzly {', '.join(sorted(set(reported) - known))} v plánu verze nejsou.")
    if len(set(reported)) != len(reported):
        raise IntentRunInvalid("Uzel se v dokladu opakuje.")
    nodes = [{key: item[key] for key in ("nodeId", "ok", "reason") if key in item} for item in body["nodes"]]
    passing = {item["nodeId"] for item in nodes if item["ok"] is True}
    passed = (all(item["ok"] is not False for item in nodes)
              and all(step["nodeId"] in passing for step in planned if step["kind"] == "step"))
    return {"schema": SCHEMA, "pageId": body["pageId"], "workflowVersionId": version["id"], "digest": body["digest"],
            "nodes": nodes, "passed": passed, "stale": body["digest"] != version_digest(active),
            "verification": VERIFICATION}


def record_intent_run(service, project, body, author="agent"):
    """`POST /api/project-architecture/intent-runs`: ověří, uloží, neprošlé uzly zapíše do logu a probudí srdce."""
    _head(body)
    with service.registry_lock:
        active = active_version(service.db, project, body["pageId"])
        try:
            version = get_version(service.db, body["workflowVersionId"])
        except FlowNotFound as error:
            raise IntentRunInvalid("workflowVersionId neexistuje.") from error
    record = validate_run(body, version, active)
    recorded_at = datetime.now(UTC).isoformat(timespec="microseconds")
    db = service.db_for(project)
    with service.lock_for(project), db:
        db.execute("BEGIN IMMEDIATE")
        IntentRunStore(db, project).insert(record, recorded_at)
    if not record["stale"]:
        for item in record["nodes"]:
            if item["ok"] is False:
                log_canvas(service, project, 2, "intent.failed",
                           {"pageId": record["pageId"], "nodeId": item["nodeId"], "reason": item.get("reason", ""),
                            "workflowVersionId": record["workflowVersionId"]}, author)
    return {**record, "recordedAt": recorded_at}
