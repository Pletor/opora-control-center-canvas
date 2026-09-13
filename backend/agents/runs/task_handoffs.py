"""Persistent, explicit, isolated Hermes documentation handoffs."""

import hashlib
import json
import queue
import threading
import time
import uuid
from pathlib import Path

from backend.agents.packets.context_packets import ContextPackets, redact_text
from backend.agents.runs.llm_runs import _canonical, _now
from backend.domain.graph.graph import valid_id
from backend.integrations.gitio import git

ACTIVE = {"starting", "running", "stopping", "verifying"}
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
MAX_CONTEXT_BYTES = 128_000


class TaskHandoffs:
    def __init__(self, canvas, plans):
        self.canvas, self.plans = canvas, plans
        self.packets = ContextPackets(canvas)
        # Desktop v3 snapshoty (opora.packet/1); přiřazuje aplikace, start je bez nich odmítne.
        self.desktop_v3 = None
        self.root = Path(canvas.root) / "task-handoff-workspaces"
        self.run_root = Path(canvas.root) / "task-handoff-runs"
        self.root.mkdir(exist_ok=True)
        self.run_root.mkdir(exist_ok=True)
        self.handles, self.threads, self.closed = {}, {}, False
        with canvas.lock, canvas.db:
            canvas.db.execute(
                "CREATE TABLE IF NOT EXISTS task_handoffs(id TEXT PRIMARY KEY, record TEXT NOT NULL)"
            )
            # A persisted PID cannot prove ownership after another service/process
            # opens this DB.  Recovery therefore refuses to invent a terminal state.
            for row in canvas.db.execute("SELECT id,record FROM task_handoffs").fetchall():
                record = json.loads(row["record"])
                if record["status"] in ACTIVE and not record.get("pid"):
                    record.update(
                        status="interrupted",
                        error="Runtime byl přerušen; žádný automatický restart.",
                        updatedAt=_now(),
                    )
                    canvas.db.execute(
                        "UPDATE task_handoffs SET record=? WHERE id=?",
                        (_canonical(record), row["id"]),
                    )

    def _record(self, handoff_id):
        if not isinstance(handoff_id, str) or not valid_id(handoff_id):
            raise ValueError("Neplatné ID dokumentačního běhu.")
        row = self.canvas.db.execute(
            "SELECT record FROM task_handoffs WHERE id=?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Dokumentační běh nebyl nalezen.")
        return json.loads(row[0])

    def _save(self, handoff_id, **changes):
        with self.canvas.lock:
            record = self._record(handoff_id)
            record.update(changes, updatedAt=_now())
            self.canvas.db.execute(
                "UPDATE task_handoffs SET record=? WHERE id=?", (_canonical(record), handoff_id)
            )
            self.canvas.db.commit()
            return record

    def _event(self, handoff_id, event):
        with self.canvas.lock:
            record = self._record(handoff_id)
            if len(record["events"]) >= 100:
                raise ValueError("Překročen limit událostí dokumentačního běhu.")
            self._save(
                handoff_id, events=[*record["events"], {**event, "seq": len(record["events"]) + 1}]
            )

    @staticmethod
    def _task(payload):
        if not isinstance(payload, dict) or set(payload) != {"packetId", "task"}:
            raise ValueError("Neplatný formát přípravy dokumentačního úkolu.")
        if (
            not isinstance(payload["packetId"], str)
            or not isinstance(payload["task"], str)
            or not payload["task"].strip()
            or len(payload["task"]) > 4000
        ):
            raise ValueError("Zadejte uložený paket a neprázdný úkol, nejvýše 4000 znaků.")
        return payload["task"].strip()

    def _settings(self, project):
        data = self.canvas.project_hub.settings(project)
        settings = data["settings"]
        # Dokumentační úkol nepotřebuje neprázdný plánovací goal, ale drží stejný provider/model/budget allowlist.
        self.canvas.project_hub._validate_settings(settings)
        return settings, data["revision"]

    def capabilities(self, project):
        try:
            settings, _revision = self._settings(project)
            paths = self.plans._hermes_paths()
            available = (
                not self.closed
                and paths is not None
                and paths[2] is not None
                and paths[2].is_file()
            )
            reason = (
                None
                if available
                else "Hermes Python runtime nebo platné projektové nastavení není dostupné."
            )
            return {
                "available": available,
                "reason": reason,
                "mode": "isolated_documentation",
                "provider": settings["provider"],
                "model": settings["model"],
                "budgetSeconds": settings["budgetSeconds"],
            }
        except ValueError as exc:
            return {
                "available": False,
                "reason": str(exc),
                "mode": "isolated_documentation",
                "provider": None,
                "model": None,
                "budgetSeconds": None,
            }

    @staticmethod
    def _bounded_text(value, limit=4000):
        value = redact_text(value if isinstance(value, str) else "")
        data = value.encode("utf-8")
        return value if len(data) <= limit else data[:limit].decode("utf-8", "ignore")

    def _workspace_context(self, scope, readable):
        """Use only saved DB documentation and selected graph relations."""
        project, workspace = scope["project"], scope["workspace"]
        view = self.canvas.view(project, workspace)
        by_id = {item["id"]: item for item in view["graph"]["nodes"]}
        ids = [item for item in readable if item in by_id]
        selected = set(ids)
        nodes = [
            {
                "id": node["id"],
                "parentId": node["parentId"],
                "kind": node["kind"],
                "name": self._bounded_text(node["name"]),
                "purpose": self._bounded_text(node["purpose"]),
            }
            for node in (by_id[item] for item in ids)
        ]
        edges = [
            {"id": edge["id"], "source": edge["source"], "target": edge["target"]}
            for edge in view["graph"]["edges"]
            if edge["source"] in selected and edge["target"] in selected
        ]
        marks = ",".join("?" for _ in selected) or "?"
        mapped_paths = sorted({"", *((by_id[item].get("sourceRef") or {}).get("path", "") for item in ids)})
        path_marks = ",".join("?" for _ in mapped_paths)
        args = (project, workspace, *(selected or {"__none__"}), *mapped_paths)
        rows = self.canvas.db.execute(
            "SELECT path,revision,fields,node_id,saved_at FROM workspace_documents "
            f"WHERE project=? AND workspace=? AND (node_id IN ({marks}) OR path IN ({path_marks})) "
            "ORDER BY CASE path WHEN '' THEN 0 ELSE 1 END,path",
            args,
        ).fetchall()
        documents, used = {}, 0
        for row in rows:
            fields = {
                key: self._bounded_text(value) for key, value in json.loads(row["fields"]).items()
            }
            item = {
                "path": row["path"],
                "nodeId": row["node_id"],
                "revision": row["revision"],
                "savedAt": row["saved_at"],
                "sourceStatus": "saved_snapshot_not_filesystem_verified",
                "fields": fields,
            }
            size = len(_canonical(item).encode("utf-8"))
            if used + size <= MAX_CONTEXT_BYTES:
                documents["root" if row["path"] == "" else row["path"]] = item
                used += size
        return {
            "map": {"nodes": nodes, "edges": edges},
            "workspaceDocuments": {"items": documents, "truncated": len(documents) != len(rows)},
        }

    def _full_context(self, packet, readable):
        safe = self._workspace_context(packet["scope"], readable)
        context = {
            "map": {
                "scope": packet["scope"],
                "sourceRefs": packet["sourceRefs"],
                "included": packet["included"],
                "excluded": packet["excluded"],
                "truncated": packet["truncated"],
                **safe["map"],
            },
            "documents": packet["content"],
            "workspaceDocuments": safe["workspaceDocuments"],
        }
        if len(_canonical(context).encode("utf-8")) > MAX_CONTEXT_BYTES + packet["maxBytes"]:
            raise ValueError("Úplný kontext dokumentačního úkolu překročil bezpečný limit.")
        return context

    def prepare(self, payload):
        task = self._task(payload)
        packet = self.packets.load(payload["packetId"])
        scope = packet["scope"]
        if scope["workspace"] == "main":
            raise ValueError("Dokumentační úkol nelze připravit z pouze-pro-čtení mainu.")
        settings, revision = self._settings(scope["project"])
        readable = [scope["node"]] + [
            item["nodeId"] for item in packet["included"] if item.get("kind") == "neighbor"
        ]
        readable = list(dict.fromkeys(readable))
        with self.canvas.graph_lock, self.canvas.lock:
            context = self._full_context(packet, readable)
        identity = {
            "packetId": packet["id"],
            "packetDigest": packet["digest"],
            "scope": scope,
            "task": task,
            "settings": settings,
            "configRevision": revision,
            "context": context,
        }
        handoff_id = uuid.uuid4().hex
        digest = hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()
        record = {
            "id": handoff_id,
            "digest": digest,
            "scope": scope,
            "task": task,
            "allowedFiles": ["result.md"],
            "readableNodeIds": readable,
            "contextSummary": {
                "packetId": packet["id"],
                "packetDigest": packet["digest"],
                "sizeBytes": packet["sizeBytes"],
                "included": packet["included"],
                "truncated": packet["truncated"],
            },
            "provider": settings["provider"],
            "model": settings["model"],
            "budgetSeconds": settings["budgetSeconds"],
            "settingsRevision": revision,
            "packet": packet,
            "context": context,
            "contextDigest": hashlib.sha256(_canonical(context).encode("utf-8")).hexdigest(),
            "status": "prepared",
            "events": [],
            "verification": {"passed": None},
            "result": None,
            "error": None,
            "pid": None,
            "localTreeInactive": False,
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        with self.canvas.lock, self.canvas.db:
            self.canvas.db.execute(
                "INSERT INTO task_handoffs VALUES(?,?)", (handoff_id, _canonical(record))
            )
        return self._public(record)

    def _snapshot_context(self, snapshot):
        """Kontext worker nástrojů = PŘESNÝ neměnný snapshot; documents nese celý balíček."""
        packet = snapshot["packet"]
        scope = packet["scope"]
        lineage = [packet["task"], *packet["context"]["ancestors"]] if scope["nodeId"] else []
        nodes = [
            {key: item[key] for key in ("nodeId", "parentId", "kind", "name", "purpose")}
            for item in lineage
        ]
        return {
            "map": {
                "scope": {"project": scope["project"], "workspace": scope["workspace"], "node": scope["nodeId"]},
                "snapshotId": snapshot["id"],
                "digest": snapshot["digest"],
                "schema": packet["schema"],
                "sourceManifest": packet["sourceManifest"],
                "warnings": packet["warnings"],
                "nodes": nodes,
                "edges": packet["context"]["relations"],
            },
            "documents": packet,
            "workspaceDocuments": {
                "items": {("root" if item["path"] == "" else item["path"]): item for item in packet["context"]["documents"]},
                "truncated": False,
            },
        }

    def prepare_from_snapshot(self, snapshot, task):
        """Připraví dokumentační běh nad neměnným Desktop v3 snapshotem; nikdy nespouští."""
        if not isinstance(task, str) or not task.strip() or len(task) > 4000:
            raise ValueError("Zadejte neprázdný úkol, nejvýše 4000 znaků.")
        task = task.strip()
        packet = snapshot["packet"]
        if packet.get("schema") != "opora.packet/1":
            raise ValueError("Snapshot nemá podporované schéma balíčku.")
        packet_scope = packet["scope"]
        scope = {"project": packet_scope["project"], "workspace": packet_scope["workspace"], "node": packet_scope["nodeId"]}
        if scope["workspace"] == "main":
            raise ValueError("Dokumentační úkol nelze připravit z pouze-pro-čtení mainu.")
        settings, revision = self._settings(scope["project"])
        readable = list(dict.fromkeys(item for item in [scope["node"], *(item["nodeId"] for item in packet["context"]["ancestors"])] if item))
        context = self._snapshot_context(snapshot)
        from backend.agents.packets.desktop_v3_packets import MAX_PACKET_BYTES

        if len(_canonical(context).encode("utf-8")) > MAX_CONTEXT_BYTES + MAX_PACKET_BYTES:
            raise ValueError("Úplný kontext dokumentačního úkolu překročil bezpečný limit.")
        identity = {
            "snapshotId": snapshot["id"],
            "packetDigest": snapshot["digest"],
            "scope": scope,
            "task": task,
            "settings": settings,
            "configRevision": revision,
            "context": context,
        }
        handoff_id = uuid.uuid4().hex
        digest = hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()
        record = {
            "id": handoff_id,
            "digest": digest,
            "scope": scope,
            "task": task,
            "allowedFiles": ["result.md"],
            "readableNodeIds": readable,
            "contextSummary": {
                "snapshotId": snapshot["id"],
                "packetDigest": snapshot["digest"],
                "schema": packet["schema"],
                "sizeBytes": len(_canonical(packet).encode("utf-8")),
                "sourceManifest": packet["sourceManifest"],
                "warnings": packet["warnings"],
            },
            "provider": settings["provider"],
            "model": settings["model"],
            "budgetSeconds": settings["budgetSeconds"],
            "settingsRevision": revision,
            "packetKind": "desktop-v3",
            "packet": {"id": snapshot["id"], "digest": snapshot["digest"], "kind": "desktop-v3"},
            "context": context,
            "contextDigest": hashlib.sha256(_canonical(context).encode("utf-8")).hexdigest(),
            "status": "prepared",
            "events": [],
            "verification": {"passed": None},
            "result": None,
            "error": None,
            "pid": None,
            "localTreeInactive": False,
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        with self.canvas.lock, self.canvas.db:
            self.canvas.db.execute(
                "INSERT INTO task_handoffs VALUES(?,?)", (handoff_id, _canonical(record))
            )
        return self._public(record)

    def _check_sources(self, record):
        """Stejná záruka pro oba druhy paketů: zdroje se od přípravy nesměly změnit."""
        if record.get("packetKind") == "desktop-v3":
            if self.desktop_v3 is None:
                raise ValueError("Desktop v3 snapshoty nejsou v tomto runtime dostupné.")
            snapshot = self.desktop_v3.load(
                record["packet"]["id"], record["scope"]["project"], record["scope"]["workspace"]
            )
            if self.desktop_v3.current_digest(snapshot) != record["packet"]["digest"]:
                raise ValueError("Podklady snapshotu se změnily; připravte nový náhled a snapshot.")
            expected = hashlib.sha256(_canonical(self._snapshot_context(snapshot)).encode("utf-8")).hexdigest()
            if expected != record["contextDigest"]:
                raise ValueError("Snapshot neodpovídá připravenému kontextu; připravte nový náhled.")
            return
        validation = self.packets.validate(record["packet"]["id"])
        if validation["stale"]:
            raise ValueError("Paket, mapa nebo dokumentace se změnily; připravte nový náhled.")

    def _check_context(self, record):
        if record.get("packetKind") == "desktop-v3":
            self._check_sources(record)
            return
        current_context = self._full_context(record["packet"], record["readableNodeIds"])
        if (
            hashlib.sha256(_canonical(current_context).encode("utf-8")).hexdigest()
            != record["contextDigest"]
        ):
            raise ValueError("Mapa nebo uložená dokumentace se změnily; připravte nový náhled.")

    @staticmethod
    def _public(record):
        fields = (
            "id",
            "digest",
            "scope",
            "task",
            "allowedFiles",
            "readableNodeIds",
            "contextSummary",
            "provider",
            "model",
            "budgetSeconds",
            "status",
            "events",
            "verification",
            "result",
            "error",
            "localTreeInactive",
        )
        return {key: record[key] for key in fields}

    def get(self, handoff_id):
        with self.canvas.lock:
            return self._public(self._record(handoff_id))

    def list(self, project, workspace):
        if not isinstance(project, str) or not isinstance(workspace, str):
            raise ValueError("Projekt a pracovní prostor jsou povinné.")  # noqa: TRY004 — veřejný chybový kontrakt API
        with self.canvas.lock:
            rows = [
                json.loads(row[0])
                for row in self.canvas.db.execute(
                    "SELECT record FROM task_handoffs ORDER BY rowid DESC LIMIT 100"
                )
            ]
        return {
            "runs": [
                self._public(record)
                for record in rows
                if record["scope"]["project"] == project
                and record["scope"]["workspace"] == workspace
            ][:20]
        }

    def _workspace(self, handoff_id):
        path = self.root / handoff_id
        if path.resolve() != path.absolute() or path.is_symlink():
            raise ValueError("Izolovaný pracovní prostor byl přesměrován.")
        return path

    def export(self, handoff_id):
        """Přesný redigovaný immutable snapshot, který worker dostává přes custom tools."""
        with self.canvas.lock:
            record = self._record(handoff_id)
        return {
            key: record[key]
            for key in (
                "id",
                "digest",
                "scope",
                "task",
                "allowedFiles",
                "readableNodeIds",
                "context",
                "provider",
                "model",
                "budgetSeconds",
            )
        }

    def _initialize_workspace(self, handoff_id, record, settings):
        """Připraví jen lokální soubory a Git; nikdy nespouští model."""
        path = self._workspace(handoff_id)
        if path.exists():
            raise ValueError("Izolovaný pracovní prostor již existuje.")
        path.mkdir()
        git(path, "-c", "core.longpaths=true", "init", "--initial-branch=main")
        git(path, "-c", "user.name=Opora Canvas", "-c", "user.email=canvas@localhost",
            "-c", "core.longpaths=true", "-c", "commit.gpgsign=false",
            "commit", "--allow-empty", "-m", "task: isolated documentation workspace")
        packet = {"id": handoff_id, "task": record["task"], "scope": record["scope"],
                  "context": record["context"], "settings": settings, "workspacePath": str(path)}
        run_dir = self.run_root / handoff_id
        if run_dir.exists() or run_dir.is_symlink():
            raise ValueError("Interní runtime prostor již existuje nebo byl přesměrován.")
        run_dir.mkdir()
        packet_path = run_dir / "handoff-context.json"
        packet_path.write_text(_canonical(packet), encoding="utf-8")
        return path, packet_path, packet

    def start(self, handoff_id, payload):
        if (
            not isinstance(payload, dict)
            or set(payload) != {"digest", "confirmed"}
            or payload.get("confirmed") is not True
            or not isinstance(payload["digest"], str)
        ):
            raise ValueError("Start vyžaduje přesný digest a potvrzení.")
        with self.canvas.graph_lock:
            with self.canvas.lock:
                record = self._record(handoff_id)
                if payload["digest"] != record["digest"]:
                    raise ValueError("Náhled se neshoduje; vytvořte nový dokumentační úkol.")
                if record["status"] in ACTIVE | TERMINAL:
                    return self._public(record)
                if self.closed:
                    raise ValueError("Dokumentační runtime je zavřený.")
                active = self.canvas.db.execute(
                    "SELECT 1 FROM task_handoffs WHERE json_extract(record,'$.status') IN ('starting','running','stopping','verifying')"
                ).fetchone()
                if active:
                    raise ValueError("Jiný dokumentační běh již probíhá.")
                coding = getattr(self.canvas, "coding_runs", None)
                if self.plans.list()["active"] or (coding is not None and coding.list()["active"]):
                    raise ValueError("Jiný omezený běh již probíhá.")
            self._check_sources(record)
            settings, revision = self._settings(record["scope"]["project"])
            if revision != record["settingsRevision"]:
                raise ValueError("Nastavení se změnilo; připravte nový náhled.")
            paths = self.plans._hermes_paths()
            if paths is None or paths[2] is None or not paths[2].is_file():
                raise ValueError("Hermes Python runtime není dostupný.")
            with self.canvas.lock, self.canvas.db:
                self.canvas.db.execute("BEGIN IMMEDIATE")
                record = self._record(handoff_id)
                if payload["digest"] != record["digest"]:
                    raise ValueError("Náhled se neshoduje; vytvořte nový dokumentační úkol.")
                if record["status"] in ACTIVE | TERMINAL:
                    return self._public(record)
                active = self.canvas.db.execute(
                    "SELECT 1 FROM task_handoffs WHERE id<>? AND json_extract(record,'$.status') IN ('starting','running','stopping','verifying')",
                    (handoff_id,),
                ).fetchone()
                if active or self.closed:
                    raise ValueError("Jiný dokumentační běh již probíhá nebo je runtime zavřený.")
                self._check_context(record)
                settings, revision = self._settings(record["scope"]["project"])
                if revision != record["settingsRevision"]:
                    raise ValueError("Nastavení se změnilo; připravte nový náhled.")
                record.update(status="starting", error=None, updatedAt=_now())
                self.canvas.db.execute(
                    "UPDATE task_handoffs SET record=? WHERE id=?", (_canonical(record), handoff_id)
                )
            try:
                path, packet_path, packet = self._initialize_workspace(handoff_id, record, settings)
            except Exception:
                with self.canvas.lock:
                    if self._record(handoff_id)["status"] == "starting":
                        self._save(handoff_id, status="failed", localTreeInactive=True,
                                   error="Příprava izolovaného repozitáře selhala; model nebyl spuštěn.")
                raise
            with self.canvas.lock:
                record = self._record(handoff_id)
                if record["status"] != "starting":
                    return self._public(record)
                record = self._save(handoff_id, workspacePath=str(path))
                thread = threading.Thread(
                    target=self.worker, args=(handoff_id, packet_path, packet, paths), daemon=True
                )
                self.threads[handoff_id] = thread
                thread.start()
                return self._public(record)

    def worker(self, handoff_id, packet_path, packet, paths):
        process = job = None
        messages, overflow = queue.Queue(maxsize=200), threading.Event()
        try:
            with self.canvas.lock:
                if self._record(handoff_id)["status"] != "starting":
                    return
                process, job = self.plans._spawn(
                    [
                        str(paths[2]),
                        str(Path(__file__).with_name("task_handoff_worker.py")),
                        str(packet_path),
                    ]
                )
                self.handles[handoff_id] = (process, job)
                self._save(handoff_id, status="running", pid=process.pid)
            self._event(
                handoff_id, {"kind": "process_started", "pid": process.pid, "observedAt": _now()}
            )

            def reader():
                seen = 0
                for line in iter(process.stdout.readline, b""):
                    seen += len(line)
                    if seen > 128000:
                        overflow.set()
                        return
                    if line.startswith(b"OPORA_EVENT "):
                        try:
                            messages.put_nowait(json.loads(line[12:]))
                        except (ValueError, queue.Full):
                            overflow.set()
                            return

            threading.Thread(target=reader, daemon=True).start()
            deadline = time.monotonic() + packet["settings"]["budgetSeconds"]
            while process.poll() is None or not self.plans._tree_inactive(process, job):
                while not messages.empty():
                    self._event(handoff_id, messages.get_nowait())
                if (
                    overflow.is_set()
                    or time.monotonic() >= deadline
                    or self.get(handoff_id)["status"] == "stopping"
                ):
                    inactive = self.plans._terminate(handoff_id, process, job)
                    self._save(
                        handoff_id,
                        status="cancelled" if inactive else "stopping",
                        localTreeInactive=inactive,
                        pid=None,
                        error="Běh byl zastaven nebo překročil lokální limit.",
                    )
                    return
                time.sleep(0.05)
            while not messages.empty():
                self._event(handoff_id, messages.get_nowait())
            with self.canvas.lock:
                current = self._record(handoff_id)
                if current["status"] != "running":
                    return
                if time.monotonic() >= deadline:
                    self._save(
                        handoff_id,
                        status="cancelled",
                        localTreeInactive=True,
                        pid=None,
                        error="Běh překročil lokální limit.",
                    )
                    return
                self._save(handoff_id, status="verifying")
            if process.returncode != 0:
                with self.canvas.lock:
                    if self._record(handoff_id)["status"] != "verifying":
                        return
                    self._save(
                        handoff_id,
                        status="failed",
                        error="Hermes worker selhal; podrobnosti jsou v událostech.",
                        pid=None,
                    )
                return
            path = self._workspace(handoff_id) / "result.md"
            valid = (
                path.is_file()
                and not path.is_symlink()
                and path.parent.resolve() == self._workspace(handoff_id).resolve()
                and 0 < path.stat().st_size <= 64_000
            )
            content = path.read_text(encoding="utf-8") if valid else ""
            valid = valid and bool(content.strip()) and len(content.encode("utf-8")) <= 64_000
            verification = {
                "passed": bool(valid),
                "path": "result.md",
                "reason": None
                if valid
                else "result.md chybí, je přesměrován nebo překročil limit.",
            }
            result = (
                {"content": content, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                if valid
                else None
            )
            with self.canvas.lock:
                if self._record(handoff_id)["status"] != "verifying":
                    return
                if time.monotonic() >= deadline:
                    self._save(handoff_id, status="cancelled", pid=None, localTreeInactive=True,
                               error="Lokální časový limit vypršel při ověření výsledku.")
                    return
                self._save(
                    handoff_id,
                    status="completed" if valid else "failed",
                    verification=verification,
                    result=result,
                    error=None if valid else verification["reason"],
                    pid=None,
                    localTreeInactive=True,
                )
        except Exception as exc:  # noqa: BLE001
            self._event(
                handoff_id,
                {"kind": "runtime_error", "errorType": type(exc).__name__, "observedAt": _now()},
            )
            self._save(
                handoff_id,
                status="failed",
                error="Dokumentační běh selhal; žádný automatický restart.",
                pid=None,
            )
        finally:
            inactive = (
                process is None
                or self.plans._tree_inactive(process, job)
                or self.plans._terminate(handoff_id, process, job)
            )
            if job is not None:
                job.close()
            with self.canvas.lock:
                self.handles.pop(handoff_id, None)
                self.threads.pop(handoff_id, None)
                if inactive and self._record(handoff_id)["status"] == "stopping":
                    self._save(handoff_id, status="cancelled", localTreeInactive=True, pid=None)

    def stop(self, handoff_id, payload):
        if (
            not isinstance(payload, dict)
            or set(payload) != {"confirmed"}
            or payload.get("confirmed") is not True
        ):
            raise ValueError("Stop vyžaduje explicitní potvrzení.")
        with self.canvas.lock:
            record = self._record(handoff_id)
            if record["status"] not in ACTIVE:
                return self._public(record)
            self._save(handoff_id, status="stopping")
            handle = self.handles.get(handoff_id)
            thread = self.threads.get(handoff_id)
            if handle is None and thread is None:
                return self._public(
                    self._save(handoff_id, status="cancelled", localTreeInactive=True, pid=None)
                )
        if handle:
            self.plans._terminate(handoff_id, *handle)
        thread = self.threads.get(handoff_id)
        if thread:
            thread.join(8)
        with self.canvas.lock:
            return self._public(self._record(handoff_id))

    def close(self):
        with self.canvas.lock:
            if self.closed:
                return
            self.closed = True
            active = [row["id"] for row in self.list_all() if row["status"] in ACTIVE]
        for handoff_id in active:
            self.stop(handoff_id, {"confirmed": True})

    def list_all(self):
        return [
            json.loads(row[0]) for row in self.canvas.db.execute("SELECT record FROM task_handoffs")
        ]
