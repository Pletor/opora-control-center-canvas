"""Bounded owner-conversation excerpts of native solutions, never a second search engine."""
import json


def size(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True))


def excerpt(value, limit):
    if size(value) <= limit:
        return value
    return {"excerpt": json.dumps(value, ensure_ascii=False, sort_keys=True)[:limit],
            "truncated": True, "totalChars": size(value)}


def proof(value):
    if size(value) <= 1600:
        return value
    keys = ("status", "verified", "independent", "level", "executionId", "receiptId", "acceptedRevision",
            "assignmentDigest", "headSha", "graphDigest", "graphManifestId", "workspaceId")
    kept = {key: value[key] for key in keys if key in value}
    return {**kept, "projection": {"truncated": True, "omittedFields": [key for key in value if key not in kept]}}


def solution(value):
    facts = value.get("facts", {})
    spec = facts.get("specification")
    fields = (spec or {}).get("fields", {})
    inputs, sources = facts.get("inputs", []), facts.get("sources", [])
    variants = value.get("snapshots", [value["snapshot"]])
    result = {"solutionRef": value["solutionRef"], "title": value["title"][:240],
        "purpose": value["purpose"][:600], "element": {"kind": (value.get("element") or {}).get("kind")},
        "snapshot": {key: value["snapshot"][key] for key in ("workspaceId", "graphDigest")},
        "verification": proof(value["verification"]), "match": excerpt(value.get("match"), 600),
        "snapshots": [{key: item[key] for key in ("workspaceId", "graphDigest")} for item in variants[:3]],
        "facts": {"specification": {**{key: spec[key] for key in ("acceptedRevision", "revision")},
            "fields": {key: text[:400] if isinstance(text, str) else excerpt(text, 400) for key, text in fields.items()}}
            if spec else None, "inputs": [excerpt(item, 350) for item in inputs[:3]], "sources": sources[:4]},
        "projection": {"titleTruncated": len(value["title"]) > 240, "purposeTruncated": len(value["purpose"]) > 600,
            "fieldsTruncated": sorted(set((spec or {}).get("fieldsTruncated", [])) |
                {key for key, text in fields.items() if isinstance(text, str) and len(text) > 400}),
            "inputsAvailable": len(inputs), "nativeInputsTruncated": facts.get("inputsTruncated", False),
            "sourcesAvailable": len(sources), "snapshotsAvailable": len(variants),
            "otherSnapshotProofsOmitted": len(variants) > 1,
            "evidenceHeadersOmitted": len(value.get("evidence", []))}}
    # Canonical references are kept whole. Reduce excerpt lists rather than cutting an identity.
    while size(result) > 6000 and (result["facts"]["sources"] or result["facts"]["inputs"] or result["snapshots"]):
        for items in (result["facts"]["sources"], result["facts"]["inputs"], result["snapshots"]):
            if items:
                items.pop()
    while size(result) > 6000:
        result["title"] = result["title"][:len(result["title"]) // 2]
        result["purpose"] = result["purpose"][:len(result["purpose"]) // 2]
        if result["facts"]["specification"]:
            for key, text in result["facts"]["specification"]["fields"].items():
                if isinstance(text, str):
                    result["facts"]["specification"]["fields"][key] = text[:len(text) // 2]
                    if key not in result["projection"]["fieldsTruncated"]:
                        result["projection"]["fieldsTruncated"].append(key)
        result["projection"].update(titleTruncated=True, purposeTruncated=True)
    result["projection"].update(inputsReturned=len(result["facts"]["inputs"]),
        sourcesReturned=len(result["facts"]["sources"]), snapshotsReturned=len(result["snapshots"]))
    return result


def project(payload):
    comparison = payload.get("comparison", {})
    common = comparison.get("commonSources", [])
    return {"solutions": [solution(item) for item in payload["solutions"]],
        "ranking": payload["ranking"], "retrieval": excerpt(payload.get("retrieval"), 1200),
        "truncated": payload["truncated"],
        "comparison": {"basis": comparison.get("basis"), "commonSources": common[:4],
            "commonSourcesAvailable": len(common), "commonSourcesTruncated": len(common) > 4,
            "differences": [{"field": item["field"]} for item in comparison.get("differences", [])],
            "valuesOmitted": True},
        "projection": {"kind": "bounded native solution excerpts", "truncated": True, "fullResearchHeadersIncluded": False,
            "exactSourceRead": "Use research_read source:{projectId,workspaceId,id,revision}; follow all chunks.",
            "nativeSolutionCount": len(payload["solutions"]), "nativePayloadChars": size(payload)}}
