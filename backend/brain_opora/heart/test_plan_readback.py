import json

import pytest

from backend.brain_opora.heart import opora_heart as cli


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPORA_PROJECT", "p")
    monkeypatch.setenv("OPORA_WORKSPACE", "main")
    cli._override["workspace"] = None
    (tmp_path / cli.ACTIVE).write_text('{"workspace":"w"}')


@pytest.mark.parametrize("project,explicit,current,expected,source", [
    ("p", None, "main", "w", "active"),
    ("p", None, "current", "current", "current"),
    ("p", "main", "main", "main", "explicit"),
    ("other", None, "main", None, "project_home"),
])
def test_context_scope_preserves_explicit_and_foreign_home(env, monkeypatch, project, explicit, current, expected, source):
    monkeypatch.setenv("OPORA_WORKSPACE", current)
    monkeypatch.setattr(cli, "call", lambda *a, **kw: {"workspaces": [{"id": "w"}]})
    observed = []
    monkeypatch.setattr(cli, "load_context", lambda *args: observed.append(args) or {})
    argv = ["ctx", "plan-of", "--project", project] + (["--workspace", explicit] if explicit else [])
    result = cli.run(cli.parser().parse_args(argv))
    assert observed[0][2] == expected
    assert (result["workspace"], result["workspaceSource"]) == (expected, source)


def test_deleted_active_workspace_is_not_used(env, monkeypatch):
    monkeypatch.setattr(cli, "call", lambda *a, **kw: {"workspaces": []})
    monkeypatch.setattr(cli, "load_context", lambda *args: {})
    result = cli.run(cli.parser().parse_args(["ctx", "plan-of", "--project", "p"]))
    assert result["workspace"] == "main"


@pytest.mark.parametrize("failed", [False, True, "wrong_scope", "missing_node", "changed_spec", "missing_edge"])
def test_default_plan_saves_proposal_without_accept_and_verifies_receipt(env, monkeypatch, tmp_path, failed):
    plan = {"nodes": [{"ref": "task", "kind": "node", "name": "Partial plan"}], "edges": []}
    filename = tmp_path / "plan.json"
    filename.write_text(json.dumps(plan))
    calls = []
    receipt = {"id": "proposal", "refs": {"task": "n"},
               "additions": {"nodes": [{"id": "n", "name": "Partial plan"}], "edges": [{"id": "e", "source": "n"}]},
               "specifications": [{"nodeId": "n", "fields": {"goal": "Required outcome"}}]}

    def call(method, path, body=None, query=None):
        calls.append((method, path))
        if path.endswith("/context"):
            return {"graphManifestId": "m", "acceptedHead": "r", "graphDigest": "d"}
        if method == "POST":
            assert path == cli.GRAPH_PROPOSALS
            return receipt
        if failed is True:
            raise cli.Failure({"error": "temporary read outage"})
        saved = json.loads(json.dumps(receipt))
        saved.update(project="p", workspace="foreign" if failed == "wrong_scope" else "w", parentRevision="r", accepted=False)
        if failed == "missing_node":
            saved["additions"]["nodes"] = []
        if failed == "missing_edge":
            saved["additions"]["edges"] = []
        if failed == "changed_spec":
            saved["specifications"][0]["fields"]["goal"] = "Different outcome"
        return saved

    monkeypatch.setattr(cli, "call", call)
    result = cli.run(cli.parser().parse_args(["plan", "--file", str(filename), "--workspace", "w"]))
    assert result["accepted"] is False and result["persisted"] is True
    assert result["verified"] is (not failed)
    assert result["ok"] is (not failed)
    assert result["workspace"] == "w" and result["proposalId"] == "proposal"
    assert calls == [("GET", cli.GRAPH_PROPOSALS + "/context"), ("POST", cli.GRAPH_PROPOSALS),
                     ("GET", cli.GRAPH_PROPOSALS + "/proposal")]
    if failed:
        assert result["code"] == "plan_readback_failed"
    else:
        assert result["readback"]["nodeIds"] == ["n"]


def test_accept_is_explicit_and_no_accept_remains_compatible():
    assert cli.parser().parse_args(["plan"]).no_accept is True
    assert cli.parser().parse_args(["plan", "--no-accept"]).no_accept is True
    assert cli.parser().parse_args(["plan", "--accept"]).no_accept is False
