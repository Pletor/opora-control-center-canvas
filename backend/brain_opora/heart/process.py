"""Jeden proces dávky srdce s časovým limitem (docs/brain-heart.md §2).

Na Windows běží proces ve `WindowsJob` (KILL_ON_JOB_CLOSE): po limitu se zabije celý strom potomků
(`claude` → `python opora_heart.py` …). Jinde ve vlastní skupině procesů, kterou zabije `killpg`.
Zpráva dávky jde na stdin, výstup se čte po řádcích (`stream-json`: událost na řádek, objekt výsledku na konci)
a každý řádek jde i do `on_line` (kroky dávky za běhu, `steps.py`).
"""
import os
import signal
import subprocess
import threading
from dataclasses import dataclass

from backend.integrations.windows_job import WindowsJob


@dataclass(frozen=True)
class Outcome:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


def _text(raw):
    return (raw or b"").decode("utf-8", errors="replace")


def _kill(process, job):
    if job is not None:
        job.terminate_wait()
    elif process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            pass
    if process.poll() is None:
        process.kill()


def _drain(stream, sink):
    for raw in iter(stream.readline, b""):
        sink(raw)


def run_process(command, *, cwd, env, stdin_text, timeout, on_line=None):
    """Spustí příkaz, pošle `stdin_text` a počká nejvýš `timeout` s; po limitu proces zabije (`timed_out`)."""
    job = WindowsJob() if os.name == "nt" else None
    flags = (job.CREATE_SUSPENDED | job.CREATE_NO_WINDOW) if job else 0
    process = None
    out, err = [], []

    def stdout_line(raw):
        out.append(raw)
        if on_line is not None:
            on_line(_text(raw))

    def feed_stdin():
        try:
            process.stdin.write(stdin_text.encode("utf-8"))
            process.stdin.close()
        except OSError:  # proces skončil dřív, než přečetl vstup
            pass

    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, creationflags=flags, start_new_session=job is None)
        if job is not None:
            job.assign_and_resume(process)
        threads = [threading.Thread(target=target, args=args, daemon=True) for target, args in
                   ((feed_stdin, ()), (_drain, (process.stdout, stdout_line)), (_drain, (process.stderr, err.append)))]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            _kill(process, job)
            timed_out = True
        for thread in threads:
            thread.join(timeout=10)
        return Outcome(None if timed_out else process.returncode, _text(b"".join(out)), _text(b"".join(err)), timed_out)
    finally:
        if process is not None and process.poll() is None:
            _kill(process, job)
        if job is not None:
            job.close()
