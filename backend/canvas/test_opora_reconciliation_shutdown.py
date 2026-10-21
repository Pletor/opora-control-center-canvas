"""Bounded shutdown fences network callbacks and project-lock waiters."""
import threading

import pytest

from backend.canvas.reconciliation_test_support import Service, data, reader, setup
from backend.canvas.test_opora_reconciliation_manager import manager


def test_shutdown_during_network_no_late_db_access(tmp_path):
    db, _repo, _jobs, _binding = setup(tmp_path / 'state.sqlite')
    entered, release = threading.Event(), threading.Event()
    def blocked(pin):
        entered.set()
        release.wait(5)
        return data(pin)
    service = Service(db)
    worker = manager(service, reader(blocked), [1000])
    thread = threading.Thread(target=worker.run_one)
    thread.start()
    assert entered.wait(2)
    worker.close()
    db.close()
    service.db_for = lambda _: pytest.fail('DB accessed after shutdown')
    release.set()
    thread.join(2)
    assert not thread.is_alive()


def test_shutdown_does_not_wait_for_external_project_lock(tmp_path):
    import time
    db, _repo, _jobs, _binding = setup(tmp_path / 'state.sqlite')
    service = Service(db)
    waiting = threading.Event()
    class WaitingLock:
        def __enter__(self):
            waiting.set()
            service.lock.acquire()
        def __exit__(self, *args):
            service.lock.release()
    service.graph_lock_for = lambda _: WaitingLock()
    worker = manager(service, reader(lambda _: pytest.fail('network after close')), [1000])
    service.lock.acquire()
    thread = threading.Thread(target=worker.run_one)
    thread.start()
    assert waiting.wait(2)
    started = time.monotonic()
    worker.close()
    assert time.monotonic() - started < 0.5
    db.close()
    service.db_for = lambda _: pytest.fail('DB accessed after close')
    service.lock.release()
    thread.join(2)
    assert not thread.is_alive()

def test_shutdown_while_finish_waits_for_project_lock(tmp_path):
    import time
    db, _repo, _jobs, _binding = setup(tmp_path / 'state.sqlite')
    service = Service(db)
    entered, release_network, waiting, armed = [threading.Event() for _ in range(4)]
    class WaitingLock:
        def __enter__(self):
            if armed.is_set():
                waiting.set()
            service.lock.acquire()
        def __exit__(self, *args):
            service.lock.release()
    service.graph_lock_for = lambda _: WaitingLock()
    def fetch(pin):
        entered.set()
        release_network.wait(3)
        return data(pin)
    worker = manager(service, reader(fetch), [1000])
    thread = threading.Thread(target=worker.run_one)
    thread.start()
    assert entered.wait(2)
    service.lock.acquire()
    armed.set()
    release_network.set()
    assert waiting.wait(2)
    started = time.monotonic()
    worker.close()
    assert time.monotonic() - started < 0.5
    db.close()
    service.db_for = lambda _: pytest.fail('finish accessed closed database')
    service.lock.release()
    thread.join(2)
    assert not thread.is_alive()
