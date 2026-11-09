"""Hybrid solution retrieval over the existing authorized canonical knowledge graph."""
from backend.editor.research import solution_candidates, solution_ranking, solution_comparison, solution_verification, model


def search(canvas, scopes, query, limit, authorize, context, validate, ranking="hybrid", runner=None):
    if ranking not in ("hybrid","lexical"):
        model.fail("Unknown solution ranking.")
    validate(canvas,scopes,query,[],[],limit,authorize)
    candidates, total, truncated = solution_candidates.collect(canvas,scopes,query,authorize,context)
    ranked, retrieval = solution_ranking.rank(candidates,query,ranking,runner)
    found={}
    proofs={}
    for item in ranked:
        p,w,node=item["project"],item["workspace"],item["node"]
        key=(p,w)
        if key not in proofs:
            ids=[record["node"]["id"] for record in ranked if record["project"]==p and record["workspace"]==w]
            proofs[key]=solution_verification.project(canvas,p,w,item["view"],ids)
        proof=proofs[key][node["id"]]
        snapshot={"workspaceId":w,"graphDigest":item["view"]["digest"],"verification":proof}
        result={"solutionRef":{"projectId":p,"nodeId":node["id"]},"snapshot":snapshot,
                "title":node["name"],"purpose":node["purpose"],"element":node.get("element"),
                "verification":proof,"evidence":item["evidence"],"match":item["match"],"facts":solution_comparison.facts(item)}
        identity=(p,node["id"])
        if identity in found:
            found[identity]["snapshots"].append(snapshot)
            if proof.get("verified") and not found[identity]["verification"].get("verified"):
                found[identity]={**result,"snapshots":found[identity]["snapshots"]}
        else:
            found[identity]={**result,"snapshots":[snapshot]}
    solutions=sorted(found.values(),key=lambda item:(-item["match"]["score"],item["title"].casefold(),item["solutionRef"]["projectId"],item["solutionRef"]["nodeId"]))[:limit]
    retrieval.update(candidates=total,candidatesRanked=len(candidates),candidateLimit=solution_candidates.MAX_CANDIDATES,truncated=truncated)
    return {"solutions":solutions,"truncated":truncated or len(found)>limit,"ranking":"hybrid-lexical-semantic-graph" if retrieval["used"]=="hybrid" else "lexical-all-terms",
            "retrieval":retrieval,"comparison":solution_comparison.compare(solutions)}
