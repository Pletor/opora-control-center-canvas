"""Lossless bounded reads of immutable cards and semantic topic hierarchy."""
import hashlib

from backend.editor.research import model, service as research


def parts(service, project, workspace, id, revision=None, offset=0, size=12000, snapshot=None):
    if type(offset) is not int or offset < 0 or type(size) is not int or not 1 <= size <= 64000:
        model.fail("offset must be nonnegative and size between 1 and 64000.")
    if offset and (revision is None or not snapshot):
        model.fail("Continuation requires the returned revision and snapshot.")
    card = research.detail(service, project, workspace, id, revision)["card"]
    serialized = research._json(card)
    digest = hashlib.sha256(research._json([project, workspace, id, card["revision"], serialized]).encode()).hexdigest()
    if snapshot is not None and snapshot != digest:
        model.fail("Snapshot does not match this scope and immutable card revision.", 409, "research_snapshot")
    if offset > len(serialized):
        model.fail("offset exceeds the complete card length.")
    end = min(offset + size, len(serialized))
    return {"project": project, "workspace": workspace, "id": id, "revision": card["revision"],
            "snapshot": digest, "format": "research-card-json", "offsetUnit": "unicode-code-points",
            "offset": offset, "total": len(serialized), "text": serialized[offset:end],
            "nextOffset": end if end < len(serialized) else None, "complete": end == len(serialized)}


def topics(service, project, workspace, archived=False):
    graph = research.listing(service, project, workspace, archived)
    roots = []
    for card in sorted(graph["cards"], key=lambda item: (item["topicPath"], item["id"])):
        children = roots
        path = []
        for label in card["topicPath"]:
            path = [*path, label]
            node = next((item for item in children if item["label"] == label), None)
            if node is None:
                node = {"label": label, "path": path, "cardIds": [], "children": []}
                children.append(node)
            children = node["children"]
        node["cardIds"].append(card["id"])
    return {"project": project, "workspace": workspace, "topics": roots}
