"""Explicit immutable V3 revisions with server-owned named native identities."""
from copy import deepcopy
from uuid import UUID, uuid5

from backend.canvas.opora_change_validation import scope, subject
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_complete import derive
from backend.canvas.opora_graph_complete_build import compile_plan, normalize_complete
from backend.canvas.operation_receipts import Receipt
from backend.canvas.payload_errors import NextStep


class SupersededProposal(NextStep):
    def __init__(self, latest):
        super().__init__("Proposal was superseded; review its latest revision.", code="proposal_superseded",
                         hint="Read proposal " + latest + " before preparing another revision.")
        self.latest = latest

    def body(self):
        return {**super().body(), "latestProposalId": self.latest}


def lineage_status(repo, identifier):
    """Derived read metadata; never written into the immutable proposal or receipt."""
    current, seen, direct = identifier, set(), None
    while current not in seen:
        seen.add(current)
        row = repo.db.execute("SELECT id FROM opora_graph_proposals WHERE project_id=? AND workspace_id=? "
                              "AND json_extract(content, '$.supersedes')=? ORDER BY created_at DESC,id DESC LIMIT 1",
                              (*repo.scope, current)).fetchone()
        if row is None:
            break
        current = repo.read(row[0])["id"]
        direct = direct or current
    return {"supersededBy": direct, "latestProposalId": current} if direct else {}


def require_latest(repo, identifier):
    """Called inside the native write transaction; an immutable parent has one successor."""
    status = lineage_status(repo, identifier)
    if status:
        raise SupersededProposal(status["latestProposalId"])


def validate_allocation(allocation, plan):
    if (not isinstance(allocation, dict) or set(allocation) != {"ids", "nodeKinds"}
            or not isinstance(allocation["ids"], dict) or not isinstance(allocation["nodeKinds"], dict)):
        raise ValueError("Invalid named identity allocation.")
    for label, value in allocation["ids"].items():
        if not isinstance(label, str) or not label or not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError("Invalid native identity label or UUID.")
    if len(set(allocation["ids"].values())) != len(allocation["ids"]):
        raise ValueError("Native identity labels must have unique UUIDs.")
    for ref, kind in allocation["nodeKinds"].items():
        from backend.canvas.canvas_plan_fields import plan_ref
        plan_ref(ref, "identityAllocation")
        if kind not in ("node", "sector", "area") or "node:" + ref not in allocation["ids"]:
            raise ValueError("Invalid retained node identity kind.")
    for node in plan["nodes"]:
        if allocation["nodeKinds"].get(node["ref"]) != node["kind"]:
            raise ValueError("A retained ref cannot change kind.")


def inherited_allocation(old, plan):
    allocation = deepcopy(old.get("identityAllocation"))
    if allocation is None:
        ids = {}
        compile_plan(old["plan"], old["acceptedGraph"], old["baseGraph"], old["stateEffects"]["before"],
                     old["identitySeed"], observed=ids)
        allocation = {"ids": ids, "nodeKinds": {node["ref"]: node["kind"] for node in old["plan"]["nodes"]}}
    for node in plan["nodes"]:
        prior = allocation["nodeKinds"].setdefault(node["ref"], node["kind"])
        if prior != node["kind"]:
            raise ValueError("A retained ref cannot change kind, including a previously removed ref.")
    return allocation


def revise(proposals, identifier, payload, by):
    expected = {"project", "workspace", "expectedAcceptedHead", "expectedGraphDigest", "subject",
                "plan", "observeResearchSources", "operationId"}
    if set(payload) != expected or payload["observeResearchSources"] is not True:
        raise ValueError("Revise requires explicit fresh research observation and an operationId.")
    project, workspace = scope(payload)
    author, label = _author(by, allow_agent=True), subject(payload)
    plan = normalize_complete(payload["plan"])
    receipt = Receipt({**payload, "proposalId": identifier}, "graph-proposal-revise", author)
    with proposals.service.graph_lock_for(project), proposals.service.lock_for(project):
        repo = proposals.repository(project, workspace)
        with repo.db:
            repo.db.execute("BEGIN IMMEDIATE")
            replay = receipt.replay(repo.db)
            if replay is not None:
                return replay
            old = repo.read(identifier)
            if old.get("schemaVersion") != 3 or old["kind"] != "graph-changes" or repo.accepted(identifier):
                raise ValueError("Revise requires an unaccepted complete V3 proposal.")
            require_latest(repo, identifier)
            context, graph, manifest = proposals.current_change(project, workspace, plan["removeNodes"], plan["adoptArchitectureContext"])
            proposals.expect(context, payload["expectedAcceptedHead"], payload["expectedGraphDigest"])
            if old["parentRevision"] != context["acceptedHead"]:
                raise ValueError("Proposal accepted base changed; explicitly rebase before revising.")
            allocation = inherited_allocation(old, plan)
            seed = str(uuid5(UUID(old["identitySeed"]), payload["operationId"]))
            derived = derive(proposals.service, project, workspace, graph, manifest, plan,
                             identity_seed=seed, identity_allocation=allocation)
            validate_allocation(derived["identityAllocation"], plan)
            record = proposals.change_record(project, workspace, context, manifest, derived, author, label, identifier)
            result = {**repo.insert(record), "accepted": False}
            receipt.begin(repo.db)
            receipt.complete(repo.db, result)
            return result
