"""Library integration fixtures use real accepted specs and sparse execution claims."""
import pytest

from backend.canvas.test_opora_changesets import accept
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.library.test_harness_kit import kit, propose_kit


@pytest.fixture
def learning_plan(sparse):
    graphs, _, _ = sparse
    steps = [{"id": "s1", "order": 1, "title": "Implement", "acceptance": ["Checks pass"],
              "dependsOn": [], "kind": "code", "files": []}]
    proposal, head = propose_kit(sparse, kit(), {"steps": steps})
    accept(graphs.service, proposal, head)
    return sparse


@pytest.fixture
def learning_run(learning_plan):
    graphs, authority, refs = learning_plan
    return graphs.service, authority, refs, claimed(learning_plan)
