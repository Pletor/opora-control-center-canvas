import json

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_hub_store import MAIN_LOG, OporaHubStore, canonical, content_id

FIRST = "a" * 40
SECOND = "b" * 40


@pytest.fixture
def store(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        yield OporaHubStore(service)
    finally:
        service.close()


def record(commit_id=FIRST, subject="Zadání uzlu", workspace="draft"):
    return {"id": commit_id, "project": "draft", "workspace": workspace,
            "scope": {"kind": "node", "id": "node-1"}, "parent": None,
            "createdAt": "2026-09-18T10:00:00.000000+00:00", "specRevision": 1,
            "graphDigest": "3f1c9ab27de4", "subject": subject,
            "by": {"kind": "human", "name": "Petr"}, "pair": None}


def test_written_commit_is_a_file_named_after_its_id(store):
    store.write("draft", record())

    folder = store.folder("draft")
    assert [path.name for path in sorted(folder.iterdir())] == [f"{FIRST}.json"]
    assert json.loads((folder / f"{FIRST}.json").read_text(encoding="utf-8")) == record()
    assert store.records("draft", "draft") == [record()]


def test_existing_commit_is_never_overwritten(store):
    store.write("draft", record(subject="původní"))

    with pytest.raises(ValueError) as error:
        store.write("draft", record(subject="přepsaný"))

    assert str(error.value)
    assert store.records("draft", "draft")[0]["subject"] == "původní"


def test_records_see_only_the_asked_workspace(store):
    store.write("draft", record())
    store.write("draft", record(commit_id=SECOND, workspace="work-1"))

    assert [one["id"] for one in store.records("draft", "draft")] == [FIRST]
    assert [one["id"] for one in store.records("draft", "work-1")] == [SECOND]
    assert store.records("draft", "work-2") == []


def test_main_is_an_append_only_list_of_ids(store):
    assert store.main_ids("draft") == set()

    store.mark_main("draft", FIRST)
    store.mark_main("draft", SECOND)
    store.mark_main("draft", FIRST)

    assert store.main_ids("draft") == {FIRST, SECOND}
    log = (store.folder("draft") / MAIN_LOG).read_text(encoding="utf-8").splitlines()
    assert log == [FIRST, SECOND, FIRST]


def test_fingerprint_reads_the_content_not_the_order_of_keys():
    content = {"subject": "Zadání s háčky", "specRevision": 2}

    assert canonical(content) == '{"specRevision":2,"subject":"Zadání s háčky"}'
    assert content_id(content) == content_id({"specRevision": 2, "subject": "Zadání s háčky"})
    assert content_id(content) != content_id({**content, "specRevision": 3})
    assert len(content_id(content)) == 40
