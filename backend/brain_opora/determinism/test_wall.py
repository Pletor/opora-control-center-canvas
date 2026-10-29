"""Zeď brány: tabulka docs/brain-gate.md §3 jako čistá funkce a `check` nad skutečným projektem."""
import pytest

from backend.brain_opora.determinism import gate_setting, tokens, wall
from backend.canvas.canvas_service import CanvasService

HEART = {"role": "heart", "project": "draft"}
WORKER = {"role": "worker", "project": "draft"}
PLAN = "/api/canvas-plan"


def test_gate_off_allows_everything():
    for token in (None, wall.INVALID, WORKER, {"role": "heart", "project": "jiny"}):
        assert wall.decide("POST", PLAN, "agent", False, token, "draft") is wall.ALLOW


def test_reads_and_human_pass():
    assert wall.decide("GET", PLAN, "agent", True, None, "draft") is wall.ALLOW
    assert wall.decide("HEAD", PLAN, "unknown", True, wall.INVALID, "draft") is wall.ALLOW
    assert wall.decide("POST", PLAN, "human", True, None, "draft") is wall.ALLOW
    assert wall.decide("POST", PLAN, "human", True, HEART, "draft") is wall.ALLOW


def test_heart_of_this_project_gets_full_autonomy():
    for method in ("POST", "GET"):
        verdict = wall.decide(method, PLAN, "agent", True, HEART, "draft")
        assert verdict.allow and verdict.heart and verdict.project == "draft"


def test_gate_paths_pass_with_any_token():
    for token in (None, wall.INVALID, WORKER):
        assert wall.decide("POST", "/api/gate/requests", "agent", True, token, "draft") is wall.ALLOW
    assert wall.decide("POST", "/api/gateway", "agent", True, None, "draft").code == "gate_required"


def test_refusals_carry_code_and_hint():
    cases = [(None, "draft", 403, "gate_required"), (WORKER, "draft", 403, "gate_required"),
             (wall.INVALID, "draft", 401, "gate_token_invalid"),
             ({"role": "heart", "project": "jiny"}, "draft", 403, "gate_scope"),
             ({"role": "worker", "project": "jiny"}, "draft", 403, "gate_scope"),
             (HEART, "", 403, "gate_scope")]  # query a tělo jmenují různé projekty
    for token, project, status, code in cases:
        verdict = wall.decide("POST", PLAN, "agent", True, token, project)
        assert not verdict.allow and (verdict.status, verdict.code) == (status, code)
        assert set(verdict.body()) == {"error", "code", "hint"} and verdict.hint and verdict.error
    assert wall.decide("POST", PLAN, "unknown", True, None, "draft").hint == wall.GATE_HINT


LANE_PATHS = ("/api/oporahub/executions/claim", "/api/oporahub/executions/e1/deliver",
              "/api/oporahub/executions/e1/heartbeat", "/api/oporahub/harness-invocations",
              "/api/oporahub/review-identities/claim", "/api/desktop-v3/agent-output")
WALLED = (PLAN, "/api/oporahub/graph-proposals", "/api/desktop-v3/node", "/api/desktop-v3/rule",
          "/api/oporahub/executionsX", "/api/oporahub/review-identities/i1/verify", "/api/desktop-v3/agent-outputs")


def test_lane_lets_card_work_through_without_token():
    for path in LANE_PATHS:
        for token in (None, wall.INVALID, WORKER, {"role": "worker", "project": "jiny"}):
            assert wall.decide("POST", path, "agent", True, token, "draft") is wall.ALLOW, (path, token)


def test_canvas_and_rules_stay_with_heart_and_human():
    for path in WALLED:
        assert wall.decide("POST", path, "agent", True, None, "draft").code == "gate_required", path
        assert wall.decide("POST", path, "human", True, None, "draft") is wall.ALLOW
        assert wall.decide("POST", path, "agent", False, None, "draft") is wall.ALLOW


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.db_for("draft")
    yield canvas
    canvas.close()


def test_check_reads_switch_and_verifies_token(service):
    def check(header=None, query="draft", body="", method="POST", actor="agent"):
        return wall.check(service, method, PLAN, actor, header, query, lambda: body)

    assert check() is wall.ALLOW  # brána vypnutá
    gate_setting.write(service, {"project": "draft", "enabled": True})
    assert check().code == "gate_required" and check(query="", body="draft").code == "gate_required"
    assert check(query="", body=123) is wall.ALLOW  # žádný projekt = zeď se nepoužije
    assert check(header="x" * 43).code == "gate_token_invalid"
    _, heart = tokens.issue_heart(service, "draft", "draft")
    assert check(header=heart).heart
    assert check(header=heart, body="jiny").code == "gate_scope"  # dva různé projekty, jeden se zapnutou bránou
    worker = tokens.issue_worker(service, "draft", "draft", {"name": "dev"})["token"]
    assert check(header=worker).code == "gate_required"
    claim = wall.check(service, "POST", "/api/oporahub/executions/claim", "agent", None, "draft", lambda: "")
    assert claim is wall.ALLOW  # pruh orchestrátora i se zapnutou bránou
    assert check(actor="human") is wall.ALLOW and check(method="GET") is wall.ALLOW


def test_relevant_skips_human_and_plain_reads():
    assert not wall.relevant("POST", "human", "t") and not wall.relevant("GET", "agent", None)
    assert wall.relevant("POST", "unknown", None) and wall.relevant("GET", "agent", "t")
