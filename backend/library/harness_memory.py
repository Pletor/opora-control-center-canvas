"""Lifespan-owned delivery of native Harness facts through existing enabled role credentials."""
import hashlib
import json
import logging
import os
import threading
import time

from backend.integrations.openviking_client import OpenVikingUnavailable
from backend.library import harness_shared_memory as shared
from backend.memory import roles
from database.repositories import harness_memory as store

LOGGER = logging.getLogger(__name__)


def memory_uri(job, role):
    # Every source event has its own immutable address. A delayed old writer cannot overwrite a withdrawal.
    key = hashlib.sha256("\0".join(map(str, job["key"])).encode()).hexdigest()
    return f"viking://user/{role}/peers/{job['key'][0]}/resources/cards/{job['node']}/harness-{key}.md"


class HarnessMemory:
    def __init__(self, canvas, memory, *, clock=time.time):
        self.canvas, self.memory, self.clock = canvas, memory, clock
        self.stop, self.thread = threading.Event(), None

    def start(self):
        if os.environ.get("OPORA_HARNESS_MEMORY_WORKER", "1") == "0" or self.thread or self.stop.is_set():
            return
        self.thread = threading.Thread(target=self._loop, name="opora-harness-memory", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _loop(self):
        while not self.stop.wait(2):
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - background delivery cannot break Canvas saves
                LOGGER.warning("Harness memory delivery is unavailable; pending facts remain queued.")

    def run_once(self):
        if self.stop.is_set() or not self.memory.enabled():
            return []
        results = []
        for project in self.canvas.project_ids():
            if self.stop.is_set() or len(results) >= 8:
                break
            with self.canvas.lock_for(project):
                db = self.canvas.db_for(project)
                with db:
                    if db.in_transaction:
                        raise RuntimeError("Memory delivery must run outside a source transaction.")
                    db.execute("BEGIN IMMEDIATE")
                    job = store.claim(db, project, self.clock())
                    if job is None:
                        continue
                    if not store.current(db, job):
                        store.finish(db, job, "superseded", self.clock())
                        results.append("superseded")
                        continue
                    role = store.role(db, job)
                    if not isinstance(role, str) or roles.role(role) is None:
                        store.finish(db, job, "waiting-role", self.clock(), error="missing-registered-role")
                        results.append("waiting-role")
                        continue
                    # Pin the selected role before I/O, including retries after a lost response.
                    db.execute("UPDATE harness_memory_deliveries SET role_id=? WHERE " + store.KEY + " AND lease_owner=?",
                               (role, *job["key"], job["owner"]))
            uri, state, error = memory_uri(job, role), "submitted", ""
            is_shared = json.loads(job["payload"])["schema"] == shared.SCHEMA
            if is_shared and not shared.current(self.canvas, job):
                with self.canvas.lock_for(project), db:
                    store.finish(db, job, "superseded", self.clock())
                results.append("superseded")
                continue
            try:
                if len(job["payload"]) > 12000:
                    raise ValueError("bounded metadata exceeded")
                if self.stop.is_set() or not self.memory.enabled():
                    return results
                # Reuse the existing role-key authority. No administrator client or caller-supplied URI/key.
                client = self.memory._role_client(role)
                kind = "harness-shared" if is_shared else "harness-fixture" if json.loads(job["payload"])["schema"] == "harness.fixture-memory/1" else "harness-outcome"
                client.write(role, uri, job["payload"], tags=["opora=1", f"kind={kind}", f"project={project}"])
            except (ValueError, OSError, OpenVikingUnavailable):
                state, error = "retry", "memory-write-unavailable"
            if self.stop.is_set():
                return results  # Leave the lease for restart recovery; never touch a closing Canvas connection.
            if is_shared and not shared.current(self.canvas, job):
                state, error = "superseded", "shared-evidence-changed"
            with self.canvas.lock_for(project), db:
                changed = store.finish(db, job, state, self.clock(), error=error, role=role, uri=uri if state == "submitted" else "")
            results.append(state if changed else "lease-lost")
        return results
