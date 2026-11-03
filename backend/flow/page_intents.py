"""Stav záměru stránky (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §4–§5): jediné místo, které ho počítá.

Stránka je uzel grafu se `site.kind = "page"`, její záměr je workflow `page_intent` s `owner_ref = opora:page:<id>`.
Stav: `none` (bez workflow, aktivní verze i kandidáta), `pending` (kandidát čeká na člověka), `approved` (aktivní
verze, stránka se od schválení nezměnila) a `stale` (aktivní verze, ale `pageDigest` schválení se liší od otisku
stránky teď). Otisk stránky = sha256 kanonického JSON jejích `site` polí `path`, `goal`, `feel`, `sections`; schválení
ho zapíše do logu `version.approved` (`workflows.approve`). `doneCount` počítá uzly `intent.done` aktivní verze,
bez ní kandidáta. Čte ho snímek srdce, `map_check` (`page.no-intent`, `page.intent-stale`) a `GET /api/flow/page-intents`.
`intent_claims` dá rozkladu (`ticket.issue` s `machine.intent`) tvrzení `claim` uzlů `intent.done` aktivní verze.
"""

import hashlib
import json

from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import get_version, list_versions, list_workflows

DIGEST_KEYS = ("path", "goal", "feel", "sections")
DONE = "intent.done"


def owner_ref(page_id):
    return f"opora:page:{page_id}"


def pages_of(graph):
    """Uzly stránek grafu `{nodes}` v jeho pořadí."""
    return [node for node in graph.get("nodes") or []
            if isinstance(node.get("site"), dict) and node["site"].get("kind") == "page"]


def page_digest(site):
    """Otisk záměru člověka na stránce: sha256 kanonického JSON `path`, `goal`, `feel`, `sections` (chybějící = null)."""
    data = {key: (site or {}).get(key) for key in DIGEST_KEYS}
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _approved_digest(db, version_id):
    row = db.execute("SELECT payload FROM flow_log_events WHERE type='version.approved' "
                     "AND json_extract(payload,'$.version_id')=? ORDER BY seq DESC LIMIT 1", (version_id,)).fetchone()
    return json.loads(row["payload"]).get("pageDigest") if row else None


def _done(version):
    return sum(node.get("type") == DONE for node in version["graph"].get("nodes") or [])


def status(db, project_id, pages):
    """`[{pageId, state, workflowId?, activeN?, candidateN?, doneCount}]` pro stránky `[{id, site}]` v jejich pořadí."""
    flows = {flow["owner_ref"]: flow for flow in list_workflows(db, project_id, "page_intent")}
    result = []
    for page in pages:
        item, flow = {"pageId": page["id"], "state": "none", "doneCount": 0}, flows.get(owner_ref(page["id"]))
        if flow is not None:
            versions = list_versions(db, flow["id"])
            active = next((v for v in versions if v["status"] == "active"), None)
            candidate = next((v for v in reversed(versions) if v["status"] == "candidate"), None)
            item["workflowId"] = flow["id"]
            if active:
                item["activeN"] = active["n"]
                fresh = _approved_digest(db, active["id"]) == page_digest(page.get("site"))
                item["state"] = "approved" if fresh else "stale"
            if candidate:
                item["candidateN"], item["state"] = candidate["n"], "pending"
            item["doneCount"] = _done(active or candidate) if active or candidate else 0
        result.append(item)
    return result


def read_status(service, project, graph):
    """`status` stránek grafu pod zámkem registru (graf čte volající mimo něj)."""
    with service.registry_lock:
        return status(service.db, project, pages_of(graph))


def owner_of(db, version_id):
    """`(project_id, pageId)` verze záměru stránky; jiný druh workflow = None."""
    flow = db.execute("SELECT kind, project_id, owner_ref FROM flow_workflows WHERE id=?",
                      (get_version(db, version_id)["workflow_id"],)).fetchone()
    if flow["kind"] != "page_intent":
        return None
    return flow["project_id"], flow["owner_ref"].removeprefix("opora:page:")


def current_digest(graph, page_id):
    """Otisk stránky `page_id` v grafu; stránka v grafu není = None."""
    page = next((node for node in pages_of(graph) if node["id"] == page_id), None)
    return page_digest(page["site"]) if page else None


def intent_claims(db, project_id, version_id, node_ids):
    """Tvrzení `claim` uzlů `node_ids` aktivní verze `page_intent` projektu; jinak `FlowInvalid` s důvodem."""
    version = get_version(db, version_id)
    flow = db.execute("SELECT kind, project_id FROM flow_workflows WHERE id=?", (version["workflow_id"],)).fetchone()
    if flow["kind"] != "page_intent" or flow["project_id"] != project_id:
        raise FlowInvalid("Verze není záměr stránky tohoto projektu.")
    if version["status"] != "active":
        raise FlowInvalid(f"Rozkládá se jen schválená (aktivní) verze záměru, verze je {version['status']}.")
    nodes = {node["id"]: node for node in version["graph"].get("nodes") or []}
    claims = []
    for node_id in node_ids:
        node = nodes.get(node_id)
        if node is None or node.get("type") != DONE:
            raise FlowInvalid(f"Uzel {node_id} není kritérium intent.done této verze.")
        claim = (node.get("params") or {}).get("claim")
        if not isinstance(claim, str) or not claim.strip():
            raise FlowInvalid(f"Kritérium {node_id} nemá claim.")
        claims.append(claim.strip())
    return claims
