"""The three additional reads retain native source authority and never apply the generated plan."""
from backend.api.brain_opora.test_canvas_capability_routes import SCOPE, call
from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.brain_opora.determinism import tokens
from backend.editor.brief_vault.test_brief_vault_gates import root, vault_client, walk
from backend.editor.brief_vault.test_brief_vault_placement import plan, state, stored, view
from backend.editor.node.test_removals import HEADERS
from backend.integrations import mirror_client
from backend.project.design import design_system
from backend.project.design.test_design_system import repository

setup = capability_setup


def test_mirror_and_committed_design_match_native_reads_and_reject_foreign_scope(setup, tmp_path, monkeypatch):
    client, service, auth = setup
    monkeypatch.setattr(mirror_client, "client_for", lambda project: None)
    mirror = call(client, auth, "brief_vault_routes.brief_vault_mirror")
    assert mirror.status_code == 200, mirror.text
    assert mirror.json()["result"] == client.get("/api/brief-vault/mirror", params=SCOPE).json()
    repo = repository(tmp_path, b"# Committed design\n")
    monkeypatch.setattr(design_system, "main_project_root", lambda service, project: repo)
    (repo / "DESIGN.md").write_text("Uncommitted change", encoding="utf-8")
    result = call(client, auth, "design_system_routes.read")
    assert result.status_code == 200, result.text
    assert result.json()["result"] == design_system.read(service, "draft")
    assert result.json()["result"]["markdown"] == "# Committed design\n"
    for op in ("brief_vault_routes.brief_vault_mirror", "brief_vault_routes.brief_vault_plan", "design_system_routes.read"):
        data = {"fragmentIds": []} if op.endswith("_plan") else {}
        assert call(client, auth, op, data, scope={**SCOPE, "workspace": "foreign"}).status_code == 403
    monkeypatch.setattr(design_system, "main_project_root", lambda service, project: None)
    assert call(client, auth, "design_system_routes.read").json()["result"]["available"] is False


def test_native_vault_plan_parity_full_readback_and_no_mutation(tmp_path):
    with vault_client(tmp_path) as client:
        service = client.app.state.service
        _, token = tokens.issue_heart(service, "draft", "draft")
        auth = {**HEADERS, tokens.HEADER: token, "X-Opora-Actor": "agent; name=heart"}
        fragment = walk(client, root(client), "synthesized")
        def snapshot():
            current = view(client)
            return current["graph"], current["digest"], state(client), stored(client, fragment["id"])
        before = snapshot()
        expected = plan(client, [fragment["id"]])
        actual = call(client, auth, "brief_vault_routes.brief_vault_plan", {"fragmentIds": [fragment["id"]]})
        assert actual.status_code == 200, actual.text
        assert actual.json()["result"] == expected
        assert actual.json()["state"] == "read"
        assert snapshot() == before
        bad = call(client, auth, "brief_vault_routes.brief_vault_plan", {"fragmentIds": "not-an-array"})
        assert bad.status_code == 400, bad.text
        blocked = call(client, auth, "brief_vault_routes.brief_vault_plan", {"fragmentIds": ["missing"]})
        assert blocked.status_code == 409, blocked.text
