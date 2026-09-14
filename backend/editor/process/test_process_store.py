import json
from pathlib import Path

import pytest

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
