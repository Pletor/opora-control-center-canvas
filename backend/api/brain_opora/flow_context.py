"""Kontext plátna ke zprávě srdci (`context: {kind: "flow", flowId, versionId?, nodeIds?}`, docs/brain-heart-channel.md §2).

Ověří, že plátno knihovny existuje, verze patří k němu a vybrané uzly leží v grafu té verze (bez `versionId` v aktivní,
jinak v nejnovější). Vrací očištěný slovník, který srdce čte jako data (`batch.py`), ne jako příkaz.
"""
from backend.brain_opora.determinism.gate_payloads import invalid
from backend.flow import library
from backend.flow.workflows import FlowNotFound

KEYS = {"kind", "flowId", "versionId", "nodeIds"}
EXAMPLE = '{"kind": "flow", "flowId": "<id plátna>", "versionId": "<id verze>", "nodeIds": ["<id uzlu>"]}'
NODE_LIMIT = 100


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 200 and "\0" not in value


def flow_context(service, raw):
    if not isinstance(raw, dict) or set(raw) - KEYS or raw.get("kind") != "flow" or not _text(raw.get("flowId")):
        raise invalid('context je {kind: "flow", flowId, versionId?, nodeIds?}.', "Příklad: " + EXAMPLE)
    version_id, node_ids = raw.get("versionId"), raw.get("nodeIds", [])
    if (version_id is not None and not _text(version_id)) or not (
            isinstance(node_ids, list) and len(node_ids) <= NODE_LIMIT and all(_text(n) for n in node_ids)):
        raise invalid("versionId je text a nodeIds seznam textů (nejvýš 100).", "Příklad: " + EXAMPLE)
    try:
        with service.registry_lock:
            versions = library.flow_detail(service.db, raw["flowId"])["versions"]
    except FlowNotFound:
        raise invalid(f"Plátno {raw['flowId']} v knihovně neexistuje.",
                      "Id plátna vypíše: python opora_heart.py library show.") from None
    if version_id is not None:
        version = next((v for v in versions if v["id"] == version_id), None)
    else:
        version = next((v for v in versions if v["status"] == "active"), versions[-1] if versions else None)
    if version is None:
        raise invalid(f"Verze {version_id or '(žádná)'} nepatří k plátnu {raw['flowId']}.",
                      "Verze vypíše: python opora_heart.py library get FLOW.")
    present = {n.get("id") for n in version["graph"].get("nodes") or []}
    foreign = [n for n in node_ids if n not in present]
    if foreign:
        raise invalid(f"Uzly {', '.join(foreign)} nejsou ve verzi {version['id']} plátna.",
                      "Vyber uzly z grafu: python opora_heart.py library get FLOW.")
    return {"kind": "flow", "flowId": raw["flowId"], "versionId": version["id"], "nodeIds": node_ids}
