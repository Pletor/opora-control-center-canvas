"""Co srdce budí: selhaný úkol ano, vrácení úkolu pracovníkem (`release`, status ready s důvodem) ne."""
from backend.brain_opora.heart.inputs import wake_input


def test_failed_task_wakes_the_heart_but_a_released_one_does_not():
    failed = {"kind": "gate.task", "data": {"taskId": "ht_1", "status": "failed"}}
    released = {"kind": "gate.task", "data": {"taskId": "ht_1", "status": "ready", "reason": "Nestihnu to."}}
    assert wake_input(failed) == {"type": "taskFailed", "taskId": "ht_1"}
    assert wake_input(released) is None
