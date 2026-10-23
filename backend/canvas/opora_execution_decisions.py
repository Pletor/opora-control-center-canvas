"""`result.decisions[]`: an execution's decisions become card decisions with its `executionId`.

A/B protokol N11 / M4: without this, OporaHub v2 decisions only survived as prose in `summary`.
Each item is a plain text (like legacy `agent-output.decisions`) or `{text, why?, alternatives?, evidence?}`
whose `text` becomes the card decision while the handoff keeps the whole object; it is stored in `state.decisions`
as `{id, text, pinned: false, path: "", nodeId, createdAt, by: "agent", executionId}` in the same
transaction as the result receipt, so a replayed result never duplicates them. The write is the
execution's own authority (enrolled cards refuse every other non-human decision write).
"""
import json
import uuid

from backend.canvas.canvas_service import now
from backend.editor.agent_memory.desktop_v3_state import MAX_TEXT, DesktopV3State, validate_state

MAX_PER_RESULT = 20


def _text(item):
    """A decision is a plain text or `{text, why?, alternatives?, evidence?}` (the handoff keeps the detail)."""
    return item.get("text") if isinstance(item, dict) else item


def validate_decisions(result):
    """Optional `result.decisions`: at most 20 non-empty texts or objects with `text`; returns the list (or [])."""
    if "decisions" not in result:
        return []
    items = result["decisions"]
    if (not isinstance(items, list) or len(items) > MAX_PER_RESULT
            or not all(isinstance(text, str) and text.strip() and len(text) <= MAX_TEXT and "\0" not in text
                       for text in map(_text, items))):
        raise ValueError(f"decisions je pole nejvýše {MAX_PER_RESULT} neprázdných textů (nebo objektů s text) do {MAX_TEXT} znaků.")
    return items


def store(canvas, db, record, texts):
    """Append the decisions to the card's state; caller holds the project locks and transaction."""
    if not texts:
        return []
    project, workspace = record["project"], record["workspace"]
    current = DesktopV3State(canvas).current(project, workspace)
    stamp = now()
    added = [{"id": uuid.uuid4().hex, "text": _text(item), "pinned": False, "path": "", "nodeId": record["nodeId"],
              "createdAt": stamp, "by": "agent", "executionId": record["executionId"]} for item in texts]
    # Shallow copy: unchanged nodes stay identical objects and are not validated again.
    state = validate_state({**current["state"], "decisions": [*current["state"]["decisions"], *added]},
                           unchanged=current["state"]["nodes"])
    db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
               (project, workspace, current["revision"] + 1, json.dumps(state, ensure_ascii=False), stamp))
    return [item["id"] for item in added]
