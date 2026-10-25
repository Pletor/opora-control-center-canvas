"""Select explicit server-owned scope policy; never merge or inherit project authority."""
from backend.canvas.opora_execution_observer_auth import strict_json


class ScopeNotConfigured(ValueError):
    pass


def select(raw, validator, project=None, workspace=None):
    if len(raw.encode("utf-8")) > 64 * 1024:
        raise ValueError("Harness scope configuration exceeds 64 KiB.")
    value = strict_json(raw)
    multiple = isinstance(value, dict) and value.get("schema") == "harness.scopes/1"
    if multiple:
        if set(value) != {"schema", "scopes"} or not isinstance(value["scopes"], list) or not 1 <= len(value["scopes"]) <= 32:
            raise ValueError("Harness scopes requires 1 to 32 explicit policies.")
        entries = value["scopes"]
    else:
        entries = [value]
    seen, checked = set(), []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Harness scope policy must be an object.")  # noqa: TRY004 -- configuration errors share a fail-closed ValueError boundary.
        item = validator(entry)
        key = (item["project"], item["workspace"])
        if key in seen:
            raise ValueError("Duplicate Harness scope policy.")
        seen.add(key)
        checked.append(item)
    if project is None and workspace is None and not multiple:
        return checked[0]  # Legacy inspection API; runtime callers always supply exact scope.
    for item in checked:
        if (item["project"], item["workspace"]) == (project, workspace):
            return item
    raise ScopeNotConfigured("Harness is not configured for this exact scope.")
