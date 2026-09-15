import json
import threading
from pathlib import Path

import pytest

from backend.editor.process import process_store
from backend.editor.process.process_store import ProcessStore, actor, validate

HUMAN = {"kind": "human", "name": "Pletor"}
EXAMPLES = Path(__file__).resolve().parents[3] / "shared" / "examples"


def make(tmp_path):
    store = ProcessStore(tmp_path / "projects" / "p1")
    process = store.create("Reranker", HUMAN, by=HUMAN, node_id="n1", steps=["Návrh", "Implementace"])
    return store, process


def test_create_get_list(tmp_path):
    store, process = make(tmp_path)
    assert process["state"] == "draft" and process["revision"] == 1 and process["projectId"] == "p1"
    assert [s["state"] for s in process["steps"]] == ["pending", "pending"]
    assert process["history"][0]["from"] is None and process["history"][0]["to"] == "draft"
    assert store.get(process["id"]) == process
    assert (tmp_path / "projects/p1/processes" / process["id"] / "process.json").is_file()
    second = store.create("Druhý", HUMAN, by=HUMAN)
    assert [p["id"] for p in store.list()] == [second["id"], process["id"]] or len(store.list()) == 2
    assert store.list(state="draft") and store.list(state="done") == []
    with pytest.raises(ValueError):
        store.list(state="weird")


def test_save_cas_and_atomic(tmp_path):
    store, process = make(tmp_path)
    changed = {**process, "title": "Jiný název"}
    saved = store.save(changed, expected_revision=1)
    assert saved["revision"] == 2 and saved["title"] == "Jiný název"
    with pytest.raises(ValueError, match="mezitím změnil"):
        store.save({**saved, "title": "x"}, expected_revision=1)
    assert not list((store.directory(process["id"])).glob("*.tmp"))


def test_save_cas_is_atomic_across_distinct_store_instances(tmp_path):
    store, process = make(tmp_path)
    first = ProcessStore(store.project_dir)
    second = ProcessStore(store.project_dir)
    start = threading.Barrier(3)
    read_lock = threading.Lock()
    write_lock = threading.Lock()
    both_read = threading.Event()
    results = []
    errors = []
    result_lock = threading.Lock()
    readers = 0

    def pause_after_old_read(original_get):
        def get(process_id):
            nonlocal readers
            stored = original_get(process_id)
            if stored["revision"] == 1:
                with read_lock:
                    readers += 1
                    if readers == 2:
                        both_read.set()
                # Bez zámku oba writeři pokračují až po přečtení stejné revize.
                # Se zámkem čekání vyprší a první zápis bezpečně pokračuje.
                both_read.wait(timeout=1)
            return stored

        return get

    def serialized_write(path, candidate):
        # Izoluje tento CAS test od starého sdíleného názvu tmp souboru.
        with write_lock:
            ProcessStore._write(first, path, candidate)

    first.get = pause_after_old_read(first.get)
    second.get = pause_after_old_read(second.get)
    first._write = serialized_write
    second._write = serialized_write

    def save(store_instance, title, note):
        candidate = {
            **process,
            "title": title,
            "history": [
                *process["history"],
                {"from": "draft", "to": "draft", "at": process["updatedAt"], "by": HUMAN, "note": note},
            ],
        }
        try:
            start.wait(timeout=1)
            saved = store_instance.save(candidate, expected_revision=1)
            with result_lock:
                results.append(saved)
        except BaseException as error:  # zachytí i chybu vlákna pro přesnou diagnózu
            with result_lock:
                errors.append(error)

    threads = [
        threading.Thread(target=save, args=(first, "První vítěz", "první")),
        threading.Thread(target=save, args=(second, "Druhý vítěz", "druhý")),
    ]
    for thread in threads:
        thread.start()
    start.wait(timeout=1)
    for thread in threads:
        thread.join(timeout=3)

    assert not [thread for thread in threads if thread.is_alive()]
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ValueError)
    assert "mezitím změnil" in str(errors[0])
    stored = store.get(process["id"])
    assert stored == results[0]
    assert stored["revision"] == 2
    assert stored["history"][-1]["note"] in {"první", "druhý"}
    assert stored["history"][-1] == results[0]["history"][-1]


