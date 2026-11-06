import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).with_name("opora_session_hook.py")


def run_hook(stdin):
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=False)


def test_hook_writes_session_and_excludes_opora(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    done = run_hook(json.dumps({"session_id": "s1", "transcript_path": "t.jsonl", "cwd": str(tmp_path)}))
    saved = json.loads((tmp_path / ".opora" / "session.json").read_text("utf-8"))
    assert done.returncode == 0 and saved["sessionId"] == "s1" and saved["transcriptPath"] == "t.jsonl" and saved["at"]
    assert ".opora/" in (tmp_path / ".git" / "info" / "exclude").read_text("utf-8")


def test_hook_survives_bad_input():
    assert run_hook("není json").returncode == 0
    assert run_hook("").returncode == 0
