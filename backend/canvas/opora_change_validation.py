"""Raw editable specification documents and bounded, typed proposal operations."""
import re

from backend.canvas.graph import digest, valid_id
from backend.canvas.payload_errors import invalid
from backend.editor.node.node_specs import validate_payload


def scope(payload):
    pid, wid = payload.get("project"), payload.get("workspace")
    if not all(valid_id(value) and len(value) <= 64 for value in (pid, wid)):
        # Stav 409 zůstává (sdílí ho desítky cest a jejich klienti); text říká, kde pole chybí.
        raise ValueError("Neplatný projekt nebo pracovní prostor: zápis OporaHubu nese project a workspace"
                         " v těle JSON, čtení v dotazu (?project=…&workspace=…).")
    return pid, wid


def identifier(value, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
        raise ValueError("Neplatné ID výchozí revize.")


def subject(payload):
    value = payload.get("subject")
    if not isinstance(value, str) or not value.strip() or len(value) > 200 or "\0" in value:
        raise invalid("", "subject", "Předmět návrhu musí mít 1 až 200 znaků" + ("; pole chybí." if value is None else "."),
                      "neprázdný text do 200 znaků: co návrh nebo přijetí mění", {"subject": "Výchozí zadání stránky"})
    return value.strip()


def documents(service, pid, wid, view):
    """Read originals, never the redacted agent-context projection."""
    return [{"nodeId": node["id"], "ownerWorkspace": service.document_workspace(pid, wid, node["id"]),
             **{key: spec[key] for key in ("revision", "fields")}}
            for node in sorted(view["graph"]["nodes"], key=lambda node: node["id"])
            for spec in [service.node_spec(pid, wid, node["id"])]]


def check_changes(payload, accepted, current):
    values = payload.get("changes")
    if not isinstance(values, list) or not 1 <= len(values) <= 100:
        raise ValueError("Návrh vyžaduje 1 až 100 změn zadání.")
    accepted = {item["nodeId"]: item for item in accepted}
    current = {item["nodeId"]: item for item in current}
    result, seen = [], set()
    pid, wid = scope(payload)
    for item in values:
        if not isinstance(item, dict) or set(item) != {"nodeId", "expectedRevision", "fields"}:
            raise ValueError("Změna vyžaduje nodeId, expectedRevision a úplná fields.")
        node = item["nodeId"]
        if not valid_id(node) or node in seen or node not in accepted or node not in current:
            raise ValueError("Karta chybí v přijatém zadání nebo se opakuje.")
        seen.add(node)
        validate_payload({"project": pid, "workspace": wid, "node": node,
                          "expected_revision": item["expectedRevision"], "fields": item["fields"]})
        previous = current[node]
        if (previous["ownerWorkspace"] != accepted[node]["ownerWorkspace"]
                or item["expectedRevision"] != previous["revision"]):
            raise ValueError("Pracovní zadání karty se změnilo. Načtěte nový kontext.")
        if item["fields"] == previous["fields"] and item["fields"] == accepted[node]["fields"]:
            raise ValueError("Změna zadání musí měnit alespoň jedno pole.")
        result.append({**item, "ownerWorkspace": previous["ownerWorkspace"], "before": previous["fields"],
                       "acceptedBefore": accepted[node]})
    return result


def specifications_version(items):
    return digest(items)
