"""Bounded canonical solution texts collected only after all requested scopes authorize."""
import re
from backend.editor.research import model, service as research
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from database.repositories.opora_changesets import ChangesetRepository
from backend.editor.research.solution_snapshot import materialization

MAX_CANDIDATES = 128
MAX_TEXT_BYTES = 6144
STOPWORDS = set("a an and the to of in for with is on jak se co do na v ve z ze pro s a i nebo je jsou".split())


def lexical(query, text):
    words = [word for word in re.findall(r"\w+",query.casefold()) if word not in STOPWORDS]
    return sum(word in text.casefold() for word in words) / len(words) if words else 0


def collect(canvas, scopes, query, authorize, context):
    for item in scopes:
        authorize(item["project"], item["workspace"], False)
    candidates = {}
    for item in scopes:
        project, workspace = item["project"], item["workspace"]
        view = research._scope(canvas, project, workspace)
        nodes = {node["id"]: node for node in view["graph"]["nodes"]}
        selected = item.get("scopeNodeId")
        if selected and selected not in nodes:
            model.fail("Search context is unavailable.", 404, "research_scope")
        allowed = set(nodes) if not selected else {selected}
        if selected and item.get("includeDescendants", True):
            while True:
                added = {node["id"] for node in nodes.values() if node.get("parentId") in allowed} - allowed
                if not added:
                    break
                allowed.update(added)
        for node in nodes.values():
            if node["id"] not in allowed or node["kind"] not in ("node", "sector"):
                continue
            title = research._json([node["id"], node["name"], node["purpose"], node.get("element")])
            links = [edge for edge in view["graph"]["edges"] if edge.get("relation") in ("requires", "uses", "communicates_with")
                     and node["id"] in (edge["source"], edge["target"])]
            graph_score = max((lexical(query, research._json(nodes.get(edge["target"] if edge["source"] == node["id"] else edge["source"], {}))) for edge in links), default=0)
            key = (project, workspace, node["id"])
            candidates[key] = {"project": project, "workspace": workspace, "view": view, "node": node,
                               "lexical": lexical(query, title), "legacyLexical":all(word in title.casefold() for word in query.casefold().split()),
                               "graph": graph_score, "titleText": title}
    ordered = sorted(candidates.values(), key=lambda item: (-item["lexical"], item["project"], item["workspace"], item["node"]["id"]))
    truncated = len(ordered)>MAX_CANDIDATES
    selected = ordered[:MAX_CANDIDATES]
    with materialization(canvas, selected, authorize):
        _materialize(canvas, selected, authorize, context)
    return selected, len(ordered), truncated


def _materialize(canvas, selected, authorize, context):
    specifications = {}
    for item in selected:
        project, workspace, node = item["project"], item["workspace"], item["node"]
        key = (project, workspace)
        if key not in specifications:
            with canvas.reading(project):
                repo = ChangesetRepository(canvas.db_for(project), project, workspace)
                head = repo.head()
                documents = {doc["nodeId"]: doc for doc in repo.read(head)["documents"]} if head else {}
                specifications[key] = (head, documents)
        head, documents = specifications[key]
        document = documents.get(node["id"])
        fields = redact_deep(document["fields"]) if document else {}
        item["specification"] = {"acceptedRevision": head, "revision": document["revision"], "fields": fields} if document else None
        evidence = context(canvas, project, workspace, node["id"], authorize)
        item["evidence"] = evidence["records"]
        own = [record for record in evidence["records"] if any(marker["relation"]=="local" and marker["scopeNodeId"]==node["id"] for marker in record["contexts"])]
        description = "\n".join([node["purpose"], *[str(fields.get(key, ""))[:1200] for key in ("goal", "acceptance", "non_goals")],
                                 *[record["card"]["title"] + ": " + record["card"]["summary"] for record in own[:8]]])
        item["semanticEligible"] = len(description.strip())>=30
        text = node["name"] + "\n" + description
        encoded = text.encode("utf-8")
        item["text"] = encoded[:MAX_TEXT_BYTES].decode("utf-8", "ignore")
        item["textTruncated"] = len(encoded)>MAX_TEXT_BYTES or evidence["truncated"] or len(own)>8
