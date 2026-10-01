import json

from backend.claude_code.assistant.event_log import EventLog, truncate_event


def test_seq_grows_and_buffer_keeps_last_events():
    log = EventLog(max_events=3)
    for index in range(5):
        log.append({"type": "text_delta", "text": str(index)})
    assert log.last_seq == 5
    assert [event["seq"] for event in log.after(0)] == [3, 4, 5]
    assert [event["seq"] for event in log.after(4)] == [5]
    assert log.after(5) == []
    # Klient z dřívějšího běhu backendu (after za koncem) dostane buffer od začátku.
    assert [event["seq"] for event in log.after(99)] == [3, 4, 5]


def test_large_event_is_truncated_with_marker():
    event = {"type": "message", "role": "assistant", "text": "á" * 70000}
    small = truncate_event(event, limit=64 * 1024)
    assert small["truncated"] is True
    assert len(json.dumps(small, ensure_ascii=False).encode("utf-8")) <= 64 * 1024
    assert small["type"] == "message" and small["role"] == "assistant"
    assert truncate_event({"type": "status", "state": "idle"}) == {"type": "status", "state": "idle"}
    stored = EventLog().append(event)
    assert stored["truncated"] is True and stored["seq"] == 1
