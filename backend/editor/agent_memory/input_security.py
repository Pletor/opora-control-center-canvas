"""Explicit URL download tasks must retain an actionable input-security block."""

import uuid

TAG = "input-security"
CONDITION = "Ověřit povolené URL, SSRF a privátní adresy, DNS a přesměrování, limity velikosti/času a typ obsahu; doložit testy."


def security_block(number):
    branch = {"kind": "none", "targetId": "", "note": ""}
    return {"id": uuid.uuid4().hex, "number": str(number), "title": "Bezpečnost vstupu", "text": CONDITION,
            "tags": [TAG], "todos": [], "images": [], "parentBlockId": "", "ports": [],
            "state": {"status": "open", "condition": CONDITION, "onMet": dict(branch), "onUnmet": dict(branch)}}


def validate_input_security(node):
    if "downloadsUrl" not in node:
        return
    if type(node["downloadsUrl"]) is not bool:
        raise ValueError("downloadsUrl musí být true/false.")
    if not node["downloadsUrl"]:
        return
    blocks = [block for block in node.get("blocks", []) if TAG in block.get("tags", [])]
    if not blocks or any(not block["state"]["condition"].strip() for block in blocks):
        raise ValueError("Karta stahující URL vyžaduje blok Bezpečnost vstupu se štítkem input-security a podmínkou.")
    if node.get("done", {}).get("confirmed") and any(block["state"]["status"] != "met" for block in blocks):
        raise ValueError("Před uzavřením URL downloaderu musí být blok bezpečnosti vstupu splněný.")
