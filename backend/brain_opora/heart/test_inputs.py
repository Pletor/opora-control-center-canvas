"""Co srdce budí: selhaný úkol ano, vrácení úkolu pracovníkem (`release`, status ready s důvodem) ne."""
from backend.brain_opora.heart.inputs import wake_input


def test_failed_task_wakes_the_heart_but_a_released_one_does_not():
    failed = {"kind": "gate.task", "data": {"taskId": "ht_1", "status": "failed"}}
    released = {"kind": "gate.task", "data": {"taskId": "ht_1", "status": "ready", "reason": "Nestihnu to."}}
    assert wake_input(failed) == {"type": "taskFailed", "taskId": "ht_1"}
    assert wake_input(released) is None


def test_merge_done_becomes_a_merged_input_that_resolve_keeps():
    event = {"kind": "merge.done", "nodeId": "n1", "executionId": "ex1", "prNumber": 12,
             "data": {"mergeSha": "abc123", "mergedAt": "2026-10-29T10:00:00Z"}}
    assert wake_input(event) == {"type": "merged", "nodeId": "n1", "executionId": "ex1", "mergeSha": "abc123", "pr": 12}
    local = {"kind": "merge.done", "nodeId": "n1", "executionId": "ex1", "prNumber": None,
             "data": {"source": "local", "commit": "def456", "mergeSha": "def456"}}
    assert wake_input(local)["pr"] is None and wake_input(local)["mergeSha"] == "def456"
