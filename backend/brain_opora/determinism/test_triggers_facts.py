"""Fakta spouštěče `card.step_failed` nad skutečnou projekcí (PLAN-002): odevzdaný běh se selhaným krokem je
pro ProcessSync `reported`, `facts` ho najde s krokem a poznámkou z výsledku, PR běhu ho utiší a přijatý návrh
s novými kroky karty vrátí kartu k převzetí (`ready`), takže spouštěč už nebudí."""
import pytest

from backend.brain_opora.determinism import triggers
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_process_sync import ProcessSync
from backend.canvas.test_opora_auto_rebase import propose as propose_fields
from backend.canvas.test_opora_changesets import SCOPE, accept, baseline, legacy_save
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_executions import claim, credentials
from backend.canvas.test_opora_plan_steps import PLAN, step
from backend.canvas.test_opora_process_sync import head, route
from database.repositories.opora_execution_pull_requests import COLUMNS, ExecutionPullRequests

NOTES = "Migrace 0042 je obsazena (poslední 0048), knowledge_version už existuje."


@pytest.fixture
def delivered(service):
    """Karta `a` s přijatými kroky, převzatá a odevzdaná: s1 `failed`, s2 a s3 `skipped`."""
    legacy_save(service, goal="Read accepted task")
    baseline(service)
    route(service)
    authority = ExecutionResults(service)
    record = claim(authority)
    results = [{"stepId": "s1", "status": "failed", "evidence": {"notes": NOTES}},
               {"stepId": "s2", "status": "skipped", "evidence": {"notes": "s1 selhal"}},
               {"stepId": "s3", "status": "skipped", "evidence": {"notes": "s1 selhal"}}]
    authority.submit(record["executionId"], {**credentials(record), "requestId": "report",
                                             "result": {"summary": "Zadání koliduje s repem.", "stepResults": results}})
    return record


def card_a(service):
    cards, _ = triggers.facts(service, "draft", "draft", 0)
    return next(item for item in cards if item["nodeId"] == "a")


def test_facts_find_the_delivered_run_with_a_failed_step_and_the_trigger_wakes(delivered, service):
    card = card_a(service)
    assert card["status"] == "reported"
    assert card["stepFailed"] == {"runId": delivered["executionId"], "stepId": "s1", "notes": NOTES, "pulled": False}
    [hit] = [hit for hit in triggers.evaluate([card], []) if hit["kind"] == "card.step_failed"]
    assert hit["state"] == delivered["executionId"] and NOTES in hit["detail"]


def test_an_open_pull_request_of_the_run_silences_the_trigger(delivered, service):
    db = service.db_for("draft")
    row = dict.fromkeys(COLUMNS) | {
        "execution_id": delivered["executionId"], "node_id": "a", "accepted_revision": delivered["acceptedRevision"],
        "repository": "o/r", "number": 7, "head_ref": "b", "head_sha": "a" * 40, "state": "open",
        "enrollment": "enrolled", "enrollment_failures": 0, "awaiting_human_close": 0, "source": "github",
        "linked_by": "agent:worker", "created_at": "2026-11-01T00:00:00Z", "updated_at": "2026-11-01T00:00:00Z"}
    with db:
        db.execute("BEGIN")
        ExecutionPullRequests(db, "draft", "draft").insert(row)
    card = card_a(service)
    assert card["stepFailed"]["pulled"] is True and triggers.step_failed(card) is None


def test_accepted_new_steps_return_the_card_to_claim_and_the_trigger_is_silent(delivered, service):
    rewritten = [step("s1", 1), step("s2", 2, ["s1"]), step("s4", 3, ["s2"])]
    rewritten[0] = {**rewritten[0], "title": "Migrace 0049 (poslední na main + 1)"}
    assert rewritten != PLAN
    accept(service, propose_fields(service, "a", steps=rewritten), head(service))
    item = ProcessSync(service).read(**SCOPE, node="a")["items"][0]
    assert item["status"] == "ready" and item["nextAction"]["kind"] == "claim"
    assert item["currentExecution"]["staleEvidence"]  # výsledek je historie, karta jde znovu k převzetí
    card = card_a(service)
    assert card["stepFailed"] is None and triggers.step_failed(card) is None


def test_live_card_behind_many_finished_cards_in_graph_order_is_still_seen(delivered, service, monkeypatch):
    """Velký plán: prvních `CARDS` karet v pořadí grafu jsou hotové / nenaplánované, živá karta je za nimi."""
    real = ProcessSync.read

    def padded(self, project, workspace, node=None, limit=None):
        result = real(self, project, workspace, node=node, limit=None)
        filler = [{"nodeId": f"x{i}", "status": "closed"} for i in range(triggers.CARDS)]
        return {**result, "items": filler + result["items"]} if limit is None else {**result, "items": filler[:limit]}

    monkeypatch.setattr(ProcessSync, "read", padded)
    assert card_a(service)["stepFailed"]["stepId"] == "s1"
