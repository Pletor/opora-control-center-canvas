"""Actual local dense scores plus lexical and explicit graph matches; no proof inference."""
import math
from backend.semantic_retrieval.service import MODEL_NAME, SemanticRetrieval, SemanticWorkerError, WorkerRunner

SEMANTIC_MIN = 0.82
MAX_SCORE_GAP = 0.12


def rank(candidates, query, ranking="hybrid", runner=None):
    metadata = {"requested": ranking, "used": "lexical", "semantic": {"status": "not_requested", "model": MODEL_NAME,
                "maxPassageTokens": 256, "minimumCosine": SEMANTIC_MIN}, "candidatePassagesTruncated": any(item["textTruncated"] for item in candidates)}
    scores = None
    if ranking == "hybrid":
        unavailable = None if runner is not None else SemanticRetrieval(None).availability_detail()
        try:
            if unavailable:
                raise SemanticWorkerError(unavailable)
            scores = (runner or WorkerRunner())(query, [{"text": item["text"]} for item in candidates]) if candidates else []
            if not isinstance(scores,list) or len(scores) != len(candidates) or any(isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not -1<=value<=1 for value in scores):
                raise SemanticWorkerError("Local semantic worker returned invalid scores.")
            metadata["used"] = "hybrid"
            metadata["semantic"]["status"] = "ok"
        except (SemanticWorkerError, OSError, ValueError) as error:
            scores = None
            metadata["semantic"].update(status="unavailable", detail=str(error))
    result = []
    for index, item in enumerate(candidates):
        dense = scores[index] if scores is not None else None
        if dense is None and not item.get("legacyLexical",item["lexical"]==1):
            continue  # Exact compatible all-terms lexical fallback, never a semantic claim.
        if dense is not None and item["lexical"] != 1 and (dense < SEMANTIC_MIN or not item["semanticEligible"]):
            continue
        score = item["lexical"] if dense is None else .25*item["lexical"] + .65*dense + .10*item["graph"]
        result.append({**item, "match": {"score": round(score,6), "lexical": item["lexical"], "semantic": dense, "graph": item["graph"]}})
    ordered = sorted(result,key=lambda item:(-item["match"]["score"],item["node"]["name"].casefold(),item["project"],item["workspace"],item["node"]["id"]))
    # Exact lexical anchors outrank merely related context; no unrelated third solution.
    if ordered and any(item["lexical"]==1 for item in ordered):
        ordered = [item for item in ordered if item["match"]["score"] >= ordered[0]["match"]["score"]-MAX_SCORE_GAP]
    metadata["maximumScoreGapFromExactAnchor"] = MAX_SCORE_GAP
    metadata["semanticAdmission"] = "own purpose, accepted specification or local research; shared and parent text alone cannot identify another solution"
    return ordered, metadata
