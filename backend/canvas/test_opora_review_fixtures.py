"""Real SQLite/project fixture; remote GitHub observation is deterministic and offline."""
from copy import deepcopy

import pytest

from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.test_canvas_service import managed_fixture
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_review_status import snapshot

HUMAN = {"kind": "human", "name": "Reviewer"}
AGENT = {"kind": "agent", "name": "Builder"}


def configure(service, pid, url="https://github.com/owner/repo.git", branch="main"):
    with service.registry_lock, service.db:
        service.db.execute("UPDATE projects SET url=?,branch=? WHERE id=?", (url, branch, pid))
    folder = service.folder(pid)
    identity = folder.read()
    identity["source"] = {"kind": "git", "value": url, "branch": branch}
    folder._write(identity)


def setup(service, pid):
    configure(service, pid)
    workspace = service._add_worktree(pid, "card", "Test agent")["id"]
    view = service.view(pid, workspace)
    service.save_graph(pid, workspace, {"nodes": [node("card")], "edges": []}, view["digest"])
    changesets = OporaChangesets(service)
    current = changesets.context(pid, workspace)
    scope = {"project": pid, "workspace": workspace}
    baseline = changesets.baseline({**scope, "subject": "Initial specs", "expectedAcceptedHead": None,
                                   "expectedGraphDigest": current["graphDigest"],
                                   "expectedSpecificationsVersion": current["specificationsVersion"]}, HUMAN)
    return {**scope, "expectedAcceptedHead": baseline["id"], "prNumber": 1}


@pytest.fixture(name="evidence_project")
def evidence_project(tmp_path):
    service, project = managed_fixture(tmp_path)
    payload = setup(service, project['id'])
    yield service, payload
    service.close()


class Reader:
    def __init__(self, payload):
        self.calls = []
        self.result = snapshot()
        for key in ("project", "workspace", "acceptedRevision"):
            self.result.pop(key)
        self.result["pr"]["baseRef"] = "main"
        self.result["reviews"][0]["body"] = f"Opora-Plan: {payload['project']}/{payload['workspace']}@{payload['expectedAcceptedHead']}"
        self.before_read = lambda: None

    def read(self, repository, number):
        self.calls.append((repository, number))
        self.before_read()
        return deepcopy(self.result)


