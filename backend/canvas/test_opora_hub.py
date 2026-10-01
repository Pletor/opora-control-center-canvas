import json

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_hub import AUTHORS, WRITERS, OporaHub
from backend.canvas.opora_hub_store import content_id

SCOPE = ("draft", "draft", "node-1")
OTHER = ("draft", "draft", "sektor-1")
DIGEST = "3f1c9ab27de4"
HUMAN = {"kind": "human", "name": "Petr"}
ORCHESTRATOR = {"kind": "orchestrator", "name": "Orchestrátor"}


@pytest.fixture
def hub(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        yield OporaHub(service)
    finally:
        service.close()


def work(subject="Zadání uzlu v revizi 3", **changes):
    payload = {"kind": "node", "specRevision": 3, "graphDigest": DIGEST,
               "subject": subject, "by": dict(HUMAN), "pair": None}
    return {**payload, **changes}


def stored(hub, commit_id):
    path = hub.store.folder("draft") / f"{commit_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_commit_lands_in_a_file_and_in_the_index(hub):
    saved = hub.commit(SCOPE, work())

    assert stored(hub, saved["id"]) == {k: v for k, v in saved.items() if k != "inMain"}
    assert saved["scope"] == {"kind": "node", "id": "node-1"} and saved["parent"] is None
    assert saved["project"] == "draft" and saved["workspace"] == "draft"
    assert saved["by"] == HUMAN and saved["graphDigest"] == DIGEST and saved["inMain"] is False
    assert hub.head(SCOPE)["id"] == saved["id"]
    assert hub.head(SCOPE)["subject"] == "Zadání uzlu v revizi 3"
    assert hub.main_of(SCOPE) is None


def test_id_is_the_fingerprint_of_the_content(hub):
    saved = hub.commit(SCOPE, work())
    content = {k: v for k, v in saved.items() if k not in ("id", "inMain")}

    assert content_id(content) == saved["id"] and len(saved["id"]) == 40
    assert content_id(dict(reversed(list(content.items())))) == saved["id"]
    assert content_id({**content, "subject": "jiné zadání"}) != saved["id"]
    assert content_id({**content, "specRevision": 4}) != saved["id"]


def test_second_commit_has_the_first_as_parent_and_other_scope_has_its_own_chain(hub):
    first = hub.commit(SCOPE, work("první"))
    second = hub.commit(SCOPE, work("druhý"))
    alone = hub.commit(OTHER, work("sektor", kind="sector"))

    assert first["parent"] is None and second["parent"] == first["id"]
    assert alone["parent"] is None and alone["scope"] == {"kind": "sector", "id": "sektor-1"}
    assert hub.head(SCOPE)["id"] == second["id"] and hub.head(OTHER)["id"] == alone["id"]


def test_commit_file_is_never_overwritten(hub):
    first = hub.commit(SCOPE, work("stejný předmět"))
    second = hub.commit(SCOPE, work("stejný předmět"))

    files = sorted(path.name for path in hub.store.folder("draft").glob("*.json"))
    assert files == sorted([f"{first['id']}.json", f"{second['id']}.json"])
    assert stored(hub, first["id"])["parent"] is None
    assert stored(hub, second["id"])["parent"] == first["id"]


@pytest.mark.parametrize("kind", ["agent", "robot", None, ""])
def test_only_human_and_orchestrator_write_history(hub, kind):
    mine = hub.commit(SCOPE, work())
    author = {"kind": kind, "name": "Claude"}

    with pytest.raises(ValueError) as commit_error:
        hub.commit(SCOPE, work(by=author))
    with pytest.raises(ValueError) as merge_error:
        hub.merge(SCOPE, mine["id"], by=author)

    assert str(commit_error.value) and str(merge_error.value)
    if kind == "agent":
        assert "Agent" in str(commit_error.value) and "Agent" in str(merge_error.value)
    assert [one["id"] for one in hub.history(SCOPE)] == [mine["id"]]
    assert hub.main_of(SCOPE) is None


def test_agent_is_a_known_author_but_never_a_writer():
    assert set(AUTHORS) - set(WRITERS) == {"agent"}


def test_merge_marks_main_and_repeats_without_change(hub):
    first = hub.commit(SCOPE, work("první"))
    second = hub.commit(SCOPE, work("druhý"))

    merged = hub.merge(SCOPE, first["id"], by=ORCHESTRATOR)
    assert merged["id"] == first["id"] and merged["inMain"] is True
    assert hub.merge(SCOPE, first["id"], by=ORCHESTRATOR) == merged
    assert hub.main_of(SCOPE)["id"] == first["id"]
    assert hub.head(SCOPE)["id"] == second["id"]

    assert hub.merge(SCOPE, second["id"], by=HUMAN)["id"] == second["id"]
    assert hub.main_of(SCOPE)["id"] == second["id"]


def test_merge_of_a_foreign_or_unknown_commit_is_refused(hub):
    mine = hub.commit(SCOPE, work())
    foreign = hub.commit(OTHER, work("sektor", kind="sector"))

    with pytest.raises(ValueError) as foreign_error:
        hub.merge(SCOPE, foreign["id"], by=HUMAN)
    with pytest.raises(ValueError) as unknown_error:
        hub.merge(SCOPE, "0" * 40, by=HUMAN)

    assert str(foreign_error.value) and str(unknown_error.value)
    assert hub.main_of(SCOPE) is None and hub.main_of(OTHER) is None
    assert hub.head(SCOPE)["id"] == mine["id"]


def test_history_is_newest_first_and_respects_the_limit(hub):
    for subject in ("první", "druhý", "třetí"):
        hub.commit(SCOPE, work(subject))
    hub.commit(OTHER, work("cizí", kind="sector"))

    assert [one["subject"] for one in hub.history(SCOPE)] == ["třetí", "druhý", "první"]
    assert [one["subject"] for one in hub.history(SCOPE, limit=2)] == ["třetí", "druhý"]
    assert [one["subject"] for one in hub.history(OTHER)] == ["cizí"]
    with pytest.raises(ValueError):
        hub.history(SCOPE, limit=0)


def test_rebuild_index_restores_the_same_commits_from_the_files(hub):
    first = hub.commit(SCOPE, work("první"))
    second = hub.commit(SCOPE, work("druhý"))
    hub.commit(OTHER, work("sektor", kind="sector"))
    hub.merge(SCOPE, first["id"], by=ORCHESTRATOR)
    before = hub.history(SCOPE)

    db = hub.canvas.db_for("draft")
    db.execute("DELETE FROM opora_commits")
    db.commit()
    assert hub.history(SCOPE) == [] and hub.head(OTHER) is None

    assert hub.rebuild_index("draft", "draft") == 3
    assert hub.history(SCOPE) == before
    assert [one["id"] for one in hub.history(SCOPE)] == [second["id"], first["id"]]
    assert hub.head(SCOPE)["id"] == second["id"]
    assert hub.main_of(SCOPE)["id"] == first["id"]


@pytest.mark.parametrize("payload", [
    work(subject=""),
    work(subject="   "),
    work(subject="x" * 201),
    work(subject="zadání\0"),
    work(subject=None),
    work(specRevision=-1),
    work(specRevision="3"),
    work(specRevision=1.5),
    work(graphDigest="abc"),
    work(graphDigest="d" * 129),
    work(graphDigest=None),
    work(kind="oblast"),
    work(kind=None),
    work(pair=[]),
    work(by={"kind": "human", "name": ""}),
    {"kind": "node", "specRevision": 1, "graphDigest": DIGEST, "subject": "bez autora"},
    "commit",
])
def test_invalid_commit_is_refused_in_czech(hub, payload):
    with pytest.raises(ValueError) as error:
        hub.commit(SCOPE, payload)

    assert str(error.value)
    assert hub.head(SCOPE) is None
    assert list(hub.store.folder("draft").glob("*.json")) == []


@pytest.mark.parametrize("scope", [
    ("draft", "draft", "node 1"),
    ("draft", "draft", ""),
    ("draft", "draft", None),
    ("draft", "", "node-1"),
    ("draft", "draft"),
    "draft",
])
def test_invalid_scope_is_refused(hub, scope):
    with pytest.raises(ValueError):
        hub.commit(scope, work())
