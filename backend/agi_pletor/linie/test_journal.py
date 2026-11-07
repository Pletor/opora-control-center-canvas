"""Deník Linie: události `linie.*` v `opora_events`, pořadí podle `id`, `after` vrátí jen novější."""
from backend.agi_pletor.linie import journal, work
from backend.agi_pletor.linie.test_work import NOW, setup  # noqa: F401 (fixture)
from backend.canvas.opora_events import emit_event


def test_journal_after_returns_only_newer(setup):
    service, _repo, tid = setup
    first = journal.read(service, "draft")
    assert [e["kind"] for e in first["events"]] == ["linie.work.created"]
    assert first["events"][0]["refs"] == {"ticket": tid} and first["events"][0]["by"] == "human"
    emit_event(service, project_id="draft", workspace_id="main", kind="guard.alert")  # cizí druh deník nevidí
    work.block(service, "draft", tid, "čeká na API", NOW, "agent:dev")
    journal.record(service, "draft", "linie.request.accepted", "human", {"request": "rq_1", "ticket": None})
    newer = journal.read(service, "draft", after=first["lastId"])
    assert [e["kind"] for e in newer["events"]] == ["linie.block", "linie.request.accepted"]
    assert newer["events"][0]["by"] == "agent:dev" and newer["events"][1]["refs"] == {"request": "rq_1"}
    assert newer["events"][0]["id"] < newer["events"][1]["id"] == newer["lastId"]
    assert journal.read(service, "draft", after=newer["lastId"]) == {"events": [], "lastId": newer["lastId"]}


def test_unchanged_work_writes_no_event(setup):
    service, _repo, tid = setup
    work.resume(service, "draft", tid, NOW)
    last = journal.read(service, "draft")["lastId"]
    work.resume(service, "draft", tid, NOW)  # stejný stav i čas: žádná změna, žádná událost
    assert journal.read(service, "draft", after=last)["events"] == []
