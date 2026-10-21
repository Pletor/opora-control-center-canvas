"""Validate stored lifecycle data independently of transport normalization."""
from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_review_policy_validation import github_id, timestamp


def semantic(value):
    if not isinstance(value, dict) or value.get("state") not in {"open", "closed-unmerged", "merged"}:
        raise ValueError("Invalid observed PR state.")
    identifier(value["headSha"])
    if value["headRepoId"] is not None:
        github_id(value["headRepoId"])
    if type(value["draft"]) is not bool:
        raise ValueError("Invalid observed draft state.")
    if value["state"] == "merged":
        timestamp(value["mergedAt"])
        identifier(value["mergeCommitSha"])
    elif value["mergedAt"] is not None or value["mergeCommitSha"] is not None:
        raise ValueError("Unmerged PR cannot carry a merged fact.")
    return value


def observation(data):
    if (not isinstance(data, dict) or set(data) != {"complete", "observedFrom", "observedUntil", "repository", "pr"}
            or data.get("complete") is not True):
        raise ValueError("Reconciliation requires complete lifecycle data.")
    if timestamp(data["observedUntil"]) < timestamp(data["observedFrom"]):
        raise ValueError("Invalid observation interval.")
    if not isinstance(data["repository"], dict) or set(data["repository"]) != {"id", "fullName"}:
        raise ValueError("Invalid observed repository shape.")
    github_id(data["repository"]["id"])
    name = data["repository"]["fullName"]
    if not isinstance(name, str) or name.casefold() != name or len(name) > 255:
        raise ValueError("Invalid observed repository name.")
    if not isinstance(data["pr"], dict) or set(data["pr"]) != {
            "id", "number", "baseRef", "headSha", "headRepoId", "state", "draft", "merged", "mergedAt", "mergeCommitSha"}:
        raise ValueError("Invalid observed PR shape.")
    pr = semantic(data["pr"])
    github_id(pr["id"])
    github_id(pr["number"])
    if not isinstance(pr["baseRef"], str) or not 1 <= len(pr["baseRef"]) <= 255:
        raise ValueError("Invalid observed PR branch.")
    if type(pr["merged"]) is not bool or pr["merged"] != (pr["state"] == "merged"):
        raise ValueError("Inconsistent merged lifecycle metadata.")
    return data
