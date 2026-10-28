"""Strážce cest: zastaralý a neúspěšný doklad cesty, karta čekající na uzavření blokovaná bránou cest."""
import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas.strazci import guard_cesty
from backend.canvas.strazci.registry import GuardContext
from backend.project.architecture.journey_plan import journey_plan
from backend.project.architecture.journey_runs import last_runs
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.test_journey_runs import make_graph, make_service, node, run


def latest(graph, **kwargs):
    record = run(journey_plan(graph, "kampan")["digest"], **kwargs)
    record["passed"] = all(segment["ok"] for segment in record["segments"])
    return {("web", "kampan"): record}


def findings(graph, runs):
    return guard_cesty.journey_findings(derive_journeys(graph), last_runs(graph, runs), "main")


@pytest.fixture
def no_links():
    yield
    pulls.register(None)


def test_journey_without_run_or_with_fresh_pass_is_quiet():
    graph = make_graph()
    assert findings(graph, {}) == []
    assert findings(graph, latest(graph)) == []


def test_failed_run_points_to_target_page_of_first_failure():
    graph = make_graph()
    [item] = findings(graph, latest(graph, s3=False))
    assert item["key"] == "journey:failed:web:kampan" and item["rule"] == "journey.failed"
    assert item["nodeId"] == "pribeh" and item["journeyId"] == "kampan" and item["severity"] == "warn"
    assert "s2 → s3" in item["message"] and "čekáno /pribeh" in item["message"]


def test_stale_run_wins_over_failure_and_points_to_first_page():
    graph = make_graph()
    runs = latest(graph, s3=False)
    runs[("web", "kampan")]["planDigest"] = "sha256:" + "0" * 64
    [item] = findings(graph, runs)
    assert (item["rule"], item["key"], item["nodeId"]) == ("journey.stale", "journey:stale:web:kampan", "home")


def test_blocked_card_is_a_block_finding():
    [item] = guard_cesty.blocked_findings([{"workspaceId": "main", "nodeId": "c1", "journeys": [
        {"journeyId": "kampan", "applicationId": "web", "name": "Kampaň", "reason": "chybí ověření"}]}])
    assert item["key"] == "journey:blocks-card:main:c1" and item["severity"] == "block"
    assert item["nodeId"] == "c1" and item["journeyId"] == "kampan" and "Kampaň: chybí ověření" in item["message"]


def test_run_reads_cards_awaiting_close_through_the_journey_gate(no_links):
    graph = make_graph()
    graph["nodes"] += [node("form", "novinky"), node("other", "web")]
    service = make_service(graph)
    service.workspaces = lambda project: []
    pulls.register(lambda canvas, project, workspace: [
        {"executionId": "x1", "state": "merged", "cardId": "form", "awaitingHumanClose": True},
        {"executionId": "x2", "state": "merged", "cardId": "other", "awaitingHumanClose": True}])
    found = guard_cesty.run(GuardContext(service, "p1", 0.0))
    assert [(item["rule"], item["nodeId"]) for item in found] == [("journey.blocks-card", "form")]
