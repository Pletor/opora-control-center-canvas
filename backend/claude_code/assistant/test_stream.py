import json

from backend.claude_code.assistant.stream import EMPTY_STATE, map_line, result_summary, tool_summary


def line(item):
    return json.dumps(item)


def test_init_stores_session_and_reports_running():
    raw = line({"type": "system", "subtype": "init", "session_id": "abc", "model": "claude-haiku",
                "tools": [], "skills": ["grilling"], "slash_commands": [], "apiKeySource": "none", "cwd": "C:/p"})
    events, state = map_line(raw, EMPTY_STATE)
    assert events == [{"type": "status", "state": "running"}]
    assert state["sessionId"] == "abc"
    assert EMPTY_STATE["sessionId"] is None  # stav se nemutuje


def test_other_system_events_are_ignored():
    for subtype in ("status", "thinking_tokens"):
        assert map_line(line({"type": "system", "subtype": subtype}), EMPTY_STATE)[0] == []


def test_stream_deltas_carry_message_id():
    _, state = map_line(line({"type": "stream_event", "event": {"type": "message_start",
                                                                "message": {"id": "msg_1", "role": "assistant"}}}))
    assert state["messageId"] == "msg_1"
    events, _ = map_line(line({"type": "stream_event", "event": {
        "type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Ahoj"}}}), state)
    assert events == [{"type": "text_delta", "messageId": "msg_1", "text": "Ahoj"}]
    for kind in ("content_block_start", "content_block_stop", "message_delta", "message_stop"):
        assert map_line(line({"type": "stream_event", "event": {"type": kind}}), state)[0] == []
    thinking = {"type": "stream_event", "event": {"type": "content_block_delta",
                                                  "delta": {"type": "thinking_delta", "thinking": "x"}}}
    assert map_line(line(thinking), state)[0] == []


def test_assistant_blocks_become_message_and_tool_use():
    raw = line({"type": "assistant", "message": {"id": "msg_2", "content": [
        {"type": "thinking", "thinking": ""},
        {"type": "text", "text": "Podívám se."},
        {"type": "tool_use", "id": "tu_1", "name": "Bash",
         "input": {"command": "python .claude/skills/opora-control-center/scripts/opora_read.py view"}},
        {"type": "tool_use", "id": "tu_2", "name": "Read", "input": {"file_path": "docs/asistent.md"}},
        {"type": "tool_use", "id": "tu_3", "name": "Skill", "input": {"skill": "grilling"}},
    ]}})
    events, _ = map_line(raw, EMPTY_STATE)
    assert events[0] == {"type": "message", "role": "assistant", "messageId": "msg_2", "text": "Podívám se."}
    assert events[1] == {"type": "tool_use", "id": "tu_1", "name": "Bash",
                         "summary": "python .claude/skills/opora-control-center/scripts/opora_read.py view"}
    assert events[2]["summary"] == "docs/asistent.md"
    assert events[3]["summary"] == "grilling"
    assert len(events) == 4


def test_tool_summaries_are_short():
    assert tool_summary("Glob", {"pattern": "**/*.py"}) == "**/*.py"
    assert tool_summary("Grep", {"pattern": "def x", "path": "backend"}) == "def x v backend"
    assert len(tool_summary("Bash", {"command": "x" * 500})) == 200
    assert tool_summary("Unknown", {"a": 1}) == ""


def test_tool_result_string_and_block_list():
    raw = line({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tu_1", "content": "y" * 400, "is_error": False},
        {"type": "tool_result", "tool_use_id": "tu_2", "is_error": True,
         "content": [{"type": "text", "text": "Permission denied"}]},
    ]}})
    events, _ = map_line(raw, EMPTY_STATE)
    assert events[0]["id"] == "tu_1" and events[0]["ok"] is True and len(events[0]["summary"]) == 300
    assert events[1] == {"type": "tool_result", "id": "tu_2", "ok": False, "summary": "Permission denied"}
    assert result_summary(None) == ""


def test_result_ends_turn_and_reports_errors():
    ok = line({"type": "result", "subtype": "success", "is_error": False, "num_turns": 2, "session_id": "abc",
               "duration_ms": 1500, "result": "Hotovo", "permission_denials": [{"tool_name": "Write"}],
               "usage": {"input_tokens": 10, "output_tokens": 5}})
    events, state = map_line(ok, {"messageId": "msg_1", "sessionId": "abc"})
    assert events == [
        {"type": "turn_end", "durationMs": 1500, "usage": {"input_tokens": 10, "output_tokens": 5},
         "isError": False, "numTurns": 2, "denied": 1},
        {"type": "status", "state": "idle"},
    ]
    assert state["messageId"] is None and state["sessionId"] == "abc"
    failed = line({"type": "result", "subtype": "error_during_execution", "is_error": True,
                   "result": "Limit předplatného vyčerpán", "permission_denials": [], "usage": {}})
    events, _ = map_line(failed)
    assert [event["type"] for event in events] == ["turn_end", "error", "status"]
    assert "Limit předplatného vyčerpán" in events[1]["message"]


def test_unknown_and_broken_lines_are_ignored():
    assert map_line(line({"type": "rate_limit_event"}))[0] == []
    assert map_line("{nejde to")[0] == []
    assert map_line("[1, 2]")[0] == []


def test_control_request_is_not_an_event_but_is_extracted():
    from backend.claude_code.assistant.stream import control_request

    line = json.dumps({"type": "control_request", "request_id": "u1",
                       "request": {"subtype": "can_use_tool", "tool_name": "Bash", "input": {"command": "x"}}})
    assert control_request(line) == ("u1", {"subtype": "can_use_tool", "tool_name": "Bash", "input": {"command": "x"}})
    assert map_line(line)[0] == []
    reply = json.dumps({"type": "control_response", "response": {"subtype": "success", "request_id": "init"}})
    assert control_request(reply) is None and map_line(reply)[0] == []
    for bad in ("{", "[]", json.dumps({"type": "control_request", "request_id": "", "request": {}}),
                json.dumps({"type": "control_request", "request_id": "a", "request": "x"})):
        assert control_request(bad) is None
