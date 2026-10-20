"""Legacy read compatibility and stable JSON differences."""
import pytest
from contextlib import nullcontext
from types import SimpleNamespace

from backend.canvas.opora_proposals import OporaProposals, differences
from backend.canvas.test_opora_hub import SCOPE, hub, work  # noqa: F401


def test_legacy_metadata_remains_readable_but_is_not_invented_as_snapshot(hub):
    record = hub.commit(SCOPE, work())
    proposals = OporaProposals(hub.canvas, hub)
    assert hub.read(SCOPE, record["id"]) == record
    with pytest.raises(ValueError, match="nemá snímek"):
        proposals.diff(SCOPE, record["id"], record["id"])


def test_diff_escapes_pointer_keys_and_treats_arrays_atomically():
    assert differences({"a/b~": [1, 2], "removed": True}, {"a/b~": [2, 1], "new": None}) == [
        {"op": "replace", "path": "/a~1b~0", "before": [1, 2], "after": [2, 1]},
        {"op": "add", "path": "/new", "after": None},
        {"op": "remove", "path": "/removed", "before": True},
    ]


def test_diff_distinguishes_json_boolean_and_number():
    assert differences({"value": True}, {"value": 1}) == [
        {"op": "replace", "path": "/value", "before": True, "after": 1},
    ]


def test_read_only_workspace_rejects_proposal_before_capture_or_write():
    service = SimpleNamespace(graph_lock_for=lambda pid: nullcontext(),
                              lock_for=lambda pid: nullcontext(),
                              view=lambda pid, wid: {"readOnly": True})
    proposals = OporaProposals(service, None)
    with pytest.raises(ValueError, match="jen pro čtení"):
        proposals.propose(SCOPE, {"expectedHead": None, "expectedContextVersion": "0" * 64},
                          {"kind": "agent", "name": "planner"})
