"""Server-captured proposals: compare the observed context before appending history.

This first migration stage checkpoints already saved canvas assignments. It neither
applies arbitrary client patches nor approves or merges implementation work.
"""

import json

from backend.canvas.opora_hub import _scope
from backend.editor.agent_packet.specification_context import capture_specification


class OporaProposals:
    def __init__(self, service, hub):
        self.service, self.hub = service, hub

    def context(self, scope):
        pid, _, _ = _scope(scope)
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            return self._context(scope)

    def _context(self, scope):
        pid, wid, scope_id = scope
        view = self.service.view(pid, wid)
        node = next((n for n in view["graph"]["nodes"] if n["id"] == scope_id), None)
        if node is None:
            raise ValueError("Rozsah v tomto pracovním prostoru neexistuje.")
        head = self.hub.head(scope)
        return {
            "head": head["id"] if head else None,
            "scope": {"kind": node["kind"], "id": scope_id},
            "specRevision": self.service.specs.read(scope)["revision"],
            "graphDigest": view["digest"],
            **capture_specification(self.service, pid, wid, scope_id),
        }

    def propose(self, scope, payload, by):
        pid, _, _ = _scope(scope)
        if not isinstance(payload, dict):
            raise ValueError("Obsah návrhu musí být objekt.")  # noqa: TRY004 — API maps validation to HTTP 409
        if "expectedHead" not in payload or "expectedContextVersion" not in payload:
            raise ValueError("Návrh vyžaduje expectedHead a expectedContextVersion z kontextu.")
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            if self.service.view(pid, scope[1])["readOnly"]:
                raise ValueError("Pracovní prostor je jen pro čtení; návrh zde nelze zapsat.")
            context = self._context(scope)
            if payload["expectedContextVersion"] != context["contextVersion"]:
                raise ValueError("Zadání se změnilo. Načtěte nový kontext návrhu.")
            return self.hub.propose(scope, {
                "kind": context["scope"]["kind"],
                "specRevision": context["specRevision"],
                "graphDigest": context["graphDigest"],
                "subject": payload.get("subject"), "by": by, "pair": None,
                "specificationSnapshot": {
                    "contextVersion": context["contextVersion"],
                    "specification": context["specification"],
                },
            }, expected_head=payload["expectedHead"])

    def diff(self, scope, before, after):
        """Compare immutable snapshots; legacy metadata cannot stand in for lost content."""
        snapshots = []
        for identifier in (before, after):
            record = self.hub.read(scope, identifier)
            snapshot = record.get("specificationSnapshot")
            if snapshot is None:
                raise ValueError("Starší commit nemá snímek zadání; obsah nelze porovnat.")
            snapshots.append(snapshot["specification"])
        return {"before": before, "after": after,
                "changes": differences(snapshots[0], snapshots[1])}


def differences(before, after, path=""):
    """JSON Pointer paths; arrays are atomic so reordering never invents identities."""
    if json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True):
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in before:
                changes.append({"op": "add", "path": pointer, "after": after[key]})
            elif key not in after:
                changes.append({"op": "remove", "path": pointer, "before": before[key]})
            else:
                changes.extend(differences(before[key], after[key], pointer))
        return changes
    return [{"op": "replace", "path": path, "before": before, "after": after}]
