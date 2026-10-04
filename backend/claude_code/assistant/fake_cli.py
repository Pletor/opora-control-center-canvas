"""Falešné `claude -p` stream-json CLI jen pro testy; skutečný model se v testech nikdy nespouští.

Na každou zprávu ze stdin vypíše tvary z docs/asistent.md §11: `system/init`, `stream_event`
(message_start + text_delta), `assistant` s textem a `result`. Text zprávy řídí scénáře:
`SLEEP` tah nikdy nedokončí, `DIE` ukončí proces uprostřed tahu, `WRITE` se zeptá na Bash
s `opora_write.py` a `EDIT` na nástroj Edit (§5.1). Po `allow` zápis „provede“ (soubor
`written.txt` v cwd) a odpoví „allowed command=…“; po `deny` odpoví „denied: <zpráva>“.
`DRAFT` zapíše koncept `Write` do `$OPORA_DRAFTS_DIR/plan.json` a pak se zeptá na `--json-file`
(docs/davka-planu.md §2); `ESCAPE` zkusí `Write` přes `..` mimo adresář konceptů.
Na `control_request` initialize odpoví `control_response` jako skutečné CLI.
"""

import json
import os
import sys
import time
import uuid

WRITE_COMMAND = ('python x/opora_write.py /api/node-spec --project p --workspace w '
                 """--json '{"node": "n1", "expected_revision": 3}'""")


def emit(item):
    sys.stdout.write(json.dumps(item) + "\n")
    sys.stdout.flush()


def read_item():
    line = sys.stdin.readline()
    return json.loads(line) if line else None


def ask(turn, tool_name, tool_input):
    """Pošle dotaz na oprávnění a počká na `control_response` se stejným request_id."""
    request_id = f"req-{turn}"
    emit({"type": "control_request", "request_id": request_id, "request": {
        "subtype": "can_use_tool", "tool_name": tool_name, "display_name": tool_name, "input": tool_input,
        "description": tool_input.get("description", ""), "permission_suggestions": [], "tool_use_id": f"toolu_{turn}"}})
    while True:
        item = read_item()
        if item is None:
            sys.exit(0)
        response = item.get("response") or {}
        if item.get("type") == "control_response" and response.get("request_id") == request_id:
            return response.get("response") or {}


def permission_reply(turn, text):
    if "WRITE" in text:
        tool_input = {"command": WRITE_COMMAND, "description": "Zapíše spec karty n1"}
        answer = ask(turn, "Bash", tool_input)
    else:
        answer = ask(turn, "Edit", {"file_path": "src/app.py", "old_string": "a", "new_string": "b"})
    if answer.get("behavior") == "allow":
        with open("written.txt", "w", encoding="utf-8") as handle:
            handle.write(json.dumps(answer.get("updatedInput")))
        return "allowed command=" + str((answer.get("updatedInput") or {}).get("command"))
    return "denied: " + str(answer.get("message"))


PLAN = {"dryRun": True, "plan": {"nodes": [{"ref": "a", "kind": "area", "text": "Zadání"},
                                          {"ref": "k", "parent": "a", "blocks": [{"ref": "b", "ports": [{"ref": "ok"}]}]}],
                                "edges": [{"from": "k", "to": "@n1", "port": "next"}]}}


def draft_reply(turn, text):
    """Koncept: `Write` (backend pustí sám), soubor zapíše „CLI“, pak zápis s `--json-file`."""
    drafts = os.environ.get("OPORA_DRAFTS_DIR", "")
    path = os.path.join(drafts, "..", "escape.json") if "ESCAPE" in text else os.path.join(drafts, "plan.json")
    content = json.dumps(PLAN)
    answer = ask(turn, "Write", {"file_path": path, "content": content})
    if answer.get("behavior") != "allow":
        return "write denied: " + str(answer.get("message"))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    command = ("python x/opora_write.py /api/canvas-plan --project p --workspace w --json-file "
               f'"{path.replace(os.sep, "/")}"')
    answer = ask(f"{turn}b", "Bash", {"command": command, "description": "Dávka plánu"})
    return ("allowed " if answer.get("behavior") == "allow" else "denied: " + str(answer.get("message")))


def main(argv):
    session = argv[argv.index("--resume") + 1] if "--resume" in argv else str(uuid.uuid4())
    resume = argv[argv.index("--resume") + 1] if "--resume" in argv else "none"
    api_key = "set" if "ANTHROPIC_API_KEY" in os.environ else "unset"
    sys.stdin.reconfigure(encoding="utf-8")
    turn = 0
    while True:
        data = read_item()
        if data is None:
            return
        if data.get("type") == "control_request":
            emit({"type": "control_response", "response": {"subtype": "success", "request_id": data.get("request_id"),
                                                           "response": {"commands": []}}})
            continue
        if data.get("type") != "user":
            continue
        text = data["message"]["content"]
        turn += 1
        emit({"type": "system", "subtype": "init", "session_id": session, "apiKeySource": "none", "cwd": os.getcwd()})
        if "DIE" in text:
            sys.stderr.write("fake cli died\n")
            sys.stderr.flush()
            sys.exit(3)
        if "SLEEP" in text:
            time.sleep(120)
            continue
        message_id = f"msg_{turn}"
        emit({"type": "stream_event", "event": {"type": "message_start", "message": {"id": message_id}}})
        emit({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
                                                "delta": {"type": "text_delta", "text": "ok"}}})
        if "DRAFT" in text or "ESCAPE" in text:
            reply = draft_reply(turn, text)
        elif "WRITE" in text or "EDIT" in text:
            reply = permission_reply(turn, text)
        else:
            reply = f"resume={resume} apikey={api_key} cwd={os.path.basename(os.getcwd())} got={text}"
        emit({"type": "assistant", "message": {"id": message_id, "content": [
            {"type": "thinking", "thinking": ""}, {"type": "text", "text": reply}]}})
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1, "session_id": session,
              "duration_ms": 12, "result": reply, "permission_denials": [], "usage": {"output_tokens": 3}})


if __name__ == "__main__":
    main(sys.argv[1:])
