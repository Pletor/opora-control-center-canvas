"""Zámky po projektech, SQLite WAL a čtení snímkem (karta P2).

Každý souběžný krok čeká s timeoutem: zablokované vlákno nebo deadlock test shodí, nezasekne.
"""
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.canvas.canvas_service import BUSY_TIMEOUT_MS, READER_POOL_SIZE, CanvasService
from backend.canvas.graph import encode
from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
from backend.editor.canvas_versions.canvas_versions import CanvasVersions

WAIT = 5  # s; v pořádku trvá každý krok milisekundy
NODES = [{"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
         {"id": "dalsi", "parentId": None, "kind": "node", "name": "Další", "purpose": "", "x": 300, "y": 0}]


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def two_projects(service):
    """draft + prázdný projekt, oba s kartami focus a dalsi."""
    other = service.project_hub.empty_project({"name": "Druhý", "confirmed": True})["id"]
    for pid in ("draft", other):
        service.save_graph(pid, "draft", {"nodes": NODES, "edges": []}, service.view(pid, "draft")["digest"])
    return "draft", other


def save_state(service, pid, expected):
    return DesktopV3State(service).save({"project": pid, "workspace": "draft",
                                         "expectedRevision": expected, "state": default_state()})


def claim(pid, owner="agent", node="focus"):
    return {"project": pid, "workspace": "draft", "nodeId": node, "op": "claim", "owner": owner, "ttlSeconds": 60}


@pytest.fixture
def held():
    """Vlákno, které drží zámky (jako dlouhý zápis), dokud test nepustí `release`."""
    entered, release, threads = threading.Event(), threading.Event(), []

    def hold(*locks):
        def body():
            for lock in locks:
                lock.acquire()
            entered.set()
            release.wait(WAIT)
            for lock in reversed(locks):
                lock.release()
        thread = threading.Thread(target=body, daemon=True)
        threads.append(thread)
        thread.start()
        assert entered.wait(WAIT)

    yield hold
    release.set()
    for thread in threads:
        thread.join(WAIT)


def test_no_global_canvas_lock_remains(service):
    assert not hasattr(service, "lock") and not hasattr(service, "graph_lock")
    root = Path(__file__).resolve().parents[1]
    pattern = re.compile(r"\b(?:canvas|service)\.(?:graph_)?lock\b(?!_)")
    offenders = [f"{path}:{number}" for path in root.rglob("*.py") if not path.name.startswith("test_")
                 for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                 if pattern.search(line.split("#")[0])]
    assert offenders == []


def test_two_projects_have_independent_locks(service, held):
    a, b = two_projects(service)
    assert service.lock_for(a) is not service.lock_for(b)
    assert service.graph_lock_for(a) is not service.graph_lock_for(b)
    assert service.lock_for(a) is service.lock_for(a)
    held(service.graph_lock_for(a), service.lock_for(a))  # dlouhý zápis v A
    with ThreadPoolExecutor(max_workers=3) as pool:
        write_b = pool.submit(save_state, service, b, 0)
        claim_b = pool.submit(CardLeases(service).apply, claim(b))
        read_a = pool.submit(service.view, a, "draft")
        assert write_b.result(timeout=WAIT)["revision"] == 1
        assert len(claim_b.result(timeout=WAIT)["token"]) == 64
        # Čtení A jde snímkem a na zápis v A nečeká.
        assert [node["id"] for node in read_a.result(timeout=WAIT)["graph"]["nodes"]] == ["focus", "dalsi"]


def test_invalid_project_id_gets_no_lock(service):
    with pytest.raises(ValueError):
        service.lock_for("../x")
    with pytest.raises(ValueError):
        service.graph_lock_for(None)


def test_sqlite_runs_in_wal_with_busy_timeout(service):
    a, b = two_projects(service)
    for db in (service.db, service.db_for(a), service.db_for(b)):
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS
    reader = service.reader(a)
    assert reader is not service.db_for(a)
    assert reader.execute("PRAGMA query_only").fetchone()[0] == 1
    with pytest.raises(Exception, match="readonly"):
        reader.execute("UPDATE drafts SET graph=graph")


def test_short_lived_threads_do_not_grow_reader_connections(service):
    """Threadpool střídá vlákna (anyio je po 10 s nečinnosti ukončí); spojení nesmí přibývat s každým."""
    a, b = two_projects(service)
    read_a = threading.Barrier(4)

    def short_thread(index):
        pid = (a, b)[index % 2]
        with service.reading(pid):
            service.view(pid, "draft")
            if index < 4:
                read_a.wait(WAIT)  # první čtyři vlákna čtou souběžně: pool musí dát čtyři různá spojení

    threads = [threading.Thread(target=short_thread, args=(index,)) for index in range(200)]
    for start in range(0, len(threads), 4):
        batch = threads[start:start + 4]
        for thread in batch:
            thread.start()
        for thread in batch:
            thread.join(WAIT)
            assert not thread.is_alive()
    assert len(service._readers) <= 2 * READER_POOL_SIZE
    assert all(not db.in_transaction for db in service._readers)
    assert sum(len(idle) for idle in service._idle_readers.values()) == len(service._readers)
    # Vrácené spojení dál čte čerstvý snímek: změna po zápisu je vidět.
    renamed = [{**NODES[0], "name": "Přejmenované"}, NODES[1]]
    service.save_graph(a, "draft", {"nodes": renamed, "edges": []}, service.view(a, "draft")["digest"])
    seen = []
    reader = threading.Thread(target=lambda: seen.append(service.view(a, "draft")["graph"]["nodes"][0]["name"]))
    reader.start()
    reader.join(WAIT)
    assert seen == ["Přejmenované"]


def test_reader_pool_closes_connections_above_limit(service):
    pid, _ = two_projects(service)
    borrowed = [service.reader(pid) for _ in range(READER_POOL_SIZE + 3)]
    assert len({id(db) for db in borrowed}) == READER_POOL_SIZE + 3
    for db in borrowed:
        db.execute("BEGIN")
        service.release_reader(pid, db)
    assert len(service._idle_readers[pid]) == READER_POOL_SIZE
    assert sum(len(idle) for idle in service._idle_readers.values()) == len(service._readers)
    assert all(db in service._readers for db in service._idle_readers[pid])
    with pytest.raises(Exception, match="closed"):
        borrowed[-1].execute("SELECT 1")


def test_read_during_write_never_sees_uncommitted_data(service):
    pid, _ = two_projects(service)
    written, commit = threading.Event(), threading.Event()
    changed = {"nodes": [{**NODES[0], "name": "Rozpracované"}], "edges": []}

    def writer():
        db = service.db_for(pid)
        with service.lock_for(pid), db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE drafts SET graph=? WHERE id=?", (encode(changed), pid))
            written.set()
            commit.wait(WAIT)

    with ThreadPoolExecutor(max_workers=2) as pool:
        job = pool.submit(writer)
        assert written.wait(WAIT)
        during = pool.submit(service.view, pid, "draft").result(timeout=WAIT)
        assert [node["name"] for node in during["graph"]["nodes"]] == ["Ohnisko", "Další"]
        commit.set()
        job.result(timeout=WAIT)
    assert [node["name"] for node in service.view(pid, "draft")["graph"]["nodes"]] == ["Rozpracované"]


def test_versions_list_does_not_block_lease_write(service, monkeypatch):
    pid, _ = two_projects(service)
    versions = CanvasVersions(service)
    versions.save({"project": pid, "workspace": "draft", "digest": service.view(pid, "draft")["digest"], "author": "test"})
    inside, release = threading.Event(), threading.Event()
    original = CanvasVersions._summaries

    def slow(self, db, project, workspace):
        inside.set()
        release.wait(WAIT)
        return original(self, db, project, workspace)

    monkeypatch.setattr(CanvasVersions, "_summaries", slow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        listing = pool.submit(versions.list, pid, "draft")
        assert inside.wait(WAIT)
        try:
            lease = pool.submit(CardLeases(service).apply, claim(pid)).result(timeout=WAIT)
            state = pool.submit(save_state, service, pid, 0).result(timeout=WAIT)
        finally:
            release.set()
        assert len(lease["token"]) == 64 and state["revision"] == 1
        assert len(listing.result(timeout=WAIT)["versions"]) == 1


def test_writes_stay_serialized_and_revision_cas_unchanged(service):
    pid, _ = two_projects(service)
    barrier = threading.Barrier(4)

    def racer(_):
        barrier.wait(WAIT)
        try:
            return save_state(service, pid, 0)["revision"]
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [future.result(timeout=WAIT) for future in [pool.submit(racer, i) for i in range(4)]]
    assert results.count(1) == 1
    assert all("revize nesouhlasí" in item for item in results if item != 1)
    assert DesktopV3State(service).read(pid, "draft")["revision"] == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda owner: _try(CardLeases(service).apply, claim(pid, owner)), ["a", "b"]))
    assert sorted(isinstance(item, dict) for item in claims) == [False, True]


def _try(function, *args):
    try:
        return function(*args)
    except ValueError as error:
        return str(error)


def test_mixed_load_on_two_projects_has_no_deadlock(service):
    projects = two_projects(service)
    versions, leases, state = CanvasVersions(service), CardLeases(service), DesktopV3State(service)

    def worker(index):
        pid = projects[index % 2]
        for step in range(15):
            service.view(pid, "draft")
            leases.summary(pid, "draft")
            versions.list(pid, "draft")
            current = state.read(pid, "draft")["revision"]
            _try(save_state, service, pid, current)
            token = _try(leases.apply, claim(pid, f"w{index}", NODES[step % 2]["id"]))
            if isinstance(token, dict):
                leases.apply({"project": pid, "workspace": "draft", "nodeId": NODES[step % 2]["id"],
                              "op": "release", "token": token["token"]})
            if step % 5 == 0:
                _try(versions.save, {"project": pid, "workspace": "draft", "author": f"w{index}",
                                     "digest": service.view(pid, "draft")["digest"]})
        return index

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(worker, index) for index in range(6)]
        assert sorted(future.result(timeout=60) for future in futures) == list(range(6))
    for pid in projects:
        assert state.read(pid, "draft")["revision"] >= 1
