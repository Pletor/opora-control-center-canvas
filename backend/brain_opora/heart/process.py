"""Jeden proces dávky srdce s časovým limitem (docs/brain-heart.md §2).

Na Windows běží proces ve `WindowsJob` (KILL_ON_JOB_CLOSE): po limitu se zabije celý strom potomků
(`claude` → `python opora_heart.py` …). Jinde ve vlastní skupině procesů, kterou zabije `killpg`.
Zpráva dávky jde na stdin, výstup se čte celý (`stream-json`: událost na řádek, objekt výsledku na konci).
"""
import os
import signal
import subprocess
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


def run_process(command, *, cwd, env, stdin_text, timeout):
    """Spustí příkaz, pošle `stdin_text` a počká nejvýš `timeout` s; po limitu proces zabije (`timed_out`)."""
    job = WindowsJob() if os.name == "nt" else None
    flags = (job.CREATE_SUSPENDED | job.CREATE_NO_WINDOW) if job else 0
    process = None
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, creationflags=flags, start_new_session=job is None)
        if job is not None:
            job.assign_and_resume(process)
        try:
            out, err = process.communicate(stdin_text.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill(process, job)
            out, err = process.communicate(timeout=10)
            return Outcome(None, _text(out), _text(err), True)
        return Outcome(process.returncode, _text(out), _text(err))
    finally:
        if process is not None and process.poll() is None:
            _kill(process, job)
        if job is not None:
            job.close()
