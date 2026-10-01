import json
import sys
import threading
from pathlib import Path

from backend.claude_code.assistant import fake_cli
from backend.claude_code.assistant.session_process import SessionProcess, user_line

FAKE = str(Path(fake_cli.__file__))


def test_user_line_is_stream_json():
    line = user_line("Ahoj ✓")
    assert line.endswith("\n")
    assert json.loads(line) == {"type": "user", "message": {"role": "user", "content": "Ahoj ✓"}}


def test_reads_lines_and_reports_intentional_exit(tmp_path):
    lines, exited = [], threading.Event()
    process = SessionProcess([sys.executable, FAKE], cwd=tmp_path, env=None,
                             on_line=lambda proc, line: lines.append(json.loads(line)),
                             on_exit=lambda proc: exited.set()).start()
    process.send("Ahoj ✓")
    for _ in range(500):
        if any(item["type"] == "result" for item in lines):
            break
        threading.Event().wait(0.02)
    assert [item["type"] for item in lines] == ["system", "stream_event", "stream_event", "assistant", "result"]
    assert "got=Ahoj ✓" in lines[3]["message"]["content"][1]["text"]
    assert process.alive
    process.kill()
    assert exited.wait(10) and process.intentional and not process.alive


def test_unexpected_exit_keeps_stderr_tail(tmp_path):
    exited = threading.Event()
    process = SessionProcess([sys.executable, FAKE], cwd=tmp_path, env=None, on_line=lambda proc, line: None,
                             on_exit=lambda proc: exited.set()).start()
    process.send("DIE")
    assert exited.wait(10)
    assert not process.intentional
    assert "fake cli died" in process.stderr_tail()
