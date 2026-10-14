"""Poučení Schránky (docs/schranka-neurony.md §5, §9 bod 12): vznik branou learned, unikátní původ, vyhasínání
s podstrčeným časem, potvrzení, vyřazení jen člověkem, izolace projektu a prostoru, node-brief a verze plátna."""
from datetime import UTC, datetime, timedelta

import pytest

from backend.editor.brief_vault import brief_vault_lessons as lessons_module
from backend.editor.brief_vault.brief_vault_lessons import THRESHOLD, effective_weight
from backend.editor.brief_vault.test_brief_vault_discipline import (
    AGENT,
    HEADERS,
    SCOPE,
    post,
    split_root,
)
from backend.editor.brief_vault.test_brief_vault_gates import force, gate, root, vault_client

ACTUAL = {"actual": {"tests": "pass", "criticRounds": 1, "unexpected": False}}
LESSON = {"lesson": "Migraci piš idempotentně.", "kind": "pattern"}
START = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


@pytest.fixture
def clock(monkeypatch):
    now = {"value": START}
    monkeypatch.setattr(lessons_module, "utc_now", lambda: now["value"])
    return now


def lessons(client, **params):
    response = client.get("/api/brief-vault/lessons", params={**SCOPE, **params})
    assert response.status_code == 200, response.text
    return response.json()["lessons"]


def learned(client, fragment_id, discipline="be"):
    fragment = force(client, fragment_id, "verified", discipline, verified=ACTUAL)
    return gate(client, fragment, "learned", payload=LESSON)


def test_effective_weight_halves_every_30_days():
    assert effective_weight(1.0, START.isoformat(), START + timedelta(days=30)) == pytest.approx(0.5)
    assert effective_weight(1.0, START.isoformat(), START + timedelta(days=60)) == pytest.approx(0.25)
    assert effective_weight(1.0, START.isoformat(), START - timedelta(days=1)) == 1.0


def test_learned_creates_one_lesson_per_cycle(client, clock):
    fragment = root(client)
    done = learned(client, fragment["id"])
    lesson = done["lesson"]
    assert done["lessonCreated"] is True and done["gateStep"] == 8
    assert lesson["text"] == LESSON["lesson"] and lesson["kind"] == "pattern"
    assert lesson["discipline"] == "be" and lesson["fragmentId"] == fragment["id"] and lesson["effectiveWeight"] == 1.0
    assert lessons(client) == [lesson] and lessons(client, discipline="be") == [lesson] and lessons(client, discipline="ux") == []
    off = gate(client, done["fragment"], "learned", value=False)["fragment"]
    again = gate(client, off, "learned", payload={"lesson": "Jiný text.", "kind": "antipattern"})
    assert again["lessonCreated"] is False and again["lesson"]["id"] == lesson["id"] and len(lessons(client)) == 1
    assert client.get("/api/brief-vault/lessons", params={**SCOPE, "discipline": "neni"}).status_code == 400


def test_decay_threshold_and_confirm(client, clock):
    lesson = learned(client, root(client)["id"])["lesson"]
    clock["value"] = START + timedelta(days=30)
    assert lessons(client)[0]["effectiveWeight"] == 0.5
    clock["value"] = START + timedelta(days=70)  # 0.5^(70/30) ≈ 0.198 < 0.2: nevrací se, ale nemaže
    assert 0.5 ** (70 / 30) < THRESHOLD and lessons(client) == []
    confirmed = post(client, op="confirm-lesson", lessonId=lesson["id"], note="Pořád platí.")["lesson"]
    assert confirmed["confirmedAt"] == clock["value"].isoformat() and confirmed["createdAt"] == START.isoformat()
    assert lessons(client)[0]["effectiveWeight"] == 1.0
    db = client.app_state.service.db_for("draft")
    events = db.execute("SELECT kind, by, actor FROM brief_lesson_events WHERE lesson_id=?", (lesson["id"],)).fetchall()
    assert [tuple(row) for row in events] == [("confirm", "discipline-1", "agent")]