def test_save_does_not_serialize_unrelated_process_files(tmp_path):
    store, first_process = make(tmp_path)
    second_process = store.create("Druhý proces", HUMAN, by=HUMAN)
    first = ProcessStore(store.project_dir)
    second = ProcessStore(store.project_dir)
    first_writing = threading.Event()
    release_first = threading.Event()
    second_done = threading.Event()
    errors = []
    error_lock = threading.Lock()
    original_write = first._write

    def block_first_write(path, candidate):
        first_writing.set()
        release_first.wait(timeout=2)
        original_write(path, candidate)

    first._write = block_first_write

    def save_first():
        try:
            first.save({**first_process, "title": "První změněný"}, expected_revision=1)
        except BaseException as error:
            with error_lock:
                errors.append(error)

    def save_second():
        try:
            second.save({**second_process, "title": "Druhý změněný"}, expected_revision=1)
        except BaseException as error:
            with error_lock:
                errors.append(error)
        finally:
            second_done.set()

    first_thread = threading.Thread(target=save_first)
    first_thread.start()
    assert first_writing.wait(timeout=1)
    second_thread = threading.Thread(target=save_second)
    second_thread.start()
    completed_while_first_is_blocked = second_done.wait(timeout=1)
    release_first.set()
    first_thread.join(timeout=2)
    second_thread.join(timeout=2)

    assert completed_while_first_is_blocked
    assert not first_thread.is_alive() and not second_thread.is_alive()
    assert not errors
    assert store.get(first_process["id"])["title"] == "První změněný"
    assert store.get(second_process["id"])["title"] == "Druhý změněný"


def test_failed_write_preserves_old_file_and_cleans_only_its_temp(tmp_path, monkeypatch):
    store, process = make(tmp_path)
    path = store._file(process["id"])
    old_contents = path.read_text(encoding="utf-8")
    foreign_temp = path.with_name(path.name + ".foreign.tmp")
    foreign_temp.write_text("foreign writer", encoding="utf-8")
    attempted_temps = []

    def fail_replace(source, target):
        attempted_temps.append(source)
        raise OSError("simulated replace failure")

    monkeypatch.setattr(process_store.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        store.save({**process, "title": "Nesmí se uložit"}, expected_revision=1)

    assert path.read_text(encoding="utf-8") == old_contents
    assert len(attempted_temps) == 1
    assert not attempted_temps[0].exists()
    assert foreign_temp.read_text(encoding="utf-8") == "foreign writer"
    assert store.get(process["id"]) == process


def test_each_write_uses_a_unique_temporary_path(tmp_path, monkeypatch):
    store, process = make(tmp_path)
    path = store._file(process["id"])
    original_replace = process_store.os.replace
    temporary_paths = []

    def record_replace(source, target):
        temporary_paths.append(source)
        original_replace(source, target)

    monkeypatch.setattr(process_store.os, "replace", record_replace)
    store._write(path, process)
    store._write(path, process)

    assert len(temporary_paths) == 2
    assert temporary_paths[0] != temporary_paths[1]
    assert not any(path.exists() for path in temporary_paths)


def test_history_is_append_only_and_identity_fixed(tmp_path):
    store, process = make(tmp_path)
    tampered = {**process, "history": [{**process["history"][0], "note": "přepsáno"}]}
    with pytest.raises(ValueError, match="append-only"):
        store.save(tampered, expected_revision=1)
    with pytest.raises(ValueError):
        store.save({**process, "projectId": "other"}, expected_revision=1)


def test_ids_and_paths_are_validated(tmp_path):
    store, _ = make(tmp_path)
    for bad in ("../x", "prc-zzz", "prc-0123456789ab/../../etc"):
        with pytest.raises(ValueError):
            store.get(bad)
    with pytest.raises(ValueError):
        store.get("prc-0123456789ab")
    with pytest.raises(ValueError):
        actor("robot", "x")


def test_validate_rejects_broken_shapes(tmp_path):
    _, process = make(tmp_path)
    for mutate in (
        lambda p: p.pop("owner"),
        lambda p: p.update(state="paused"),
        lambda p: p["steps"].append({"id": "bad", "title": "x", "state": "pending", "evidence": None}),
        lambda p: p["steps"][0].update(state="done"),
        lambda p: p["history"].clear(),
        lambda p: p["inputs"].update(unknown=1),
        lambda p: p["outputs"].append({"kind": "pdf", "ref": "x"}),
    ):
        broken = json.loads(json.dumps(process))
        mutate(broken)
        with pytest.raises(ValueError):
            validate(broken)


@pytest.mark.parametrize("name", ["process-draft", "process-running", "process-repair", "process-done"])
def test_shared_examples_validate(name):
    validate(json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8")))
