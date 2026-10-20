"""Observed latest GitHub checks; this never verifies a required-check policy."""


def _positive_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def observed_checks(snapshot, sha):
    latest, invalid = {}, False
    for kind, entries in (("check", snapshot.get("checks", [])), ("status", snapshot.get("statuses", []))):
        for item in entries:
            if not isinstance(item, dict):
                invalid = True
                continue
            item_sha = item.get("headSha" if kind == "check" else "sha")
            if item_sha != sha:
                continue
            identifier = item.get("id")
            name = item.get("name" if kind == "check" else "context")
            if not _positive_id(identifier) or not isinstance(name, str) or not name.strip():
                invalid = True
                continue
            if kind == "check" and not _positive_id(item.get("appId")):
                invalid = True
                continue
            key = (kind, item.get("appId"), name)
            old = latest.get(key)
            if old is None or identifier > old["id"]:
                latest[key] = item
            elif old["id"] == identifier and old != item:
                invalid = True
    states = []
    for key, item in latest.items():
        if key[0] == "status":
            state = {"success": "passed", "failure": "failed", "error": "failed", "pending": "pending"}.get(item.get("state"), "unknown")
        elif item.get("status") == "completed":
            state = {"success": "passed", "failure": "failed", "cancelled": "failed", "timed_out": "failed", "action_required": "failed", "startup_failure": "failed", "stale": "unknown"}.get(item.get("conclusion"), "unknown")
        else:
            state = "pending" if item.get("status") in {"queued", "in_progress", "waiting", "pending", "requested"} else "unknown"
        states.append(state)
    status = ("failed" if "failed" in states else "unknown" if invalid or not states or "unknown" in states
              else "pending" if "pending" in states else "passed")
    return {"status": status, "observedCount": len(states)}
