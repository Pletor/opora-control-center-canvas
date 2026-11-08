import json
from types import SimpleNamespace

import pytest

from backend.brain_opora.heart import opora_heart, research_actions


def test_scoped_proposal_and_feedback_commands_cannot_override_token_scope(tmp_path):
    calls = []
    tool = SimpleNamespace(scope=lambda: {"project": "p1", "workspace": "w1"},
                           call=lambda *a, **kw: calls.append((a, kw)) or {}, Failure=opora_heart.Failure)
    def run(*args):
        parsed = opora_heart.parser().parse_args(["research-map", *args])
        return research_actions.run(parsed, tool)
    run("reviews", "--decision", "decision1")
    assert calls[-1][1]["query"] == {"project": "p1", "workspace": "w1", "decisionId": "decision1"}
    run("ticket-branch", "--ticket", "tk_1", "--feedback", "fb_1")
    assert calls[-1][0][2] == {"project": "p1", "workspace": "w1", "ticketId": "tk_1", "feedbackId": "fb_1"}
    run("ticket-answer", "--ticket", "tk_1", "--feedback", "fb_1", "--card", "rc_1", "--revision", "3", "--text", "answer")
    assert calls[-1][0][2]["revision"] == 3
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps({"tasks": []}), encoding="utf-8")
    run("tasks", "--review", "rr_1", "--file", str(tasks))
    assert calls[-1][0][2] == {"project": "p1", "workspace": "w1", "tasks": []}
    tasks.write_text(json.dumps({"tasks": [], "project": "foreign"}), encoding="utf-8")
    with pytest.raises(opora_heart.Failure):
        run("tasks", "--review", "rr_1", "--file", str(tasks))