def test_drop_is_human_only(client, clock):
    lesson = learned(client, root(client)["id"])["lesson"]
    response = client.post("/api/brief-vault", headers=AGENT, json={**SCOPE, "op": "drop-lesson", "lessonId": lesson["id"],
                                                                     "note": "Neplatí."})
    assert response.status_code == 403 and len(lessons(client)) == 1
    dropped = post(client, headers=HEADERS, op="drop-lesson", lessonId=lesson["id"], note="Neplatí.")["lesson"]
    assert dropped["dropped"] is True and lessons(client) == []
    post(client, expect=409, op="confirm-lesson", lessonId=lesson["id"], note="zpět")
    db = client.app_state.service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM brief_lessons WHERE lesson_id=?", (lesson["id"],)).fetchone()[0] == 2


def test_lessons_are_scoped_to_project_and_workspace(client, clock):
    lesson = learned(client, root(client)["id"])["lesson"]
    db = client.app_state.service.db_for("draft")
    columns = "project_id, workspace_id, lesson_id, revision, fragment_id, cycle_revision, discipline, kind, text, weight," \
              " created_at, confirmed_at, dropped, by, actor, saved_at"
    with db:
        for project, workspace in (("jiny", SCOPE["workspace"]), (SCOPE["project"], "jiny")):
            db.execute(f"INSERT INTO brief_lessons({columns}) VALUES(?,?,?,1,'f',1,'be','pattern','Cizí.',1.0,?,?,0,'x','agent',?)",
                       (project, workspace, "cizi", START.isoformat(), START.isoformat(), START.isoformat()))
    assert [item["id"] for item in lessons(client)] == [lesson["id"]]
    post(client, expect=409, op="confirm-lesson", lessonId="cizi", note="cizí")
    post(client, expect=409, headers=HEADERS, op="drop-lesson", lessonId="cizi", note="cizí")


def test_node_brief_carries_at_most_five_lessons_of_card_discipline(client, clock):
    _root, (first, _second) = split_root(client)
    for index in range(6):
        fragment = post(client, op="create", scopeNodeId="s1", discipline="be", title=f"F{index}", text=f"t{index}")["fragment"]
        clock["value"] = START + timedelta(days=index)
        learned(client, fragment["id"])
    other = post(client, op="create", scopeNodeId="s1", discipline="ux", title="UX", text="u")["fragment"]
    learned(client, other["id"], "ux")
    digest = client.get("/api/view", params=SCOPE).json()["digest"]
    current = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
    planned = client.post("/api/canvas-plan", headers=AGENT, json={**SCOPE, "digest": digest, "dryRun": False, "plan": {
        "extend": [{"node": "@c1", "expectedRevision": current, "fragmentRef": [{"fragmentId": first["id"]}]}]}})
    assert planned.status_code == 200, planned.text
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()
    items = brief["lessons"]["items"]
    assert brief["lessons"]["disciplines"] == ["be"] and len(items) == 5 and {item["discipline"] for item in items} == {"be"}
    assert items[0]["effectiveWeight"] >= items[-1]["effectiveWeight"] and "lessons.items" in brief["trust"]["dataFromAgents"]


def test_canvas_version_carries_gates_and_lessons(client, clock):
    from backend.editor.canvas_versions.test_canvas_versions import digest, save, versions
    fragment = root(client)
    done = learned(client, fragment["id"])
    saved = save(client).json()["version"]
    gate(client, done["fragment"], "scoped", value=False)
    post(client, headers=HEADERS, op="drop-lesson", lessonId=done["lesson"]["id"], note="pryč")
    assert versions(client)["dirty"] is True and lessons(client) == []
    restored = client.post("/api/canvas-versions/restore", headers=HEADERS, json={
        **SCOPE, "versionId": saved["id"], "digest": digest(client), "author": "test",
        "expectedToken": versions(client)["currentToken"]})
    assert restored.status_code == 200, restored.text
    assert [item["id"] for item in lessons(client)] == [done["lesson"]["id"]]
    from backend.editor.brief_vault.test_brief_vault_discipline import nodes, tree
    assert nodes(tree(client))[fragment["id"]]["gateStep"] == 8 and versions(client)["dirty"] is False
