"""Owner-only continuation bookkeeping; actions and snapshots stay exact."""
import json


def identity(action):
    return json.dumps({key: value for key, value in action.items() if key not in ("offset", "limit", "snapshot")},
                      ensure_ascii=False, sort_keys=True)


def remember(pending, action, result):
    key = identity(action)
    if result.get("nextOffset") is None:
        pending.pop(key, None)
    else:
        pending[key] = {**action, "offset": result["nextOffset"], "snapshot": result["snapshot"]}


def mismatch(pending, action):
    expected = pending.get(identity(action))
    if expected is None and action.get("offset", 0) != 0:
        return "Owner reads must start at offset 0 in this turn; a prior snapshot does not prove the prefix was read."
    if expected and (action.get("offset", 0), action.get("snapshot")) != (expected["offset"], expected["snapshot"]):
        return "Continuation must use the preceding nextOffset and exact snapshot; no unread range may be skipped."
    return None
