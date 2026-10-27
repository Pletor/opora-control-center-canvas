"""Brána cesty zákazníka v uzavření karty (`docs/brana-cesty.md` §5): obě větve, s kroky plánu i bez nich."""
import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas import opora_card_done as card_done
from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_card_done import card_done_state, closure_gate
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_auto_rebase import propose
from backend.canvas.test_opora_changesets import SCOPE, accept, baseline
from backend.canvas.test_opora_executions import claim
from backend.canvas.test_opora_plan_steps import PLAN
from backend.canvas.test_opora_step_results import done, submit
from backend.canvas.test_project_architecture import domain, page
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.test_completion_evidence import evidence
from backend.project.architecture import journey_runs
from backend.project.architecture.journey_plan import journey_plan
from database.schema.opora_execution_schema import SCHEMA

pytestmark = pytest.mark.plan_steps_claim

JOURNEY = {"id": "kampan", "name": "Kampaň Pěstování",
           "steps": [{"id": "s1", "page": "nav"}, {"id": "s2", "page": "page"}]}


@pytest.fixture
def service(tmp_path):
    instance = CanvasService(tmp_path / "data")
    current = instance.view("draft", "draft")
    graph = {"nodes": [node("a", parent_id="page"), node("b", parent_id="page"), node("free"),
                       domain(journeys=[JOURNEY]), page()], "edges": []}
    instance.save_graph("draft", "draft", graph, current["digest"])
    yield instance
    instance.close()


def runs(service, ok=True, stale=False):
    """Poslední doklad cesty, jak ho vrací `latest_journey_runs` (passed odvozené)."""
    graph = service.view("draft", "draft")["graph"]
    digest = "sha256:" + "0" * 64 if stale else journey_plan(graph, "kampan")["digest"]
    record = {"applicationId": "app", "journeyId": "kampan", "planDigest": digest, "command": "journey_run",
              "at": "2026-10-27T21:40:00+00:00", "passed": ok,
              "segments": [{"from": "s1", "to": "s2", "ok": ok, **({} if ok else {"reason": "URL /"})}]}
    return {("app", "kampan"): record}


def use_runs(monkeypatch, value):
    monkeypatch.setattr(journey_runs, "latest_journey_runs", lambda service, project: value)


def test_done_state_lists_journeys_before_human_close():
    blocking = [{"journeyId": "kampan", "applicationId": "app", "name": "Kampaň", "reason": "zastaralé"}]
    complete = {"steps": {"total": 1, "done": 1}, "acceptanceEvidence": True, "gate": {"status": "ready"},
                "merged": True, "planWrittenBack": True, "closed": False}
    state = card_done_state({**complete, "journeys": blocking})
    assert state["missing"] == ["journeys", "human_close"] and state["blockingJourneys"] == blocking
    assert "blockingJourneys" not in card_done_state({**complete, "journeys": []})


# --- Karta bez kroků plánu: starší větev v DesktopV3State.save ---

def close_legacy(service, node_id):
    store = DesktopV3State(service)
    current = store.read("draft", "draft")
    state = current["state"]
    state["nodes"][node_id] = {"phase": "build", "criteria": [], "steps": [], "done": {"confirmed": True, "by": "human", "at": "2026-10-27T12:00:00Z", "note": "OK"},
                               "evidence": evidence()}
    return store.save({**SCOPE, "expectedRevision": current["revision"], "state": state}, actor="human", slim=True)


@pytest.mark.parametrize(("value", "reason"), [
    ({}, "chybí ověření"), ("stale", "zastaralé"), ("failed", "neprošel přechod s1 → s2")])
def test_legacy_close_refused_without_fresh_passed_run(service, monkeypatch, value, reason):
    use_runs(monkeypatch, runs(service, stale=True) if value == "stale" else runs(service, ok=False)
             if value == "failed" else value)
    with pytest.raises(ValueError, match=f"cesta Kampaň Pěstování: {reason}"):
        close_legacy(service, "b")


def test_legacy_close_passes_with_fresh_passed_run(service, monkeypatch):
    use_runs(monkeypatch, runs(service))
    close_legacy(service, "b")
    assert DesktopV3State(service).read("draft", "draft")["state"]["nodes"]["b"]["done"]["confirmed"] is True


def test_legacy_close_off_journey_is_unchanged(service, monkeypatch):
    def unexpected(service, project):
        raise AssertionError("karta mimo cestu doklady nečte")
    monkeypatch.setattr(journey_runs, "latest_journey_runs", unexpected)
    close_legacy(service, "free")


# --- Karta s přijatými kroky: closure_gate (opora_card_done) ---

@pytest.fixture
def finished(service, monkeypatch):
    """Karta `a` se všemi kroky hotovými, sloučeným PR se zápisem plánu a vnější bránou: chybí jen cesta a člověk."""
    service.db_for("draft").executescript(SCHEMA)
    from backend.canvas.opora_execution_results import ExecutionResults
    initial = baseline(service)
    accept(service, propose(service, "a", goal="Build it", steps=PLAN), initial["id"])
    authority = ExecutionResults(service)
    submit(authority, claim(authority), "r1", done("s1"), done("s2"), done("s3"))
    monkeypatch.setattr(pulls, "read", lambda *args: [{"cardId": "a", "state": "merged", "executionId": "x",
                                                        "planWrittenBack": True}])
    monkeypatch.setattr(card_done, "gates_by_execution", lambda *args: None)
    return service


@pytest.mark.parametrize(("value", "reason"), [
    ({}, "chybí ověření"), ("stale", "zastaralé"), ("failed", "neprošel přechod s1 → s2")])
def test_stepped_close_refused_names_journey(finished, monkeypatch, value, reason):
    use_runs(monkeypatch, runs(finished, stale=True) if value == "stale" else runs(finished, ok=False)
             if value == "failed" else value)
    with pytest.raises(ValueError, match=f"cesta Kampaň Pěstování: {reason}"):
        closure_gate(finished, "draft", "draft", "a")


def test_stepped_close_passes_with_fresh_passed_run(finished, monkeypatch):
    use_runs(monkeypatch, runs(finished))
    assert closure_gate(finished, "draft", "draft", "a")["missing"] == ["human_close"]


def test_agent_state_dod_shows_blocking_journey(finished, monkeypatch):
    from backend.canvas.opora_agent_state import AgentState
    use_runs(monkeypatch, {})
    entry = next(item for item in AgentState(finished).read("draft", "draft")["cards"] if item["nodeId"] == "a")
    assert entry["dod"]["journeys"] is False and "journeys" in entry["dod"]["missing"]
    assert entry["dod"]["blockingJourneys"][0]["reason"] == "chybí ověření"
