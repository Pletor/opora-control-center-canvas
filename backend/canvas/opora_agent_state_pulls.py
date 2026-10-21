"""Optional seam to the execution → pull request link module (docs/oporahub-agent-state.md).

The link module (`backend/canvas/opora_execution_pull_requests.py`) is developed separately.
When it is importable, its `list_execution_pull_requests` feeds the `pull_request`, `merge`
and `plan_writeback` stages; when it is absent those stages report `not_connected`.
Nothing here writes or guesses a link: no module means no link, never an empty success.

Accepted shapes: a list of items or `{"items": [...]}`. Item keys read: `executionId`,
`state` (`open` | `merged` | `closed`, alias `prState`) and optional `planWrittenBack`.
"""
import inspect

_override = None


def register(source):
    """Test/integration hook: replace the source (callable) or restore discovery (None)."""
    global _override  # One tiny documented registry slot.
    _override = source


def source():
    if _override is not None:
        return _override
    try:
        from backend.canvas.opora_execution_pull_requests import list_execution_pull_requests
    except ImportError:
        return None
    return list_execution_pull_requests


def read(canvas, project, workspace):
    """Normalized `[{executionId, state, planWrittenBack?}]` or None when not connected."""
    reader = source()
    if reader is None:
        return None
    arity = len(inspect.signature(reader).parameters)
    raw = reader(canvas, project, workspace) if arity >= 3 else reader(project, workspace)
    items = raw.get("items", []) if isinstance(raw, dict) else list(raw or [])
    result = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("executionId"), str):
            continue
        state = item.get("state", item.get("prState"))
        value = {"executionId": item["executionId"],
                 "state": state if state in {"open", "merged", "closed"} else "open"}
        if "planWrittenBack" in item:
            value["planWrittenBack"] = item["planWrittenBack"] is True
        result.append(value)
    return sorted(result, key=lambda value: (value["executionId"], value["state"]))
