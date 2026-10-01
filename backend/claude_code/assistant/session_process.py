"""Jeden dlouho běžící proces `claude -p` pro jednu session (docs/asistent.md §3).

Zprávy jdou na stdin jako řádky stream-json, stdout čte vlákno po řádcích. Na Windows
je proces v `WindowsJob` (KILL_ON_JOB_CLOSE), takže zabití ukončí celý strom potomků.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections import deque

from backend.integrations.windows_job import WindowsJob

STDERR_TAIL_LINES = 20


def user_line(text):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}}, ensure_ascii=False) + "\n"


class SessionProcess:
    def __init__(self, command, *, cwd, env, on_line, on_exit, popen=subprocess.Popen):
        self.command = list(command)
        self.cwd = str(cwd)
        self.env = env
        self._on_line = on_line
        self._on_exit = on_exit
        self._popen = popen
        self._process = None
        self._job = None
        self._stderr = deque(maxlen=STDERR_TAIL_LINES)
        self._write_lock = threading.Lock()
        self.intentional = False
        self.reader = None

    def start(self):
        options = {
            "cwd": self.cwd,
            "env": self.env,
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if os.name == "nt":
            self._job = WindowsJob()
            flags = WindowsJob.CREATE_SUSPENDED | WindowsJob.CREATE_NO_WINDOW
            try:
                self._process = self._popen(self.command, creationflags=flags, **options)
                self._job.assign_and_resume(self._process)
            except BaseException:
                if self._process is not None:
                    self._process.kill()
                self._job.close()
                self._job = None
                raise
        else:
            self._process = self._popen(self.command, start_new_session=True, **options)
        self._stderr_reader = threading.Thread(target=self._drain_stderr, daemon=True, name="assistant-stderr")
        self._stderr_reader.start()
        self.reader = threading.Thread(target=self._read, daemon=True, name="assistant-stdout")
        self.reader.start()
        return self

    @property
    def alive(self):
        return self._process is not None and self._process.poll() is None

    @property
    def pid(self):
        return self._process.pid if self._process is not None else None

    def stderr_tail(self):
        return "\n".join(self._stderr)

    def send(self, text):
        line = user_line(text)
        with self._write_lock:
            try:
                self._process.stdin.write(line)
                self._process.stdin.flush()
            except (OSError, ValueError) as exc:
                raise OSError("Proces asistenta nepřijal zprávu.") from exc

    def kill(self):
        """Ukončí celý strom; konec procesu pak nehlásí jako chybu tahu."""
        self.intentional = True
        process = self._process
        if process is None or process.poll() is not None:
            return
        job = self._job
        try:
            if job is not None:
                job.terminate_wait(timeout=5)
            else:
                process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass

    def _drain_stderr(self):
        try:
            for line in self._process.stderr:
                self._stderr.append(line.rstrip("\r\n")[:500])
        except (OSError, ValueError):
            pass

    def _read(self):
        try:
            for line in self._process.stdout:
                line = line.strip()
                if line:
                    try:
                        self._on_line(self, line)
                    except Exception:  # noqa: BLE001 - chyba mapování nesmí zabít čtecí vlákno
                        pass
        except (OSError, ValueError):
            pass
        try:
            self._process.wait(timeout=10)
        except subprocess.SubprocessError:
            self.kill()
        self._stderr_reader.join(timeout=2)
        job, self._job = self._job, None
        if job is not None:
            job.close()
        for stream in (self._process.stdin, self._process.stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        self._on_exit(self)
