"""Server-owned isolated fixture runner; stdout comparison uses exact UTF-8 bytes."""
from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable

CALL_SECONDS = 5
BUDGET_SECONDS = 60
OUTPUT_LIMIT = 128 * 1024
# After the run ends (exit or kill), how long cleanup may still take: on Windows a killed process can need tens
# of ms (more under load) to exit and close its pipes. The run itself still ends at its own deadline; this only
# keeps a slow but successful cleanup from being reported as "cleanup-incomplete". Bounded, so a process or
# reader that never finishes is still reported as such, at most this much past the call's deadline.
CLEANUP_GRACE_SECONDS = 1.0


def _capture(command: list[str], data: bytes = b"", timeout: float = CALL_SECONDS) -> dict:
    """Bound both output streams together; never retain raw bytes past the caller."""
    started = time.monotonic()
    if timeout <= 0:
        return {"reason": "timeout", "exit": None, "stdout": b"", "duration": 0}
    deadline = started + timeout
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=os.name != "nt")
    except (OSError, ValueError):
        return {"reason": "runtime-unavailable", "exit": None, "stdout": b"", "duration": 0}
    buffers = [bytearray(), bytearray()]
    lock, overflow = threading.Lock(), threading.Event()

    def read(stream, index):
        try:
            while chunk := stream.read(4096):
                with lock:
                    remaining = OUTPUT_LIMIT - sum(map(len, buffers))
                    buffers[index].extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        overflow.set()
                        break
        except (OSError, ValueError):
            overflow.set()
        finally:
            stream.close()

    def write():
        try:
            process.stdin.write(data)
            process.stdin.close()
        except (OSError, ValueError):
            pass

    threads = [threading.Thread(target=read, args=(process.stdout, 0), daemon=True),
               threading.Thread(target=read, args=(process.stderr, 1), daemon=True),
               threading.Thread(target=write, daemon=True)]
    for thread in threads:
        thread.start()
    reason = "completed"
    while process.poll() is None:
        if overflow.is_set() or time.monotonic() >= deadline - min(0.2, timeout / 4):
            reason = "output-limit" if overflow.is_set() else "timeout"
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            break
        time.sleep(0.005)
    settle_by = max(deadline, time.monotonic() + CLEANUP_GRACE_SECONDS)
    try:
        process.wait(timeout=max(0, settle_by - time.monotonic()))
    except subprocess.TimeoutExpired:
        reason = "cleanup-incomplete"
    for thread in threads:
        thread.join(timeout=max(0, settle_by - time.monotonic()))
    if any(thread.is_alive() for thread in threads):
        reason = "cleanup-incomplete"
    elif overflow.is_set():
        reason = "output-limit"
    return {"reason": reason, "exit": process.poll(), "stdout": bytes(buffers[0]),
            "duration": round((time.monotonic() - started) * 1000)}


def _cleanup(name: str, deadline: float | None = None) -> bool:
    deadline = time.monotonic() + 2 * CALL_SECONDS if deadline is None else deadline
    if time.monotonic() >= deadline:
        return False
    _capture(["docker", "rm", "--force", name], timeout=min(CALL_SECONDS, deadline - time.monotonic()))
    if time.monotonic() >= deadline:
        return False
    check = _capture(["docker", "ps", "--all", "--filter", f"name=^/{name}$",
                      "--format", "{{.Names}}"], timeout=min(CALL_SECONDS, deadline - time.monotonic()))
    return time.monotonic() <= deadline and check["reason"] == "completed" and check["exit"] == 0 and not check["stdout"].strip()


def _current(current: Callable[[], bool]) -> bool:
    try:
        return current() is True
    except Exception:  # noqa: BLE001 - authority callback failure must fail closed.
        return False


def cleanup_run(run_id: str, planned_trials: int) -> bool:
    """Recover only the exact names persisted by this server's abandoned run."""
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id) or type(planned_trials) is not int or not 1 <= planned_trials <= 16:
        raise ValueError("invalid verifier recovery")
    deadline, complete = time.monotonic() + 30, True
    for order in range(planned_trials):
        if time.monotonic() >= deadline:
            return False
        complete = _cleanup(f"harness-verify-{run_id}-{order}", deadline) and complete
    return complete


