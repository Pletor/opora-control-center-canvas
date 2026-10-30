"""`assignment.handoff`: výběr předchůdců na vazbě `next`, poslední přijatý výsledek, PR, snímek v otisku."""
import pytest

from backend.canvas import opora_executions
from backend.canvas.graph import digest
from backend.canvas.opora_execution_handoff import area_flows, handoff_for, pinned
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE, baseline, service  # noqa: F401
from backend.canvas.test_opora_executions import claim, credentials
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.schema.opora_execution_pull_request_schema import SCHEMA as PR_SCHEMA
from database.schema.opora_execution_schema import SCHEMA

RESULT = {"summary": "ROZHODNUTI-0: originál pod klíčem sha256. PREDAVKA-0: naváž na rozhraní.",
          "decisions": [{"text": "Ukládáme originál", "why": "audit", "alternatives": ["jen výtah"], "evidence": ["PR #100"]}],
          "selfChecks": {"headSha": "c" * 40, "checks": [{"name": "tests", "command": "pytest", "exitCode": 0,
                                                          "status": "passed", "summary": "KONTROLA-0"}]}}


@pytest.fixture
def authority(service):  # noqa: F811
    db = service.db_for("draft")
    db.executescript(SCHEMA)
    db.executescript(PR_SCHEMA)
    current = service.view("draft", "draft")
    graph = current["graph"]
    service.save_graph("draft", "draft", {**graph, "edges": [*graph["edges"], {"id": "e-ab", "source": "a", "target": "b"}]},
                       current["digest"])
    baseline(service)
    return ExecutionResults(service)


def reported(authority):
    record = claim(authority, "pred", node="a")
    authority.submit(record["executionId"], {**credentials(record), "requestId": "r1", "result": RESULT})
    return record


def link(service, record, state="merged"):  # noqa: F811
    db = service.db_for("draft")
    with db:
        db.execute("BEGIN IMMEDIATE")
        ExecutionPullRequests(db, "draft", "draft").insert({
            "execution_id": record["executionId"], "node_id": "a", "accepted_revision": record["acceptedRevision"],
            "repository": "sim/ample", "number": 100, "head_ref": "work/a", "head_sha": "c" * 40, "state": state,
            "binding_id": None, "enrollment": "unavailable", "enrollment_error": None, "enrollment_retry_at": None,
            "enrollment_failures": 0, "merge_sha": "d" * 40 if state == "merged" else None, "merged_at": None,
            "awaiting_human_close": 0, "attention": None, "source": "agent", "linked_by": "agent",
            "created_at": "2026-10-23T10:00:00Z", "updated_at": "2026-10-23T10:00:00Z"})


def test_card_without_predecessors_gets_an_empty_handoff_inside_its_digest(authority):
    record = claim(authority, node="a")
    value = record["assignment"]["handoff"]
    assert value["predecessors"] == value["areaFlows"] == value["omitted"] == []
    assert digest(record["assignment"]) == record["assignmentDigest"]
    read = authority.read_assignment(record["executionId"], **SCOPE, token=record["token"])
    assert read["assignment"]["handoff"] == value


def test_successor_handoff_carries_the_reported_result(authority, service):  # noqa: F811
    record = reported(authority)
    value = handoff_for(service, service.db_for("draft"), "draft", "draft", "b")
    (entry,) = value["predecessors"]
    assert entry["cardId"] == "a" and entry["executionId"] == record["executionId"]
    assert entry["resultStatus"] == "reported" and "PREDAVKA-0" in entry["summary"]
    assert entry["decisions"] == [{"text": "Ukládáme originál", "why": "audit", "alternatives": ["jen výtah"],
                                   "evidence": ["PR #100"]}]
    assert entry["checks"] == [{"name": "tests", "status": "passed", "summary": "KONTROLA-0"}]
    assert entry["lens"] == {"endpoint": "/api/oporahub/review-lens?nodeId=a", "stored": False}
    assert "pr" not in entry
    assert value["trimmed"] == [] and value["bytes"] <= value["capBytes"]
    # Karta `a` nemá předchůdce: její předávka je prázdná.
    assert handoff_for(service, service.db_for("draft"), "draft", "draft", "a")["predecessors"] == []


def test_merged_pull_request_is_part_of_the_handoff(authority, service):  # noqa: F811
    record = reported(authority)
    link(service, record)
    (entry,) = handoff_for(service, service.db_for("draft"), "draft", "draft", "b")["predecessors"]
    assert entry["resultStatus"] == "merged"
    assert entry["pr"] == {"number": 100, "state": "merged", "mergeSha": "d" * 40,
                           "url": "https://github.com/sim/ample/pull/100"}


