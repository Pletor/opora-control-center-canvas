"""SQLite arbitration serializes enrollment against a legacy state mutation."""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_executions import authority, service  # noqa: F401
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
from backend.editor.agent_memory.test_agent_output import block


def test_state_mutation_and_claim_cannot_both_use_old_assignment(authority, service):
    state = default_state()
    state["nodes"]["a"] = {"phase": "discover", "criteria": [], "steps": [], "blocks": [block("b1", "1")]}
    store = DesktopV3State(service)
    saved = store.save({"project": "draft", "workspace": "draft", "expectedRevision": 0, "state": state}, actor="human")
    observed = authority.context("draft", "draft", "a")
    modified = copy.deepcopy(saved["state"])
    modified["nodes"]["a"]["blocks"][0]["title"] = "Different assignment"
    other = CanvasService(service.root)
    other_authority = ExecutionResults(other)
    barrier = Barrier(2)
    def claim():
        barrier.wait()
        try:
            other_authority.claim({"project": "draft", "workspace": "draft", "nodeId": "a", "requestId": "race",
                                   "ttlSeconds": 60, "expectedAcceptedHead": observed["acceptedHead"],
                                   "expectedContextVersion": observed["contextVersion"]}, "agent:worker")
            return True
        except ValueError:
            return False
    def write():
        barrier.wait()
        try:
            store.save({"project": "draft", "workspace": "draft", "expectedRevision": saved["revision"],
                        "state": modified}, actor="agent")
            return True
        except ValueError:
            return False
    try:
        with ThreadPoolExecutor(2) as pool:
            first, second = pool.submit(claim), pool.submit(write)
            assert sum((first.result(), second.result())) == 1
    finally:
        other.close()