def run_paired_fixture(prepared: dict, image: str, current: Callable[[], bool], run_id: str | None = None) -> dict:
    """Trusted accepted plan only; Docker configuration is server-owned, never task flags.

    outputDigest is SHA-256 of complete stdout, or null for interrupted observations.
    Container exit 125/126/127 is unknown (runtime/invocation unavailable), never failure.
    """
    run_id = uuid.uuid4().hex if run_id is None else run_id
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("invalid verifier run")
    if not isinstance(image, str) or not re.fullmatch(r"node@sha256:[0-9a-f]{64}", image):
        raise ValueError("invalid verifier image")
    try:
        scripts = {side: prepared["contents"][side].encode("utf-8") for side in ("baseline", "candidate")}
        if any(hashlib.sha256(code).hexdigest() != prepared[side]["digest"] for side, code in scripts.items()):
            raise ValueError()
        cases = prepared["plan"]["cases"]
        if not 1 <= len(cases) <= 8:
            raise ValueError()
        for case in cases:
            if not isinstance(case["id"], str) or not isinstance(case["args"], list):
                raise TypeError()
            if any(not isinstance(arg, str) or "\0" in arg for arg in case["args"]):
                raise ValueError()
            case["expectedStdout"].encode("utf-8")
    except (KeyError, TypeError, AttributeError, UnicodeError, ValueError):
        raise ValueError("invalid pinned fixture") from None
    trials, stopped, cleanup_complete = [], None, True
    started = time.monotonic()
    for index, case in enumerate(cases):
        sides = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
        for side in sides:
            trial = {"case": case["id"], "side": side, "order": len(trials) + 1, "outcome": "unknown",
                     "reason": stopped, "exitCode": None, "durationMs": None, "outputDigest": None}
            if not stopped and not _current(current):
                stopped = "authority-not-current"
            if not stopped and time.monotonic() - started >= BUDGET_SECONDS:
                stopped = "launch-budget-exhausted"
            if stopped:
                trial["reason"] = stopped
                trials.append(trial)
                continue
            name = f"harness-verify-{run_id}-{len(trials)}"
            command = ["docker", "run", "--name", name, "--interactive", "--user", "65534:65534",
                       "--network=none", "--read-only", "--cap-drop=ALL",
                       "--security-opt=no-new-privileges", "--pids-limit=32", "--memory=128m",
                       "--memory-swap=128m", "--cpus=1", "--log-driver=none", "--pull=never",
                       "--entrypoint=node", image, "--input-type=module", "-", *case["args"]]
            try:
                observed = _capture(command, scripts[side], min(CALL_SECONDS, BUDGET_SECONDS - (time.monotonic() - started)))
            finally:
                cleaned = _cleanup(name)
                cleanup_complete = cleanup_complete and cleaned
            reason = observed["reason"]
            trial.update(reason=reason, exitCode=observed["exit"], durationMs=observed["duration"])
            if not cleaned or reason == "cleanup-incomplete":
                stopped = trial["reason"] = "cleanup-incomplete"
                cleanup_complete = False
            elif not _current(current):
                stopped = trial["reason"] = "authority-not-current"
            elif reason == "completed" and observed["exit"] not in (125, 126, 127):
                matches = observed["stdout"] == case["expectedStdout"].encode("utf-8")
                trial["outcome"] = "pass" if observed["exit"] == 0 and matches else "fail"
                trial["reason"] = "expected-output" if trial["outcome"] == "pass" else "output-mismatch" if observed["exit"] == 0 else "nonzero-exit"
                trial["outputDigest"] = hashlib.sha256(observed["stdout"]).hexdigest()
            else:
                stopped = trial["reason"] = reason if reason != "completed" else "runtime-unavailable"
            trials.append(trial)
    pairs = list(zip(trials[::2], trials[1::2]))
    ordered = [{trial["side"]: trial["outcome"] for trial in pair} for pair in pairs]
    return {"trials": trials, "plannedTrials": len(trials),
            "observedTrials": sum(trial["durationMs"] is not None for trial in trials),
            "improvements": sum(pair == {"baseline": "fail", "candidate": "pass"} for pair in ordered),
            "regressions": sum(pair == {"baseline": "pass", "candidate": "fail"} for pair in ordered),
            "unknownPairs": sum("unknown" in pair.values() for pair in ordered),
            "complete": all(trial["outcome"] != "unknown" for trial in trials),
            "cleanupComplete": cleanup_complete}
