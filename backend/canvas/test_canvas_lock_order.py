"""Pořadí zámků za běhu (karta P2, etapa Testy): git_lock → graph_lock_for → lock_for → registry_lock.

Zámky služby obalí hlídač, který si pro každé vlákno pamatuje držené zámky a zapíše každé
získání zámku nižšího pořadí pod vyšším (nebo zámku jiného projektu téže úrovně). Smíšená
zátěž dvou projektů zahrnuje i zápisy do registru (nový projekt, nastavení, verze, lease).
Jediná povolená výjimka: `ProjectHub._new` zakládá databázi nového projektu pod registry_lock;
jeho zámek ještě nikdo jiný nezná (komentář v `_new`).
"""
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
from backend.editor.canvas_versions.canvas_versions import CanvasVersions

WAIT = 60
NODES = [{"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
         {"id": "dalsi", "parentId": None, "kind": "node", "name": "Další", "purpose": "", "x": 300, "y": 0}]
GIT, GRAPH, DATA, REGISTRY = 0, 1, 2, 3


class OrderGuard:
    def __init__(self):
        self.local = threading.local()
        self.violations = []
        self.acquired = {GIT: 0, GRAPH: 0, DATA: 0, REGISTRY: 0}

    def held(self):
        if not hasattr(self.local, "stack"):
            self.local.stack = []
        return self.local.stack

    def entering(self, inner, rank, key):
        stack = self.held()
        if any(item is inner for item, _, _ in stack):
            return  # RLock znovu ve stejném vlákně
        bad = [(r, k) for _, r, k in stack if r > rank or (r == rank and k != key)]
        if bad and not any(frame.name == "_new" for frame in traceback.extract_stack()):
            self.violations.append(((rank, key), bad, "".join(traceback.format_stack(limit=8))))


class Tracked:
    def __init__(self, guard, inner, rank, key=""):
        self.guard, self.inner, self.rank, self.key = guard, inner, rank, key

    def acquire(self, blocking=True, timeout=-1):
        self.guard.entering(self.inner, self.rank, self.key)
        acquired = self.inner.acquire(blocking, timeout)
        if acquired:
            self.guard.acquired[self.rank] += 1
            self.guard.held().append((self.inner, self.rank, self.key))
        return acquired

    def release(self):
        stack = self.guard.held()
        for index in range(len(stack) - 1, -1, -1):
            if stack[index][0] is self.inner:
                del stack[index]
                break
        self.inner.release()

    def _is_owned(self):
        return self.inner._is_owned()

    __enter__ = acquire

    def __exit__(self, *exc):
        self.release()


@pytest.fixture
def guarded(tmp_path):
    service = CanvasService(tmp_path / "data")
    guard = OrderGuard()
    original = service._project_lock

    def tracked(locks, pid):
        rank = GRAPH if locks is service._graph_locks else DATA
        return Tracked(guard, original(locks, pid), rank, pid)

    service._project_lock = tracked
    service.registry_lock = Tracked(guard, service.registry_lock, REGISTRY)
    service.git_lock = Tracked(guard, service.git_lock, GIT)
    yield service, guard
    service.close()


def _try(function, *args):
    try:
        return function(*args)
    except ValueError as error:
        return str(error)


def test_lock_order_holds_under_mixed_load_with_registry_writes(guarded):
    service, guard = guarded
    hub = service.project_hub
    other = hub.empty_project({"name": "Druhý", "confirmed": True})["id"]
    projects = ("draft", other)
    for pid in projects:
        service.save_graph(pid, "draft", {"nodes": NODES, "edges": []}, service.view(pid, "draft")["digest"])
    versions, leases, state = CanvasVersions(service), CardLeases(service), DesktopV3State(service)

    def worker(index):
        pid = projects[index % 2]
        node = NODES[index % 2]["id"]
        for step in range(8):
            view = service.view(pid, "draft")
            _try(service.save_graph, pid, "draft", view["graph"], view["digest"])
            current = state.read(pid, "draft")["revision"]
            _try(state.save, {"project": pid, "workspace": "draft", "expectedRevision": current,
                              "state": default_state()})
            token = _try(leases.apply, {"project": pid, "workspace": "draft", "nodeId": node, "op": "claim",
                                        "owner": f"w{index}", "ttlSeconds": 60})
            if isinstance(token, dict):
                leases.apply({"project": pid, "workspace": "draft", "nodeId": node, "op": "release",
                              "token": token["token"]})
            settings = hub.settings(pid)
            _try(hub.save_settings, {"project": pid, "expected_revision": settings["revision"],
                                     "name": f"Projekt {index}", "settings": settings["settings"]})
            service.bootstrap()
            versions.list(pid, "draft")
            if step % 4 == 0:
                _try(versions.save, {"project": pid, "workspace": "draft", "author": f"w{index}",
                                     "digest": service.view(pid, "draft")["digest"]})
                hub.empty_project({"name": f"Nový {index}-{step}", "confirmed": True})
        return index

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(worker, index) for index in range(6)]
        assert sorted(future.result(timeout=WAIT) for future in futures) == list(range(6))
    assert guard.violations == []
    assert guard.acquired[GRAPH] and guard.acquired[DATA] and guard.acquired[REGISTRY]


def test_order_guard_reports_inverted_and_cross_project_locks(guarded):
    service, guard = guarded
    other = service.project_hub.empty_project({"name": "Druhý", "confirmed": True})["id"]
    with service.lock_for("draft"), service.graph_lock_for("draft"):
        pass
    with service.registry_lock, service.lock_for("draft"):
        pass
    with service.lock_for("draft"), service.lock_for(other):
        pass
    assert [violation[0] for violation in guard.violations] == [(GRAPH, "draft"), (DATA, "draft"), (DATA, other)]
