"""Skutečné coding běhy: schválený test repo, Hermes tools, Docker oracle."""

import hashlib
import json
import queue
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from backend.coding_tools import ALLOWED, IMAGE, ScopedFiles, cleanup_container, docker, run_tests
from backend.gitio import git
from backend.llm_runs import _canonical, _digest, _now

ACTIVE = {"starting", "running", "stopping", "verifying"}


class CodingRuns:
    def __init__(self, canvas, plans):
        self.canvas, self.plans = canvas, plans
        self.root = Path(canvas.root) / "coding-workspaces"
        self.root.mkdir(exist_ok=True)
        self.handles, self.threads = {}, {}
        self.closed = False
        with canvas.lock:
            canvas.db.executescript("""CREATE TABLE IF NOT EXISTS coding_targets(id TEXT PRIMARY KEY, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS coding_runs(id TEXT PRIMARY KEY, record TEXT NOT NULL);""")
            rows = canvas.db.execute("SELECT id,record FROM coding_runs").fetchall()
            for row in rows:
                record = json.loads(row["record"])
                if record["status"] in ACTIVE:
                    record.update(
                        status="interrupted",
                        message="Runtime byl přerušen; žádný automatický restart.",
                    )
                    canvas.db.execute(
                        "UPDATE coding_runs SET record=? WHERE id=?",
                        (_canonical(record), row["id"]),
                    )
            canvas.db.commit()

    def _target(self, target_id):
        if not isinstance(target_id, str) or not re.fullmatch(r"[a-f0-9]{32}", target_id):
            raise ValueError("Neplatný coding workspace.")
        with self.canvas.lock:
            row = self.canvas.db.execute(
                "SELECT record FROM coding_targets WHERE id=?", (target_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Coding workspace nebyl nalezen.")
        target = json.loads(row[0])
        path = self.root / target_id
        if path.resolve() != path.absolute() or self.root.resolve() != self.root.absolute():
            raise ValueError("Coding workspace byl přesměrován.")
        if (
            git(path, "branch", "--show-current") != target["branch"]
            or git(path, "rev-parse", "HEAD") != target["baseSha"]
        ):
            raise ValueError("Identita coding větve se změnila.")
        ScopedFiles(path).path("calculator.py")
        return target, path

    def create_target(self, payload):
        if (
            set(payload) != {"project", "workspace", "layer", "confirmed"}
            or payload["confirmed"] is not True
        ):
            raise ValueError(
                "Potvrďte vytvoření izolovaného testovacího repo; vlastní cesty nepřijímáme."
            )
        self.plans.preview(payload["project"], payload["workspace"], payload["layer"])
        target_id = uuid.uuid4().hex
        path = self.root / target_id
        path.mkdir()
        (path / "calculator.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
        git(path, "init", "--initial-branch=main")
        git(path, "add", "--", "calculator.py")
        git(
            path,
            "-c",
            "user.name=Opora Canvas",
            "-c",
            "user.email=canvas@localhost",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "fixture: addition oracle baseline",
        )
        base = git(path, "rev-parse", "HEAD")
        branch = "work/" + target_id
        git(path, "branch", branch)
        git(path, "switch", branch)
        target = {
            "id": target_id,
            "project": payload["project"],
            "workspace": payload["workspace"],
            "layer": payload["layer"],
            "path": str(path),
            "branch": branch,
            "baseSha": base,
            "allowedFiles": ALLOWED,
            "kind": "isolated_addition_oracle",
        }
        with self.canvas.lock, self.canvas.db:
            self.canvas.db.execute(
                "INSERT INTO coding_targets VALUES(?,?)", (target_id, _canonical(target))
            )
        return target

    def preview(self, payload):
        if (
            set(payload) != {"targetId", "task"}
            or not isinstance(payload["task"], str)
            or not payload["task"].strip()
            or len(payload["task"]) > 4000
        ):
            raise ValueError("Zadejte bounded úkol, nejvýše 4000 znaků.")
        target, path = self._target(payload["targetId"])
        context = self.plans.preview(target["project"], target["workspace"], target["layer"])[
            "context"
        ]
        context["policy"] = {
            "purpose": "coding_sandbox",
            "allowedFiles": ALLOWED,
            "hostShell": False,
            "tests": "immutable Docker addition oracle",
            "network": False,
            "automaticWrites": True,
        }
        packet = {
            "targetId": target["id"],
            "targetPath": str(path),
            "baseSha": target["baseSha"],
            "sourceSha256": hashlib.sha256((path / "calculator.py").read_bytes()).hexdigest(),
            "task": payload["task"],
            "context": context,
        }
        return {**packet, "digest": _digest(_canonical(packet))}

    def capabilities(self):
        return {
            "mode": "coding_sandbox",
            "hermesInstalled": self.plans._hermes_paths() is not None,
            "testImage": IMAGE,
            "allowedFiles": ALLOWED,
            "contract": "Izolovaný Python addition oracle; žádný obecný host shell ani zápis do připojeného zdroje.",
        }

    def _record(self, run_id):
        row = self.canvas.db.execute(
            "SELECT record FROM coding_runs WHERE id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Coding běh nebyl nalezen.")
        return json.loads(row[0])

    def update(self, run_id, **changes):
        with self.canvas.lock, self.canvas.db:
            value = self._record(run_id)
            value.update(changes, updatedAt=_now())
            self.canvas.db.execute(
                "UPDATE coding_runs SET record=? WHERE id=?", (_canonical(value), run_id)
            )
            return value

    def event(self, run_id, event):
        with self.canvas.lock:
            value = self._record(run_id)
            events = value["events"]
            if len(events) >= 100:
                raise ValueError("Překročen limit událostí.")
            self.update(run_id, events=[*events, {**event, "seq": len(events) + 1}])

    def list(self, project=None):
        with self.canvas.lock:
            rows = [
                json.loads(r[0])
                for r in self.canvas.db.execute(
                    "SELECT record FROM coding_runs ORDER BY rowid DESC LIMIT 100"
                )
            ]
            targets = [
                json.loads(r[0])
                for r in self.canvas.db.execute(
                    "SELECT record FROM coding_targets ORDER BY rowid DESC LIMIT 100"
                )
            ]
        return {
            "runs": [r for r in rows if project is None or r["project"] == project][:20],
            "active": next((r for r in rows if r["status"] in ACTIVE), None),
            "targets": [t for t in targets if project is None or t["project"] == project],
        }

    def start(self, payload):
        if (
            set(payload) != {"targetId", "task", "digest", "confirmed"}
            or payload["confirmed"] is not True
        ):
            raise ValueError("Potvrďte přesný coding scope a běh.")
        with self.canvas.graph_lock:
            packet = self.preview({k: payload[k] for k in ("targetId", "task")})
            if packet["digest"] != payload["digest"]:
                raise ValueError("Kontext nebo soubory se změnily; vytvořte nový náhled.")
            settings = self.plans._validate_settings(packet["context"])
            paths = self.plans._hermes_paths()
            if paths is None or paths[2] is None or not paths[2].is_file():
                raise ValueError("Hermes Python runtime není dostupný.")
            try:
                if docker("image", "inspect", IMAGE).returncode != 0:
                    raise ValueError(
                        "Ověřený Docker image není lokálně dostupný. Není povolen automatický pull."
                    )
            except (OSError, subprocess.SubprocessError) as exc:
                raise ValueError("Docker sandbox není dostupný.") from exc
            with self.canvas.lock:
                handoffs = getattr(self.canvas, "task_handoffs", None)
                if (
                    self.closed
                    or self.list()["active"]
                    or self.plans.list()["active"]
                    or (
                        handoffs is not None
                        and any(
                            item["status"] in {"starting", "running", "stopping", "verifying"}
                            for item in handoffs.list_all()
                        )
                    )
                ):
                    raise ValueError("Jiný běh již probíhá nebo je runtime zavřený.")
                run_id = uuid.uuid4().hex
                packet["runId"] = run_id
                directory = self.plans.run_root / run_id
                directory.mkdir()
                packet_path = directory / "coding-context.json"
                packet_path.write_text(_canonical(packet), encoding="utf-8")
                record = {
                    "id": run_id,
                    "project": packet["context"]["project"]["id"],
                    "targetId": packet["targetId"],
                    "targetPath": packet["targetPath"],
                    "digest": packet["digest"],
                    "status": "starting",
                    "message": "Spouštění skutečného Hermes coding běhu.",
                    "events": [],
                    "pid": None,
                    "localTreeInactive": False,
                    "providerBilling": "unverified",
                    "createdAt": _now(),
                    "updatedAt": _now(),
                    "result": None,
                }
                self.canvas.db.execute(
                    "INSERT INTO coding_runs VALUES(?,?)", (run_id, _canonical(record))
                )
                self.canvas.db.commit()
                worker = threading.Thread(
                    target=self.worker,
                    args=(run_id, packet_path, packet, settings, paths),
                    daemon=True,
                )
                self.threads[run_id] = worker
                worker.start()
                return record

    def worker(self, run_id, packet_path, packet, settings, paths):
        process = job = None
        messages = queue.Queue(maxsize=200)
        output_bytes = [0]
        overflow = threading.Event()
        try:
            with self.canvas.lock:
                if self.closed or self._record(run_id)["status"] != "starting":
                    return
                command = [
                    str(paths[2]),
                    str(Path(__file__).with_name("coding_worker.py")),
                    str(packet_path),
                ]
                process, job = self.plans._spawn(command)
                self.handles[run_id] = (process, job)
                self.update(run_id, status="running", pid=process.pid)
            self.event(
                run_id, {"kind": "process_started", "pid": process.pid, "observedAt": _now()}
            )

            def reader():
                for line in iter(process.stdout.readline, b""):
                    output_bytes[0] += len(line)
                    if output_bytes[0] > 128000:
                        overflow.set()
                        return
                    if line.startswith(b"OPORA_EVENT "):
                        try:
                            messages.put_nowait(json.loads(line[12:]))
                        except (ValueError, queue.Full):
                            overflow.set()
                            return

            reader_thread = threading.Thread(target=reader, daemon=True)
            reader_thread.start()
            deadline = time.monotonic() + settings["budgetSeconds"]
            while True:
                while not messages.empty():
                    self.event(run_id, messages.get_nowait())
                with self.canvas.lock:
                    stopping = self._record(run_id)["status"] == "stopping"
                if stopping or overflow.is_set() or time.monotonic() >= deadline:
                    inactive = self.plans._terminate(run_id, process, job)
                    clean = cleanup_container(run_id)
                    self.update(
                        run_id,
                        status="stopped_local" if inactive and clean else "stopping",
                        localTreeInactive=inactive,
                        message="Lokální stop / limit; účtování providera neověřeno.",
                    )
                    return
                if process.poll() is not None and self.plans._tree_inactive(process, job):
                    reader_thread.join(2)
                    while not messages.empty():
                        self.event(run_id, messages.get_nowait())
                    break
                time.sleep(0.05)
            with self.canvas.lock:
                if self._record(run_id)["status"] != "running":
                    return
                self.update(run_id, status="verifying", localTreeInactive=True, pid=None)
            if process.returncode != 0:
                self.update(
                    run_id,
                    status="failed",
                    message="Hermes worker selhal; podrobnosti ve skutečných událostech.",
                    exitCode=process.returncode,
                )
                return
            target, path = self._target(packet["targetId"])
            tests = run_tests(path, run_id)
            diff = git(
                path, "diff", "--no-ext-diff", "--no-textconv", "HEAD", "--", "calculator.py"
            )
            (packet_path.parent / "result.diff").write_text(diff, encoding="utf-8")
            with self.canvas.lock:
                value = self._record(run_id)
                tool_tests = [
                    e
                    for e in value["events"]
                    if e["kind"] == "tests_finished"
                    and e.get("sourceSha256") == tests["sourceSha256"]
                    and e.get("exitCode") == 0
                ]
                passed = bool(
                    diff
                    and tool_tests
                    and tests["exitCode"] == 0
                    and any(e["kind"] == "file_written" for e in value["events"])
                )
                result = {
                    "tests": tests,
                    "diff": diff,
                    "baseSha": target["baseSha"],
                    "changedFiles": ["calculator.py"] if diff else [],
                    "verified": passed,
                }
                (packet_path.parent / "result.json").write_text(
                    _canonical(result), encoding="utf-8"
                )
                if value["status"] == "verifying":
                    self.update(
                        run_id,
                        status="completed" if passed else "failed",
                        result=result,
                        exitCode=process.returncode,
                        message="Doložen skutečný diff a nezávislý test."
                        if passed
                        else "Výsledek nesplnil důkazy dokončení.",
                    )
        except Exception as exc:  # noqa: BLE001 - hranice workeru musí uklidit strom i při neočekávané chybě.
            self.event(
                run_id,
                {"kind": "runtime_error", "errorType": type(exc).__name__, "observedAt": _now()},
            )
            with self.canvas.lock:
                if self._record(run_id)["status"] not in {"stopped_local", "stopping"}:
                    self.update(
                        run_id,
                        status="failed",
                        message="Coding běh selhal; žádný automatický restart.",
                    )
        finally:
            inactive = (
                process is None
                or self.plans._tree_inactive(process, job)
                or self.plans._terminate(run_id, process, job)
            )
            clean = cleanup_container(run_id)
            with self.canvas.lock:
                if inactive and clean:
                    self.handles.pop(run_id, None)
                    self.threads.pop(run_id, None)
                    self.update(run_id, localTreeInactive=True, pid=None)
                    if self._record(run_id)["status"] == "stopping":
                        self.update(run_id, status="stopped_local")
                    if job is not None:
                        job.close()
                else:
                    self.update(
                        run_id,
                        status="stopping",
                        message="Ukončení lokálního stromu/kontejneru není ověřeno.",
                    )

    def stop(self, payload):
        if set(payload) != {"runId", "project", "confirmed"} or payload["confirmed"] is not True:
            raise ValueError("Neplatné potvrzení stop.")
        with self.canvas.lock:
            value = self._record(payload["runId"])
            if value["project"] != payload["project"]:
                raise ValueError("Běh nepatří projektu.")
            if value["status"] not in ACTIVE:
                return value
            self.update(value["id"], status="stopping")
            handle = self.handles.get(value["id"])
        if handle:
            self.plans._terminate(value["id"], *handle)
        cleanup_container(value["id"])
        worker = self.threads.get(value["id"])
        if worker:
            worker.join(8)
        with self.canvas.lock:
            return self._record(value["id"])

    def close(self):
        if self.closed:
            return
        self.closed = True
        for record in self.list()["runs"]:
            if record["status"] in ACTIVE:
                self.stop({"project": record["project"], "runId": record["id"], "confirmed": True})
