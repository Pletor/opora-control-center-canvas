"""Proces dávky na malém skriptu Pythonu (nikdy `claude`): stdin, výstup a zabití po limitu."""
import os
import sys

from backend.brain_opora.heart.process import run_process


def test_stdin_reaches_the_process_and_output_returns(tmp_path):
    script = "import sys; sys.stdout.write(sys.stdin.read().upper())"
    outcome = run_process([sys.executable, "-c", script], cwd=str(tmp_path), env=dict(os.environ),
                          stdin_text="ahoj srdce", timeout=30)
    assert outcome.returncode == 0 and outcome.stdout == "AHOJ SRDCE" and outcome.timed_out is False


def test_timeout_kills_the_process(tmp_path):
    outcome = run_process([sys.executable, "-c", "import time; time.sleep(60)"], cwd=str(tmp_path),
                          env=dict(os.environ), stdin_text="", timeout=1)
    assert outcome.timed_out is True and outcome.returncode is None
