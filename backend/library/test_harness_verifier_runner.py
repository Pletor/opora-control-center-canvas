"""Process-level bounded I/O plus fixture ordering, authority and cleanup failures."""
import hashlib
import subprocess
import sys
import time

import pytest

from backend.library import harness_verifier_runner as runner

IMAGE = "node@sha256:" + "a" * 64


def fixture():
    return {"plan": {"problem": "evaluation:paired-node", "cases": [
        {"id": "first", "args": ["--no-permission"], "expectedStdout": "ok\n"},
        {"id": "second", "args": [], "expectedStdout": "ok\n"}]},
        "baseline": {"id": "scripts:old", "digest": hashlib.sha256(b"old").hexdigest()},
        "candidate": {"id": "scripts:new", "digest": hashlib.sha256(b"new").hexdigest()},
        "contents": {"baseline": "old", "candidate": "new"}}


def result(stdout=b"ok\n", reason="completed", code=0):
    return {"stdout": stdout, "reason": reason, "exit": code, "duration": 12}


def test_actual_process_exact_output_and_exit():
    observed = runner._capture([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'hi\\n'); sys.exit(3)"])
    assert observed["reason"] == "completed"
    assert observed["exit"] == 3
    assert observed["stdout"] == b"hi\n"


def test_actual_process_timeout():
    observed = runner._capture([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
    assert observed["reason"] == "timeout"
    assert observed["exit"] is not None
    assert observed["duration"] < 2000


def test_timeout_with_slow_exit_after_kill_is_still_a_timeout(monkeypatch):
    # A killed process that needs longer than the whole call budget to exit (Windows under load) has still been
    # cleaned up: the bounded grace after the kill lets it finish instead of reporting cleanup-incomplete.
    class SlowExit(subprocess.Popen):
        exits_at = None

        def wait(self, timeout=None):
            # The killed process only reports its exit 0.3 s after the first wait (three times the budget).
            self.exits_at = self.exits_at or time.monotonic() + 0.3
            remaining = self.exits_at - time.monotonic()
            if timeout is not None and timeout < remaining:
                time.sleep(max(0, timeout))
                raise subprocess.TimeoutExpired(self.args, timeout)
            time.sleep(max(0, remaining))
            return super().wait(timeout)

    monkeypatch.setattr(runner.subprocess, "Popen", SlowExit)
    observed = runner._capture([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
    assert observed["reason"] == "timeout"
    assert observed["exit"] is not None


def test_process_that_never_exits_after_kill_is_cleanup_incomplete(monkeypatch):
    waits, spawned, real_wait = [], [], subprocess.Popen.wait

    class NeverExits(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            spawned.append(self)

        def wait(self, timeout=None):
            waits.append(timeout)
            raise subprocess.TimeoutExpired(self.args, timeout)

    monkeypatch.setattr(runner.subprocess, "Popen", NeverExits)
    try:
        observed = runner._capture([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
    finally:
        for process in spawned:
            process.kill()
            real_wait(process, timeout=10)
    assert observed["reason"] == "cleanup-incomplete"
    assert waits and all(0 <= value <= runner.CLEANUP_GRACE_SECONDS for value in waits)
    assert observed["duration"] < 3000


def test_actual_process_output_flood_is_bounded():
    observed = runner._capture([sys.executable, "-c", "import os; exec('while True: os.write(1,b\\\"x\\\"*8192); os.write(2,b\\\"y\\\"*8192)')"])
    assert observed["reason"] == "output-limit"
    assert len(observed["stdout"]) <= runner.OUTPUT_LIMIT
    assert observed["exit"] is not None


def test_alternation_mismatch_and_hardened_command(monkeypatch):
    calls, removed = [], []
    def capture(command, data, timeout):
        calls.append((command, data, timeout))
        return result(b"wrong" if data == b"old" else b"ok\n")
    monkeypatch.setattr(runner, "_capture", capture)
    monkeypatch.setattr(runner, "_cleanup", lambda name: removed.append(name) or True)
    report = runner.run_paired_fixture(fixture(), IMAGE, lambda: True)
    assert report["complete"] and report["cleanupComplete"]
    assert report["improvements"] == 2 and report["regressions"] == 0
    assert [trial["side"] for trial in report["trials"]] == ["baseline", "candidate", "candidate", "baseline"]
    assert [trial["reason"] for trial in report["trials"]] == ["output-mismatch", "expected-output", "expected-output", "output-mismatch"]
    assert [trial["order"] for trial in report["trials"]] == [1, 2, 3, 4]
    assert len(set(removed)) == 4
    for command, data, timeout in calls:
        assert command.index("--entrypoint=node") < command.index(IMAGE)
        assert "--network=none" in command and "--read-only" in command
        assert "--cap-drop=ALL" in command and "--security-opt=no-new-privileges" in command
        assert "--pids-limit=32" in command and "--memory=128m" in command
        assert "--memory-swap=128m" in command and "--cpus=1" in command
        assert "--pull=never" in command and "--log-driver=none" in command
        assert command[command.index("--user") + 1] == "65534:65534"
        assert command[command.index(IMAGE) + 1:command.index(IMAGE) + 3] == ["--input-type=module", "-"]
        assert not any(arg.startswith(("--env", "--volume", "--mount")) for arg in command)
        assert data in (b"old", b"new") and timeout <= 5
    assert "stdout" not in str(report) and "wrong" not in str(report)


@pytest.mark.parametrize("reason,code,clean", [("timeout", -9, True), ("output-limit", -9, True), ("completed", 125, True), ("completed", 0, False)])
def test_incomplete_stops_and_always_cleans(monkeypatch, reason, code, clean):
    calls, removals = [], []
    monkeypatch.setattr(runner, "_capture", lambda *args: calls.append(args) or result(reason=reason, code=code))
    monkeypatch.setattr(runner, "_cleanup", lambda name: removals.append(name) or clean)
    report = runner.run_paired_fixture(fixture(), IMAGE, lambda: True)
    assert len(calls) == len(removals) == 1
    assert not report["complete"] and report["unknownPairs"] == 2
    assert report["observedTrials"] == 1 and report["plannedTrials"] == 4
    assert report["cleanupComplete"] is clean
    assert all(trial["outcome"] == "unknown" for trial in report["trials"])


def test_authority_lost_after_invocation_cannot_count_success(monkeypatch):
    states = iter([True, False])
    monkeypatch.setattr(runner, "_capture", lambda *args: result())
    monkeypatch.setattr(runner, "_cleanup", lambda _: True)
    report = runner.run_paired_fixture(fixture(), IMAGE, lambda: next(states))
    assert report["observedTrials"] == 1
    assert all(trial["reason"] == "authority-not-current" for trial in report["trials"])
    assert report["improvements"] == report["regressions"] == 0


def test_cleanup_requires_successful_absence_query(monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "_capture", lambda command, **kwargs: calls.append(command) or result(stdout=b"", code=1))
    assert not runner._cleanup("own-name")
    assert calls[0] == ["docker", "rm", "--force", "own-name"]
    assert "name=^/own-name$" in calls[1]
    monkeypatch.setattr(runner, "_capture", lambda _, **kwargs: result(stdout=b""))
    assert runner._cleanup("own-name")
    monkeypatch.setattr(runner, "_capture", lambda _, **kwargs: result(stdout=b"own-name\n"))
    assert not runner._cleanup("own-name")


def test_unpinned_image_or_code_never_launches(monkeypatch):
    monkeypatch.setattr(runner, "_capture", lambda *_: pytest.fail("must not launch"))
    with pytest.raises(ValueError, match="invalid verifier image"):
        runner.run_paired_fixture(fixture(), "node:22", lambda: True)
    tampered = fixture()
    tampered["contents"]["candidate"] = "secret tampered code"
    with pytest.raises(ValueError, match="invalid pinned fixture"):
        runner.run_paired_fixture(tampered, IMAGE, lambda: True)


def test_budget_exhaustion_never_launches(monkeypatch):
    monkeypatch.setattr(runner, "BUDGET_SECONDS", 0)
    monkeypatch.setattr(runner, "_capture", lambda *_: pytest.fail("must not launch"))
    report = runner.run_paired_fixture(fixture(), IMAGE, lambda: True)
    assert report["observedTrials"] == 0 and report["unknownPairs"] == 2
    assert all(trial["reason"] == "launch-budget-exhausted" for trial in report["trials"])


def test_recovery_uses_only_exact_server_run_names(monkeypatch):
    removed = []
    monkeypatch.setattr(runner, "_cleanup", lambda name, deadline: removed.append(name) or not name.endswith("-1"))
    assert not runner.cleanup_run("b" * 32, 3)
    assert removed == [f"harness-verify-{'b' * 32}-{index}" for index in range(3)]
    with pytest.raises(ValueError):
        runner.cleanup_run("b" * 32, 17)
    with pytest.raises(ValueError):
        runner.run_paired_fixture(fixture(), IMAGE, lambda: True, "bad-run")


def test_exact_bytes_do_not_normalize_newlines_and_count_regression(monkeypatch):
    monkeypatch.setattr(runner, "_capture", lambda command, data, timeout: result(b"ok\n" if data == b"old" else b"ok\r\n"))
    monkeypatch.setattr(runner, "_cleanup", lambda _: True)
    report = runner.run_paired_fixture(fixture(), IMAGE, lambda: True, "c" * 32)
    assert report["complete"] and report["regressions"] == 2
    assert report["improvements"] == 0
    assert report["trials"][1]["outputDigest"] == hashlib.sha256(b"ok\r\n").hexdigest()


def test_recovery_budget_is_shared_and_no_launch_after_deadline(monkeypatch):
    clock, calls = [0.0], []
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])
    def capture(command, **kwargs):
        calls.append(kwargs["timeout"])
        clock[0] += kwargs["timeout"]
        return result(stdout=b"", reason="timeout", code=-9)
    monkeypatch.setattr(runner, "_capture", capture)
    assert not runner.cleanup_run("d" * 32, 16)
    assert clock[0] == 30 and len(calls) == 6
    assert all(0 < timeout <= 5 for timeout in calls)
    assert not runner._cleanup("own-name", deadline=30)
    assert len(calls) == 6


def test_capture_nonpositive_budget_does_not_spawn(monkeypatch):
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: pytest.fail("must not launch"))
    assert runner._capture(["docker"], timeout=0)["reason"] == "timeout"
    assert runner._capture(["docker"], timeout=-1)["exit"] is None
