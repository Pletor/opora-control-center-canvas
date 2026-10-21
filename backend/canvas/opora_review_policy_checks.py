"""Only exact trusted app/name pairs can satisfy required check-run policy."""
from backend.canvas.opora_review_checks import observed_checks
from backend.canvas.opora_review_policy_ids import safe_id


def required_checks(snapshot, required, sha):
    latest, seen, invalid = {}, {}, False
    for item in snapshot.get("checks", []):
        if not isinstance(item, dict) or not safe_id(item.get("id")) or not safe_id(item.get("appId")):
            invalid = True
            continue
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            invalid = True
            continue
        identifier = item["id"]
        if identifier in seen and seen[identifier] != item:
            invalid = True
        seen[identifier] = item
        if item.get("headSha") != sha:
            continue
        key = (item["appId"], item["name"])
        if key not in latest or identifier > latest[key]["id"]:
            latest[key] = item
    rows = []
    for required_item in required:
        item = latest.get((required_item["appId"], required_item["name"]))
        status = observed_checks({"checks": [item], "statuses": []}, sha)["status"] if item else "missing"
        rows.append({**required_item, "status": "unknown" if invalid else status,
                     "runId": item["id"] if item else None})
    return {"policyVerified": False, "required": rows}, invalid
