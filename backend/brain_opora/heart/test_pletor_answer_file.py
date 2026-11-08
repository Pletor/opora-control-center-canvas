"""File-backed answers keep free text out of shell syntax without broadening permissions."""
import json
import subprocess
import sys

import pytest

from backend.brain_opora.heart import command, opora_heart
from backend.brain_opora.heart.test_opora_heart import Handler, server, run


def test_generated_helper_posts_exact_file_text_with_quotes_and_newlines(server, tmp_path):
    brain = tmp_path / "brain"
    command.write_config(brain, command.HeartSkills("P\n", {}, {}), tmp_path / "src")
    assert (brain / "opora_heart.py").read_bytes() == command.TOOL_FILE.read_bytes()
    text = 'Ověřené zjištění: "tenant".\r\nDruhý řádek: `quoted`; $(not executed).\n'
    (brain / "dilna" / "out" / "answer.txt").write_bytes(text.encode("utf-8"))
    result = subprocess.run([sys.executable, "-I", "opora_heart.py", "pletor-answer", "--question", "pq_1",
                             "--file", "dilna/out/answer.txt", "--ref", "rc_fact"], cwd=brain,
                            capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    assert len(Handler.calls) == 1
    assert Handler.calls[0]["body"] == {"text": text, "refs": ["rc_fact"], "unknown": False}
    assert Handler.calls[0]["path"] == "/api/pletor/questions/pq_1/answer"
    assert command.allowed_tools() == "Read,Grep,Glob,Bash(python opora_heart.py:*)"


@pytest.mark.parametrize("data", [b"", b" \r\n", b"nul\0text", b"x" * 8001, b"\xffbad"])
def test_invalid_files_fail_without_network_or_truncation(server, tmp_path, capsys, data):
    file = tmp_path / "answer.txt"
    file.write_bytes(data)
    code, output = run(capsys, "pletor-answer", "--question", "pq_1", "--file", str(file))
    assert code == 1
    assert json.loads(output)["code"] in ("pletor_answer_file", "pletor_answer_text")
    assert Handler.calls == []


def test_missing_file_and_exact_unicode_limit(server, tmp_path, capsys):
    code, output = run(capsys, "pletor-answer", "--question", "pq_1", "--file", "missing.txt")
    assert code == 1 and json.loads(output)["code"] == "pletor_answer_file"
    assert Handler.calls == []
    text = "ř" * 8000
    file = tmp_path / "answer.txt"
    file.write_bytes(text.encode("utf-8"))
    assert run(capsys, "pletor-answer", "--question", "pq_1", "--file", str(file))[0] == 0
    assert Handler.calls[0]["body"]["text"] == text


@pytest.mark.parametrize("arguments", [[], ["--text", "answer", "--file", "answer.txt"]])
def test_answer_input_requires_exactly_one_source(server, arguments):
    with pytest.raises(SystemExit) as error:
        opora_heart.main(["pletor-answer", "--question", "pq_1", *arguments])
    assert error.value.code == 2
    assert Handler.calls == []
