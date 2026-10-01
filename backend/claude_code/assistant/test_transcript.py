import json

from backend.claude_code.assistant.transcript import find_transcript, parse_lines, read_transcript

SID = "0f8fad5b-d9cb-469f-a165-70867728950e"


def lines():
    return [json.dumps(item) for item in [
        {"type": "summary", "summary": "x"},
        {"type": "user", "isMeta": True, "message": {"role": "user", "content": "meta"}},
        {"type": "user", "message": {"role": "user", "content": "<command-name>/clear</command-name>"}},
        {"type": "user", "message": {"role": "user",
                                     "content": '<opora_context>{"projectId":"p1"}</opora_context>\n\nCo dál?'}},
        {"type": "assistant", "message": {"id": "m1", "content": [{"type": "thinking", "thinking": ""},
                                                                 {"type": "text", "text": "Podívám se."}]}},
        {"type": "assistant", "message": {"id": "m1", "content": [{"type": "tool_use", "id": "t", "name": "Read"}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t", "content": "soubor"}]}},
        {"type": "assistant", "message": {"id": "m2", "content": [{"type": "text", "text": "Hotovo."}]}},
        {"type": "assistant", "message": {"id": "m2", "content": [{"type": "text", "text": "Ještě tohle."}]}},
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Díky"}]}},
    ]] + ["{rozbité"]


def test_parse_keeps_only_user_and_assistant_text():
    assert parse_lines(lines()) == [
        {"role": "user", "text": "Co dál?"},
        {"role": "assistant", "text": "Podívám se."},
        {"role": "assistant", "text": "Hotovo.\n\nJeště tohle."},
        {"role": "user", "text": "Díky"},
    ]
    assert len(parse_lines([json.dumps({"type": "user", "message": {"content": f"m{i}"}})
                            for i in range(600)])) == 500


def test_find_and_read_from_injected_home(tmp_path):
    folder = tmp_path / ".claude" / "projects" / "C--projekt"
    folder.mkdir(parents=True)
    (folder / f"{SID}.jsonl").write_text("\n".join(lines()), encoding="utf-8")
    assert find_transcript(SID, tmp_path) == folder / f"{SID}.jsonl"
    assert read_transcript(SID, tmp_path)[0] == {"role": "user", "text": "Co dál?"}
    assert read_transcript(None, tmp_path) == []
    assert read_transcript("../../etc/passwd", tmp_path) == []
    assert read_transcript("*", tmp_path) == []
    assert read_transcript(SID.replace("0f", "1f"), tmp_path) == []
