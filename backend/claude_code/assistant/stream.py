"""Řádek stdout `claude -p --output-format stream-json` → události aplikace (docs/asistent.md §8, §11).

`map_line` je čistá funkce: dostane řádek a stav proudu (`messageId`, `sessionId`) a vrátí
seznam událostí bez `seq` a nový stav. Neznámé typy a neparsovatelné řádky se ignorují.
`control_request` (dotaz CLI na backend, §5.1) není událost; vytáhne ho `control_request(line)`.
"""

from __future__ import annotations

import json

TOOL_SUMMARY_LIMIT = 200
RESULT_SUMMARY_LIMIT = 300
PROGRESS_STEP = 2000
EMPTY_STATE = {"messageId": None, "sessionId": None, "block": None}
# Délku bloku, který se generuje (thinking, vstup nástroje), drží `state["block"]` = {kind, name, chars, index}.
_PROGRESS_DELTAS = {"thinking_delta": ("thinking", "thinking"), "input_json_delta": ("tool_input", "partial_json")}


def _short(value, limit):
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tool_summary(name, tool_input):
    """Krátký souhrn volání: u Bash příkaz, u Read/Glob/Grep cesta nebo vzor, u Skill název."""
    data = tool_input if isinstance(tool_input, dict) else {}
    if name == "Bash":
        value = data.get("command")
    elif name == "Read":
        value = data.get("file_path") or data.get("path")
    elif name in ("Glob", "Grep"):
        value = data.get("pattern")
        if value and data.get("path"):
            value = f"{value} v {data['path']}"
    elif name == "Skill":
        value = data.get("skill") or data.get("command") or data.get("name")
    else:
        value = None
    return _short(value, TOOL_SUMMARY_LIMIT) if isinstance(value, str) and value else ""


def result_summary(content):
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        text = " ".join(parts)
    else:
        text = ""
    return _short(text, RESULT_SUMMARY_LIMIT)


def _blocks(message):
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _system(item, state):
    if item.get("subtype") != "init":
        return [], state
    session = item.get("session_id")
    if isinstance(session, str) and session:
        state = {**state, "sessionId": session}
    return [{"type": "status", "state": "running"}], state


def _block_start(event, state):
    block = event.get("content_block")
    block = block if isinstance(block, dict) else {}
    kind = {"thinking": "thinking", "tool_use": "tool_input"}.get(block.get("type"))
    if kind is None:
        return {**state, "block": None}
    name = block.get("name") if kind == "tool_input" and isinstance(block.get("name"), str) else None
    return {**state, "block": {"kind": kind, "name": name, "chars": 0, "index": event.get("index")}}


def _progress_delta(delta, state):
    """Přírůstek thinking / vstupu nástroje → (události, stav); `progress` nejvýš po každých PROGRESS_STEP znacích."""
    kind, field = _PROGRESS_DELTAS[delta["type"]]
    chunk = delta.get(field)
    if not isinstance(chunk, str):
        return [], state
    block = state.get("block")
    if not isinstance(block, dict) or block.get("kind") != kind:
        block = {"kind": kind, "name": None, "chars": 0, "index": None}
    chars = block["chars"] + len(chunk)
    block = {**block, "chars": chars}
    state = {**state, "block": block}
    if chars // PROGRESS_STEP == (chars - len(chunk)) // PROGRESS_STEP:
        return [], state
    event = {"type": "progress", "messageId": state.get("messageId"), "kind": kind, "chars": chars}
    if kind == "tool_input" and block.get("name"):
        event["name"] = block["name"]
    return [event], state


def _stream_event(item, state):
    event = item.get("event")
    if not isinstance(event, dict):
        return [], state
    kind = event.get("type")
    if kind == "message_start":
        message = event.get("message")
        message_id = message.get("id") if isinstance(message, dict) else None
        return [], {**state, "messageId": message_id if isinstance(message_id, str) else None, "block": None}
    if kind == "content_block_start":
        return [], _block_start(event, state)
    if kind == "content_block_delta":
        delta = event.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
            return [{"type": "text_delta", "messageId": state.get("messageId"), "text": delta["text"]}], state
        if isinstance(delta, dict) and delta.get("type") in _PROGRESS_DELTAS:
            return _progress_delta(delta, state)
    return [], state


def _assistant(item, state):
    message = item.get("message") if isinstance(item.get("message"), dict) else {}
    message_id = message.get("id") if isinstance(message.get("id"), str) else state.get("messageId")
    events = []
    for block in _blocks(message):
        kind = block.get("type")
        if kind == "text" and isinstance(block.get("text"), str) and block["text"]:
            events.append({"type": "message", "role": "assistant", "messageId": message_id, "text": block["text"]})
        elif kind == "tool_use":
            name = block.get("name") if isinstance(block.get("name"), str) else ""
            events.append({"type": "tool_use", "id": block.get("id"), "name": name,
                           "summary": tool_summary(name, block.get("input"))})
    return events, state


def _user(item, state):
    events = []
    for block in _blocks(item.get("message")):
        if block.get("type") == "tool_result":
            events.append({"type": "tool_result", "id": block.get("tool_use_id"),
                           "ok": not bool(block.get("is_error")),
                           "summary": result_summary(block.get("content"))})
    return events, state


def _result(item, state):
    denials = item.get("permission_denials")
    is_error = bool(item.get("is_error"))
    usage = item.get("usage") if isinstance(item.get("usage"), dict) else {}
    events = [{
        "type": "turn_end",
        "durationMs": item.get("duration_ms") if isinstance(item.get("duration_ms"), (int, float)) else None,
        "usage": usage,
        "isError": is_error,
        "numTurns": item.get("num_turns") if isinstance(item.get("num_turns"), int) else None,
        "denied": len(denials) if isinstance(denials, list) else 0,
    }]
    if is_error:
        detail = item.get("result") if isinstance(item.get("result"), str) and item.get("result") else item.get("subtype")
        events.append({"type": "error", "message": _short(f"Claude Code ukončil tah chybou: {detail or 'neznámá chyba'}", 2000)})
    events.append({"type": "status", "state": "idle"})
    return events, {**state, "messageId": None}


HANDLERS = {
    "system": _system,
    "stream_event": _stream_event,
    "assistant": _assistant,
    "user": _user,
    "result": _result,
}


def control_request(line):
    """Řádek `{"type":"control_request","request_id","request":{…}}` → (request_id, request), jinak None.

    Odpověď CLI na náš `initialize` (`control_response`) se nevrací; `map_line` ji ignoruje.
    """
    try:
        item = json.loads(line)
    except (TypeError, ValueError):
        return None
    if not isinstance(item, dict) or item.get("type") != "control_request":
        return None
    request_id, request = item.get("request_id"), item.get("request")
    if not isinstance(request_id, str) or not request_id or not isinstance(request, dict):
        return None
    return request_id, request


def map_line(line, state=None):
    """Jeden řádek CLI → (seznam událostí bez seq, nový stav). Stav se nemutuje."""
    current = dict(EMPTY_STATE if state is None else state)
    try:
        item = json.loads(line)
    except (TypeError, ValueError):
        return [], current
    if not isinstance(item, dict):
        return [], current
    handler = HANDLERS.get(item.get("type"))
    if handler is None:
        return [], current
    return handler(item, current)
