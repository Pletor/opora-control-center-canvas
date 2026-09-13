"""Bounded, proposal-only Hermes planning runs with local process containment."""

import ctypes
import hashlib
import json
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend.project_hub import MODEL_RE as IDENTIFIER

MAX_CONTEXT_CHARS = 50_000
MAX_OUTPUT_BYTES = 64 * 1024
TERMINAL = {"completed", "failed", "stopped_local", "interrupted"}
ALLOWED_PROVIDERS = {"openai-codex", "anthropic", "openrouter"}
_UNSET = object()


def _now():
    return datetime.now(UTC).isoformat()


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Kontext plánu nelze bezpečně uložit.") from exc


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _WindowsJob:
    """KILL_ON_JOB_CLOSE job. A process starts suspended until assigned."""

    CREATE_SUSPENDED = 0x00000004
    CREATE_NO_WINDOW = 0x08000000
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9
    JobObjectBasicAccountingInformation = 1

    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows Job Object není dostupný.")
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_ulonglong)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
            ]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class ACCOUNTING(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        self._accounting = ACCOUNTING
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        self.k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.k32.CreateJobObjectW.restype = wintypes.HANDLE
        self.k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.k32.SetInformationJobObject.restype = wintypes.BOOL
        self.k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.k32.AssignProcessToJobObject.restype = wintypes.BOOL
        self.k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.k32.TerminateJobObject.restype = wintypes.BOOL
        self.k32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        self.k32.QueryInformationJobObject.restype = wintypes.BOOL
        self.k32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.k32.CloseHandle.restype = wintypes.BOOL
        self.ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        self.ntdll.NtResumeProcess.restype = ctypes.c_long
        self.handle = self.k32.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("Nelze vytvořit bezpečnostní Job Object.")
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.k32.SetInformationJobObject(
            self.handle,
            self.JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            self.close()
            raise OSError("Nelze nastavit bezpečnostní Job Object.")

    def assign_and_resume(self, popen):
        handle = ctypes.c_void_p(popen._handle)
        if not self.k32.AssignProcessToJobObject(self.handle, handle):
            raise OSError("Nelze přiřadit proces do bezpečnostního Job Object.")
        if self.ntdll.NtResumeProcess(handle) != 0:
            raise OSError("Nelze bezpečně spustit plánovací proces.")

    def active_processes(self):
        info = self._accounting()
        ok = self.k32.QueryInformationJobObject(
            self.handle,
            self.JobObjectBasicAccountingInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        )
        return int(info.ActiveProcesses) if ok else None

    def terminate_wait(self, timeout=5):
        if not self.k32.TerminateJobObject(self.handle, 1):
            return False
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.active_processes() == 0:
                return True
            time.sleep(0.02)
        return self.active_processes() == 0

    def close(self):
        if getattr(self, "handle", None):
            self.k32.CloseHandle(self.handle)
            self.handle = None


class PlanRuns:
    def __init__(self, canvas, context_builder, command_builder=None, tool_probe=None):
        self.canvas = canvas
        self.context_builder = context_builder
        self.command_builder = command_builder
        self.tool_probe = tool_probe or self._zero_tool_preflight
        self.run_root = Path(canvas.root) / "llm-runs"
        self.run_root.mkdir(parents=True, exist_ok=True)
        self._handles = {}
        self._threads = {}
        self._closed = False
        with self.canvas.lock:
            self.canvas.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS llm_runs(
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace TEXT NOT NULL, layer TEXT NOT NULL,
                  digest TEXT NOT NULL, context TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL,
                  output TEXT NOT NULL DEFAULT '', provider_billing TEXT NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS llm_runs_recent ON llm_runs(updated_at DESC);
                """
            )
            columns = {row[1] for row in self.canvas.db.execute("PRAGMA table_info(llm_runs)")}
            if "output" not in columns:
                self.canvas.db.execute(
                    "ALTER TABLE llm_runs ADD COLUMN output TEXT NOT NULL DEFAULT ''"
                )
            self.canvas.db.execute(
                "UPDATE llm_runs SET status='interrupted', "
                "message='Proces skončil před dokončením.', updated_at=? "
                "WHERE status IN ('starting','running','stopping')",
                (_now(),),
            )
            self.canvas.db.commit()

    def _hermes_paths(self):
        executable = shutil.which("hermes")
        if not executable:
            return None
        cli = Path(executable).resolve()
        scripts = cli.parent
        venv = scripts.parent if scripts.name.lower() == "scripts" else None
        source = venv.parent if venv is not None else cli.parent
        python = (venv / "Scripts" / "python.exe") if venv is not None else None
        return cli, source, python

    def capabilities(self):
        injected = self.command_builder is not None
        production = os.name == "nt" and self._hermes_paths() is not None
        return {
            "available": not self._closed and (injected or production),
            "mode": "proposal_only",
            "provider_billing": "unverified",
        }

    def _context(self, project, workspace, layer):
        if not all(isinstance(x, str) and x for x in (project, workspace)) or not isinstance(
            layer, str
        ):
            raise ValueError("Neplatný rozsah plánování.")
        if not project or not workspace:
            raise ValueError("Neplatný rozsah plánování.")
        raw = self.context_builder(project, workspace, layer)
        if (
            not isinstance(raw, dict)
            or raw.get("project", {}).get("id") != project
            or raw.get("workspace") != workspace
            or raw.get("layer") != layer
        ):
            raise ValueError("Kontext plánu není konzistentní.")
        settings = raw.get("settings")
        if not isinstance(settings, dict):
            raise ValueError("Nastavení plánu chybí.")  # noqa: TRY004 - validační chyby API mají kontrakt 409.
        text = _canonical(raw)
        if len(text) > MAX_CONTEXT_CHARS:
            raise ValueError("Kontext plánu překročil bezpečný limit.")
        return raw, text

    def preview(self, project, workspace, layer):
        context, text = self._context(project, workspace, layer)
        return {"digest": _digest(text), "context": context}

    def _validate_settings(self, context):
        settings = context["settings"]
        goal = settings.get("goal")
        provider, model, budget = (
            settings.get("provider"),
            settings.get("model"),
            settings.get("budgetSeconds"),
        )
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("Cíl plánu nesmí být prázdný.")
        if (
            provider not in ALLOWED_PROVIDERS
            or not isinstance(model, str)
            or not IDENTIFIER.fullmatch(model)
        ):
            raise ValueError("Provider nebo model plánu není povolen.")
        if isinstance(budget, bool) or not isinstance(budget, int) or not 10 <= budget <= 180:
            raise ValueError("Rozpočet plánu musí být 10 až 180 sekund.")
        return settings

    def _record(self, row):
        keys = (
            "id",
            "project_id",
            "workspace",
            "layer",
            "digest",
            "status",
            "message",
            "output",
            "provider_billing",
            "created_at",
            "updated_at",
        )
        return {key: row[key] for key in keys}

    def _row(self, run_id):
        row = self.canvas.db.execute("SELECT * FROM llm_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("Plánovací běh nebyl nalezen.")
        return row

    def start(self, payload):
        exact = {"project", "workspace", "layer", "digest", "confirmed"}
        if (
            not isinstance(payload, dict)
            or set(payload) != exact
            or payload.get("confirmed") is not True
        ):
            raise ValueError("Neplatné potvrzení spuštění plánu.")
        project, workspace, layer, supplied = (
            payload[k] for k in ("project", "workspace", "layer", "digest")
        )
        if not isinstance(supplied, str):
            raise ValueError("Neplatný otisk kontextu.")  # noqa: TRY004 - validační chyby API mají kontrakt 409.
        with self.canvas.graph_lock:
            context, text = self._context(project, workspace, layer)
            settings = self._validate_settings(context)
            if _digest(text) != supplied:
                raise ValueError("Kontext plánu se změnil; vytvořte nový náhled.")
            with self.canvas.lock:
                if self._closed:
                    raise ValueError("Plánovací služba je zavřená.")
                coding = getattr(self.canvas, "coding_runs", None)
                handoffs = getattr(self.canvas, "task_handoffs", None)
                if coding is not None and coding.list()["active"]:
                    raise ValueError("Jiný coding běh již probíhá.")
                if handoffs is not None and any(
                    item["status"] in {"starting", "running", "stopping", "verifying"}
                    for item in handoffs.list_all()
                ):
                    raise ValueError("Izolovaný dokumentační běh již probíhá.")
                active = self.canvas.db.execute(
                    "SELECT id FROM llm_runs WHERE status IN ('starting','running','stopping') LIMIT 1"
                ).fetchone()
                if active:
                    raise ValueError("Jiný plánovací běh již probíhá.")
                run_id, stamp = str(uuid.uuid4()), _now()
                self.canvas.db.execute(
                    "INSERT INTO llm_runs "
                    "(id,project_id,workspace,layer,digest,context,status,message,output,provider_billing,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        project,
                        workspace,
                        layer,
                        supplied,
                        text,
                        "starting",
                        "Spouštění lokálního návrhu.",
                        "",
                        "unverified",
                        stamp,
                        stamp,
                    ),
                )
                self.canvas.db.commit()
                record = self._record(self._row(run_id))
        worker = threading.Thread(
            target=self._worker, args=(run_id, context, settings), daemon=True
        )
        with self.canvas.lock:
            self._threads[run_id] = worker
        worker.start()
        return record

    def _safe_env(self):
        return {key: value for key, value in os.environ.items() if not key.startswith("HERMES_")}

    def _zero_tool_preflight(self):
        paths = self._hermes_paths()
        if paths is None:
            return False
        _cli, source, python = paths
        if python is None or not python.is_file() or not source.is_dir():
            return False
        code = (
            "from model_tools import get_tool_definitions; import sys; "
            "sys.exit(0 if len(get_tool_definitions(enabled_toolsets=['none'])) == 0 else 1)"
        )
        try:
            result = subprocess.run(
                [str(python), "-c", code],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self._safe_env(),
                cwd=str(source),
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _command(self, prompt_path, settings):
        if self.command_builder is not None:
            command = self.command_builder(prompt_path, settings)
            if (
                not isinstance(command, (list, tuple))
                or not command
                or not all(isinstance(part, str) for part in command)
            ):
                raise ValueError("Interní příkaz plánování není bezpečný.")
            return list(command)
        paths = self._hermes_paths()
        if paths is None or os.name != "nt":
            raise OSError("Hermes CLI není dostupné.")
        hermes, _source, _python = paths
        return [
            str(hermes),
            "chat",
            "--safe-mode",
            "--toolsets",
            "none",
            "--provider",
            settings["provider"],
            "--model",
            settings["model"],
            "--reasoning",
            "low",
            "--max-turns",
            "1",
            "--run-budget",
            str(settings["budgetSeconds"]),
            "--source",
            "tool",
            "--quiet",
            "--query-file",
            str(prompt_path),
        ]

    @staticmethod
    def _kill_wait(process):
        try:
            process.kill()
            process.wait(timeout=5)
            return process.poll() is not None
        except (OSError, subprocess.SubprocessError):
            return False

    def _spawn(self, command):
        common = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "cwd": str(self.run_root),
            "env": self._safe_env(),
            "shell": False,
        }
        if os.name == "nt":
            job = _WindowsJob()
            process = None
            try:
                flags = _WindowsJob.CREATE_SUSPENDED | _WindowsJob.CREATE_NO_WINDOW
                process = subprocess.Popen(command, creationflags=flags, **common)
                job.assign_and_resume(process)
                return process, job
            except Exception:
                if process is not None:
                    self._kill_wait(process)
                job.close()
                raise
        process = subprocess.Popen(command, start_new_session=True, **common)
        return process, None

    def _tree_inactive(self, process, job):
        if job is not None:
            return job.active_processes() == 0
        if process.poll() is None:
            return False
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def _terminate(self, run_id, process, job):
        try:
            if job is not None:
                return job.terminate_wait()
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except (OSError, subprocess.SubprocessError):
            return False
        end = time.monotonic() + 5
        while time.monotonic() < end:
            if self._tree_inactive(process, job):
                return True
            time.sleep(0.02)
        return self._tree_inactive(process, job)

    def _set(self, run_id, status, message, only=None, output=_UNSET):
        with self.canvas.lock:
            row = self._row(run_id)
            if only is not None and row["status"] not in only:
                return self._record(row)
            if output is _UNSET:
                sql, values = (
                    "UPDATE llm_runs SET status=?, message=?, updated_at=? WHERE id=?",
                    (status, message, _now(), run_id),
                )
            else:
                sql, values = (
                    "UPDATE llm_runs SET status=?, message=?, output=?, updated_at=? WHERE id=?",
                    (status, message, output, _now(), run_id),
                )
            self.canvas.db.execute(sql, values)
            self.canvas.db.commit()
            return self._record(self._row(run_id))

    def _row_status(self, run_id):
        with self.canvas.lock:
            return self._row(run_id)["status"]

    def _launch(self, run_id, prompt_path, settings):
        """Atomically make the last stop/close check and register a launched tree."""
        with self.canvas.lock:
            if self._closed or self._row(run_id)["status"] != "starting":
                return None
            command = self._command(prompt_path, settings)
            process, job = self._spawn(command)
            self._handles[run_id] = (process, job)
            self.canvas.db.execute(
                "UPDATE llm_runs SET status='running', message='Lokální návrh běží.', updated_at=? WHERE id=?",
                (_now(), run_id),
            )
            self.canvas.db.commit()
            return process, job

    @staticmethod
    def _start_reader(process):
        data = bytearray()
        data_lock = threading.Lock()
        over_limit = threading.Event()

        def drain():
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    return
                with data_lock:
                    remaining = MAX_OUTPUT_BYTES - len(data)
                    if remaining > 0:
                        data.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        over_limit.set()

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        return reader, data, data_lock, over_limit

    @staticmethod
    def _reader_output(reader, data, data_lock):
        reader.join()
        with data_lock:
            return bytes(data).decode("utf-8", errors="replace").strip()

    def _mark_unlaunched_stopped(self, run_id):
        self._set(
            run_id,
            "stopped_local",
            "Spuštění bylo zrušeno před vznikem lokálního procesu.",
            {"stopping"},
        )

    def _worker(self, run_id, context, settings):
        process = job = reader = None
        keep_handle = False
        try:
            if not self.tool_probe():
                self._set(
                    run_id,
                    "failed",
                    "Bezpečnostní ověření nulových nástrojů selhalo.",
                    {"starting"},
                )
                return
            prompt_path = self.run_root / run_id / "prompt.json"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(
                "Návrh pouze pro čtení. Nevytvářej soubory ani nepoužívej nástroje.\n"
                + _canonical(context),
                encoding="utf-8",
            )
            launched = self._launch(run_id, prompt_path, settings)
            if launched is None:
                self._mark_unlaunched_stopped(run_id)
                return
            process, job = launched
            reader, data, data_lock, over_limit = self._start_reader(process)
            deadline = time.monotonic() + settings["budgetSeconds"] + 5
            while True:
                status = self._row_status(run_id)
                if status == "stopping":
                    if self._terminate(run_id, process, job):
                        self._reader_output(reader, data, data_lock)
                        self._set(
                            run_id,
                            "stopped_local",
                            "Lokální procesní strom byl zastaven; billing providera není ověřen.",
                            {"stopping"},
                        )
                    else:
                        keep_handle = True
                    return
                if over_limit.is_set():
                    if self._terminate(run_id, process, job):
                        self._reader_output(reader, data, data_lock)
                        self._set(
                            run_id,
                            "failed",
                            "Procesní výstup překročil bezpečný limit.",
                            {"running"},
                        )
                    else:
                        keep_handle = True
                        self._set(
                            run_id,
                            "stopping",
                            "Lokální proces nelze bezpečně ověřit jako zastavený.",
                            {"running", "stopping"},
                        )
                    return
                if time.monotonic() > deadline:
                    if self._terminate(run_id, process, job):
                        self._reader_output(reader, data, data_lock)
                        self._set(
                            run_id,
                            "failed",
                            "Plánovací proces překročil bezpečný časový limit.",
                            {"running"},
                        )
                    else:
                        keep_handle = True
                        self._set(
                            run_id,
                            "stopping",
                            "Lokální proces nelze bezpečně ověřit jako zastavený.",
                            {"running", "stopping"},
                        )
                    return
                if process.poll() is not None and self._tree_inactive(process, job):
                    output = self._reader_output(reader, data, data_lock)
                    if over_limit.is_set():
                        self._set(
                            run_id,
                            "failed",
                            "Procesní výstup překročil bezpečný limit.",
                            {"running"},
                        )
                    elif process.returncode == 0 and output:
                        self._set(
                            run_id,
                            "completed",
                            "Návrh byl dokončen lokálně.",
                            {"running"},
                            output=output,
                        )
                    elif process.returncode == 0:
                        self._set(
                            run_id,
                            "failed",
                            "Plánovací proces neposkytl návrh.",
                            {"running"},
                        )
                    else:
                        self._set(
                            run_id,
                            "failed",
                            "Plánovací proces selhal.",
                            {"running"},
                        )
                    return
                time.sleep(0.02)
        except Exception:  # noqa: BLE001 - finální hranice containmentu musí vždy uklidit child strom.
            if (
                process is not None
                and not self._tree_inactive(process, job)
                and not self._terminate(run_id, process, job)
            ):
                keep_handle = True
                self._set(
                    run_id,
                    "stopping",
                    "Lokální proces nelze bezpečně ověřit jako zastavený.",
                    {"starting", "running", "stopping"},
                )
                return
            self._set(
                run_id,
                "failed",
                "Plánovací proces nelze bezpečně spustit.",
                {"starting", "running"},
            )
        finally:
            if not keep_handle:
                with self.canvas.lock:
                    self._handles.pop(run_id, None)
                    self._threads.pop(run_id, None)
                if job is not None:
                    job.close()

    def list(self, project=None):
        if project is not None and (not isinstance(project, str) or not project):
            raise ValueError("Neplatný projekt.")
        with self.canvas.lock:
            where, args = ("", ()) if project is None else ("WHERE project_id=?", (project,))
            rows = self.canvas.db.execute(
                f"SELECT * FROM llm_runs {where} ORDER BY updated_at DESC LIMIT 20", args
            ).fetchall()
            active = self.canvas.db.execute(
                "SELECT * FROM llm_runs WHERE status IN ('starting','running','stopping') "
                "ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            return {
                "runs": [self._record(row) for row in rows],
                "active": self._record(active) if active else None,
            }

    def stop(self, payload):
        if (
            not isinstance(payload, dict)
            or set(payload) != {"project", "runId", "confirmed"}
            or payload.get("confirmed") is not True
        ):
            raise ValueError("Neplatné potvrzení zastavení plánu.")
        project, run_id = payload["project"], payload["runId"]
        if not isinstance(project, str) or not isinstance(run_id, str):
            raise ValueError("Neplatný plánovací běh.")  # noqa: TRY004 - validační chyby API mají kontrakt 409.
        with self.canvas.lock:
            row = self._row(run_id)
            if row["project_id"] != project:
                raise ValueError("Plánovací běh nepatří projektu.")
            if row["status"] in TERMINAL:
                return self._record(row)
            self.canvas.db.execute(
                "UPDATE llm_runs SET status='stopping', message='Zastavování lokálního procesu.', updated_at=? WHERE id=?",
                (_now(), run_id),
            )
            self.canvas.db.commit()
            handle = self._handles.get(run_id)
        if handle is not None and self._terminate(run_id, *handle):
            self._set(
                run_id,
                "stopped_local",
                "Lokální procesní strom byl zastaven; billing providera není ověřen.",
                {"stopping"},
            )
        return self._row_record(run_id)

    def _row_record(self, run_id):
        with self.canvas.lock:
            return self._record(self._row(run_id))

    def close(self):
        with self.canvas.lock:
            if self._closed:
                return
            self._closed = True
            self.canvas.db.execute(
                "UPDATE llm_runs SET status='stopping', message='Zastavování lokálního procesu.', updated_at=? "
                "WHERE status IN ('starting','running')",
                (_now(),),
            )
            self.canvas.db.commit()
            active = [(run_id, *handle) for run_id, handle in self._handles.items()]
            workers = list(self._threads.values())
        for run_id, process, job in active:
            if self._terminate(run_id, process, job):
                self._set(
                    run_id,
                    "stopped_local",
                    "Lokální procesní strom byl zastaven; billing providera není ověřen.",
                    {"stopping"},
                )
        for worker in workers:
            worker.join(timeout=12)
