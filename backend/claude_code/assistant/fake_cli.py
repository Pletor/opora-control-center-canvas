"""Falešné `claude -p` stream-json CLI jen pro testy; skutečný model se v testech nikdy nespouští.

Na každou zprávu ze stdin vypíše tvary z docs/asistent.md §11: `system/init`, `stream_event`
(message_start + text_delta), `assistant` s textem a `result`. Text zprávy řídí scénáře:
`SLEEP` tah nikdy nedokončí, `DIE` ukončí proces uprostřed tahu.
"""

import json
import os
import sys
import time
import uuid


def emit(item):
    sys.stdout.write(json.dumps(item) + "\n")
    sys.stdout.flush()


def main(argv):
    session = argv[argv.index("--resume") + 1] if "--resume" in argv else str(uuid.uuid4())
    resume = argv[argv.index("--resume") + 1] if "--resume" in argv else "none"
    api_key = "set" if "ANTHROPIC_API_KEY" in os.environ else "unset"
    sys.stdin.reconfigure(encoding="utf-8")
    turn = 0
    for line in sys.stdin:
        data = json.loads(line)
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
        reply = f"resume={resume} apikey={api_key} cwd={os.path.basename(os.getcwd())} got={text}"
        emit({"type": "assistant", "message": {"id": message_id, "content": [
            {"type": "thinking", "thinking": ""}, {"type": "text", "text": reply}]}})
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1, "session_id": session,
              "duration_ms": 12, "result": reply, "permission_denials": [], "usage": {"output_tokens": 3}})


if __name__ == "__main__":
    main(sys.argv[1:])