def test_handoff_is_a_snapshot_a_predecessor_change_does_not_revoke_the_run(authority, service, monkeypatch):  # noqa: F811
    monkeypatch.setattr(opora_executions, "require_ready", lambda *args: None)  # `a` není uzavřená
    first = reported(authority)
    record = claim(authority, "succ", node="b")
    snapshot = record["assignment"]["handoff"]
    assert snapshot["predecessors"][0]["cardId"] == "a" and digest(record["assignment"]) == record["assignmentDigest"]
    link(service, first)  # předchůdce se mezitím sloučil
    beat = authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
    assert beat["state"] == "running" and beat["assignment"]["handoff"] == snapshot
    # Nový claim by dostal novou předávku, a tedy jiný otisk.
    assert handoff_for(service, service.db_for("draft"), "draft", "draft", "b") != snapshot


def decide(service, node, by):  # noqa: F811
    """Rozhodnutí karty na ploše, jak ho zapíše srdce po sloučení předchůdce (bez executionId).

    Srdce zapisuje s plnou autonomií (`acts_as_human`), proto zápis jako člověk; o výřezu rozhoduje pole `by`."""
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    current = DesktopV3State(service).read(**SCOPE)
    item = {"id": f"hd_{by}", "text": f"Karta {node} sloučena ({by}).", "pinned": False, "path": "", "nodeId": node,
            "createdAt": "2026-10-30T11:52:00Z", "by": by}
    state = {**current["state"], "decisions": [*current["state"]["decisions"], item]}
    DesktopV3State(service).save({**SCOPE, "expectedRevision": current["revision"], "state": state}, actor="human")


def test_agent_decision_on_predecessor_after_claim_does_not_revoke_the_run(authority, service, monkeypatch):  # noqa: F811
    # Ample 2026-10-30: srdce po sloučení předchůdce zapsalo rozhodnutí na jeho kartu a obnova lease běhu nástupce
    # skončila 409 „Execution assignment changed“. Rozhodnutí předchůdce jsou předpoklad snímku jako předávka.
    monkeypatch.setattr(opora_executions, "require_ready", lambda *args: None)  # `a` není uzavřená
    reported(authority)
    record = claim(authority, "succ", node="b")
    renew = {**credentials(record), "ttlSeconds": 60}
    decide(service, "a", "agent")
    assert authority.context(**SCOPE, node="b")["contextVersion"] != record["assignment"]["contextVersion"]
    beat = authority.heartbeat(record["executionId"], renew)
    assert beat["state"] == "running" and beat["assignment"] == record["assignment"]
    # Rozhodnutí člověka na předchůdci dál mění zadání a běh odvolá.
    decide(service, "a", "human")
    with pytest.raises(ValueError, match="changed"):
        authority.heartbeat(record["executionId"], renew)


def test_pinned_keeps_records_without_handoff_comparable():
    current = {"acceptedRevision": "x"}
    assert pinned(current, {"assignment": {"acceptedRevision": "x"}}) == current
    assert pinned(current, {"assignment": {"handoff": {"v": 1}}}) == {"acceptedRevision": "x", "handoff": {"v": 1}}


def area(node_id, x):
    return {"id": node_id, "parentId": None, "kind": "area", "name": f"Oblast {node_id}", "x": x, "y": 0,
            "size": {"w": 1000, "h": 1000}}


def card(node_id, x):
    return {"id": node_id, "parentId": None, "kind": "node", "name": node_id, "x": x, "y": 100}


def test_first_card_of_an_area_gets_incoming_flow_reports():
    graph = {"nodes": [area("A1", 0), area("A2", 2000), card("a", 100), card("b", 2100), card("c", 2600)],
             "edges": [{"id": "f1", "source": "A1", "target": "A2", "port": "flow"}]}
    state = {"edges": {"f1": {"handoff": "Předávám příjem.", "summary": "Hotovo.", "sentAt": "2026-10-22T08:00:00Z"}}}
    by_id = {item["id"]: item for item in graph["nodes"]}
    (flow,) = area_flows(graph, state, by_id, by_id["b"], {"a"})
    assert flow == {"edgeId": "f1", "fromArea": {"id": "A1", "title": "Oblast A1"}, "handoff": "Předávám příjem.",
                    "summary": "Hotovo.", "sentAt": "2026-10-22T08:00:00Z", "full": {"state": "/api/desktop-v3/state"}}
    assert area_flows(graph, state, by_id, by_id["c"], {"b"}) == []  # `b` je ve stejné oblasti: `c` není první
    assert area_flows(graph, state, by_id, by_id["a"], set()) == []  # do A1 žádný tok nevede
