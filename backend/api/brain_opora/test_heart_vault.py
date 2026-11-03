"""Schránka jako nástroj srdce (PR 8b) přes skutečnou aplikaci: `vault ls` vypíše briefy, brány a výzkumy,
`vault show` plné znění, `vault plan` dá dávku generátoru Schránky, kterou `plan --file` projde validací
`/api/canvas-plan`, blokace vrátí výčtem a token srdce cizího projektu generátor nezavolá. Model neběží."""
import json
from pathlib import Path

import pytest

from backend.brain_opora.determinism import tokens
from backend.brain_opora.heart import opora_heart
from backend.editor.brief_vault.test_brief_vault_discipline import HEADERS, post
from backend.editor.brief_vault.test_brief_vault_gates import root, vault_client, walk


def tool(*argv):
    try:
        return opora_heart.run(opora_heart.parser().parse_args(list(argv)))
    except opora_heart.Failure as failure:
        return failure.payload


def caller(client, token):
    def call(method, path, body=None, query=None, actor="heart"):
        headers = {**HEADERS, tokens.HEADER: token, "X-Opora-Actor": f"agent; name={actor}"}
        response = client.request(method, path, params=query, json=body, headers=headers)
        if response.status_code >= 400:
            raise opora_heart.Failure(opora_heart.server_failure(response.status_code, response.json()))
        return response.json()
    return call


@pytest.fixture
def heart(tmp_path, monkeypatch):
    """Schránka se dvěma briefy (jeden do synthesized) a výzkumem; pak zapnutá brána a `call` tokenem srdce."""
    for key, value in {"OPORA_PROJECT": "draft", "OPORA_WORKSPACE": "draft"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    with vault_client(tmp_path / "app") as client:
        ready = walk(client, root(client), "synthesized")
        other = post(client, op="create", scopeNodeId="s1", discipline="db", title="Tabulka zákazníků",
                     text="Tabulka se jménem a e-mailem.")["fragment"]
        research = post(client, op="research", fragmentId=other["id"], title="Unikátní e-mail",
                        text="Ověřit unikátní index.")["fragment"]
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        _, token = tokens.issue_heart(client.app_state.service, "draft", "draft")
        monkeypatch.setattr(opora_heart, "call", caller(client, token))
        yield client, {"ready": ready, "other": other, "research": research}


def test_ls_lists_briefs_gates_and_research_compactly(heart):
    _, ids = heart
    text = tool("vault", "ls")
    lines = text.splitlines()
    assert lines[0] == "SCHRÁNKA prostor draft · 3 položek"
    assert f"{ids['ready']['id']} · brief · Import · draft · be · brány scoped,weighed,synthesized" in lines
    assert f"{ids['other']['id']} · brief · Tabulka zákazníků · draft · db · brány žádné" in lines
    assert any(line.startswith(f"{ids['research']['id']} · research · Unikátní e-mail") for line in lines)
    gates = tool("vault", "ls", "--kind", "gate").splitlines()
    assert gates[0] == "SCHRÁNKA prostor draft · 1 položek (gate)" and gates[1].startswith(ids["ready"]["id"])
    assert tool("vault", "ls", "--kind", "research").splitlines()[1].startswith(ids["research"]["id"])
    assert tool("vault", "ls", "--q", "zákazník").splitlines()[1:] == [
        f"{ids['other']['id']} · brief · Tabulka zákazníků · draft · db · brány žádné"]
    assert tool("vault", "ls", "--q", "nic takového").splitlines()[1:] == ["- žádné"]


def test_ls_is_capped(heart, monkeypatch):
    monkeypatch.setattr(opora_heart, "VAULT_LINES", 1)
    lines = tool("vault", "ls").splitlines()
    assert len(lines) == 3 and lines[-1] == "… zkráceno: 1 z 3; zúž --kind nebo --q"


def test_show_returns_the_full_item_without_history_rows(heart):
    _, ids = heart
    found = tool("vault", "show", ids["other"]["id"])
    assert found["fragment"]["text"] == "Tabulka se jménem a e-mailem." and found["historyCount"] == 1
    assert "history" not in found and [kid["id"] for kid in found["children"]] == [ids["research"]["id"]]
    assert set(tool("vault", "show", ids["ready"]["id"])["gateDetail"]) == {"scoped", "weighed", "synthesized"}


def test_plan_writes_a_batch_that_plan_file_accepts_and_touches_nothing(heart):
    client, ids = heart
    digest = client.get("/api/view", params={"project": "draft", "workspace": "draft"}).json()["digest"]
    out = tool("vault", "plan", "--node", ids["ready"]["id"])
    assert out["path"] == "dilna/out/vault-plan.json" and out["nodes"] == 3 and out["skipped"] == 0
    assert len(out["hash"]) == 64 and "plan --file dilna/out/vault-plan.json" in out["next"]
    batch = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert [node["kind"] for node in batch["nodes"]] == ["area", "sector", "node"]
    assert client.get("/api/view", params={"project": "draft", "workspace": "draft"}).json()["digest"] == digest
    checked = tool("plan", "--file", out["path"], "--dry-run")
    assert checked["ok"] is True and checked["dryRun"] is True, checked


def test_plan_without_nodes_reports_the_blocked_briefs(heart):
    _, ids = heart
    refused = tool("vault", "plan")
    assert refused["status"] == 409 and refused["blockedTotal"] == 1
    assert refused["fragments"] == [{"id": ids["other"]["id"], "title": "Tabulka zákazníků", "reason": "no-synthesized"}]
    assert "synthesized" in refused["hint"]


def test_heart_token_of_another_project_is_refused(heart, monkeypatch):
    client, ids = heart
    other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()["id"]
    _, foreign = tokens.issue_heart(client.app_state.service, other, "draft")
    monkeypatch.setattr(opora_heart, "call", caller(client, foreign))
    refused = tool("vault", "plan", "--node", ids["ready"]["id"])
    assert refused["status"] == 403 and refused["code"] == "gate_scope"
