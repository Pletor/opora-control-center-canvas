"""Storyboard scenes are frozen inputs of task and affected-element handoffs."""
from copy import deepcopy

import pytest

from backend.canvas.test_execution_write_set import configure, start, SCOPE
from backend.canvas.test_opora_changesets import service
from backend.editor.storyboard.storyboard import StoryboardService
from backend.editor.storyboard.test_storyboard import board


def save(service, node, title, revision=0):
    StoryboardService(service).save({**SCOPE, "nodeId": node, "expected_revision": revision,
                                    "storyboard": board(title=title)})
    if revision == 0:
        from backend.canvas.test_storyboard_acceptance import accept_scene
        accept_scene(service, node)


@pytest.mark.parametrize("protocol", [1, 2])
def test_task_and_affected_scenes_are_pinned_with_result_revision(service, protocol):
    authority = configure(service)
    save(service, "a", "Task flow")
    save(service, "login", "Login scenario")
    execution = start(authority, protocol)
    pins = {pin["nodeId"]: pin for pin in execution["assignment"]["storyboards"]}
    assert pins["a"]["storyboard"]["title"] == "Task flow"
    assert pins["login"]["storyboard"]["title"] == "Login scenario"
    assert pins["login"]["revision"] == 2 and pins["login"]["digest"]
    assert pins["login"]["acceptance"] == "accepted-content"
    receipt = authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
        "requestId": "result", "result": {"summary": "Scene implementation"}})
    assert receipt["assignmentDigest"] == execution["assignmentDigest"]


@pytest.mark.parametrize("protocol", [1, 2])
def test_changed_affected_scene_rejects_result_and_keeps_historical_snapshot(service, protocol):
    authority = configure(service)
    save(service, "login", "Original login")
    execution = start(authority, protocol)
    assignment = deepcopy(execution["assignment"])
    save(service, "login", "Changed login", 2)
    with pytest.raises(ValueError):
        authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
            "requestId": "result", "result": {"summary": "Old scene"}})
    stored = authority.read_assignment(execution["executionId"], **SCOPE, token=execution["token"])["assignment"]
    assert stored == assignment
    assert next(pin for pin in stored["storyboards"] if pin["nodeId"] == "login")["storyboard"]["title"] == "Original login"


@pytest.mark.parametrize("protocol", [1, 2])
def test_scene_change_between_context_and_claim_is_not_silently_adopted(service, protocol):
    from backend.canvas.opora_execution_context import prepare
    authority = configure(service)
    save(service, "login", "Reviewed scene")
    context = prepare(authority, {**SCOPE, "nodeId": "a", "contextProtocolVersion": 2}) if protocol == 2 else authority.context(**SCOPE, node="a")
    save(service, "login", "Unreviewed scene", 2)
    with pytest.raises(ValueError, match="accepted manifest"):
        authority.claim({**SCOPE, "nodeId": "a", "requestId": "scene-race", "ttlSeconds": 60,
            "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"],
            **({"contextProtocolVersion": 2} if protocol == 2 else {})}, "agent:worker")
