from pathlib import Path

import pytest

from backend.code_intelligence.scoped_lsp import CodeIntelligence, QueryRequest


class FakeProtocol:
    def __init__(self, result):
        self.result = result
        self.requests = []
        self.notifications = []
        self.closed = False

    def request(self, method, params, timeout):
        self.requests.append((method, params, timeout))
        if method == "initialize":
            return {"capabilities": {}}
        if method == "shutdown":
            return None
        return self.result

    def notify(self, method, params):
        self.notifications.append((method, params))

    def close(self):
        self.closed = True


def request(path="src/example.ts", operation="definition", line=0, character=0, language="typescript"):
    return QueryRequest(
        project="project",
        workspace="draft",
        language=language,
        path=path,
        operation=operation,
        line=line,
        character=character,
    )


def test_query_rejects_path_before_resolving_workspace_or_spawning(tmp_path):
    calls = []
    intelligence = CodeIntelligence(
        lambda project, workspace: calls.append((project, workspace)) or tmp_path,
        protocol_factory=lambda *args: pytest.fail("protocol must not start"),
    )

    with pytest.raises(ValueError, match="Neplatná relativní cesta"):
        intelligence.query(request(path="../outside.ts"))

    assert calls == []


def test_query_rejects_character_past_utf16_line_boundary(tmp_path):
    source = tmp_path / "src" / "example.ts"
    source.parent.mkdir()
    source.write_text("const a = 1;\n", encoding="utf-8")
    intelligence = CodeIntelligence(lambda *_: tmp_path, protocol_factory=lambda *args: pytest.fail("no spawn"))

    with pytest.raises(ValueError, match="character"):
        intelligence.query(request(character=13))


def test_definition_filters_location_outside_workspace_and_closes_protocol(tmp_path):
    source = tmp_path / "src" / "example.ts"
    source.parent.mkdir()
    source.write_text("const a = 1;\n", encoding="utf-8")
    inside = (tmp_path / "src" / "target.ts")
    inside.write_text("export const a = 1;\n", encoding="utf-8")
    outside = tmp_path.parent / "outside.ts"
    outside.write_text("export const secret = 1;\n", encoding="utf-8")
    fake = FakeProtocol([{"uri": inside.as_uri(), "range": {}}, {"uri": outside.as_uri(), "range": {}}])
    intelligence = CodeIntelligence(lambda *_: tmp_path, protocol_factory=lambda *args: fake)

    response = intelligence.query(request())

    assert response["status"] == "ok"
    assert response["results"] == [{"uri": inside.as_uri(), "range": {}}]
    assert fake.closed is True
    assert [item[0] for item in fake.requests] == ["initialize", "textDocument/definition", "shutdown"]
    assert [item[0] for item in fake.notifications] == ["initialized", "textDocument/didOpen", "exit"]


def test_document_symbols_request_is_scoped_to_open_document(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    fake = FakeProtocol([{"name": "value", "kind": 13, "range": {}, "selectionRange": {}}])
    intelligence = CodeIntelligence(lambda *_: tmp_path, protocol_factory=lambda *args: fake)

    response = intelligence.query(request(path="module.py", operation="documentSymbols", language="python"))

    assert response["results"] == [{"name": "value", "kind": 13, "range": {}, "selectionRange": {}}]
    method, params, _ = fake.requests[1]
    assert method == "textDocument/documentSymbol"
    assert params == {"textDocument": {"uri": source.as_uri()}}


def test_status_does_not_construct_protocol(tmp_path):
    intelligence = CodeIntelligence(
        lambda *_: tmp_path,
        protocol_factory=lambda *args: pytest.fail("GET status must not spawn a server"),
        node_executable="missing-node",
        launchers={"typescript": tmp_path / "missing-ts.mjs", "python": tmp_path / "missing-py.mjs"},
    )

    payload = intelligence.status("project", "draft")

    assert [provider["status"] for provider in payload["providers"]] == ["unavailable", "unavailable"]
    assert payload["semantic"]["status"] == "unavailable"


def test_status_accepts_optional_parent_semantic_status_without_importing_service(tmp_path):
    semantic = {"status": "configured", "reason": "local service connected"}
    intelligence = CodeIntelligence(lambda *_: tmp_path, semantic_status=lambda: semantic)

    payload = intelligence.status("project", "draft")

    assert payload["semantic"] == semantic


def test_status_fails_closed_when_optional_semantic_status_errors(tmp_path):
    intelligence = CodeIntelligence(lambda *_: tmp_path, semantic_status=lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    payload = intelligence.status("project", "draft")

    assert payload["semantic"]["status"] == "unavailable"
    assert "unavailable" in payload["semantic"]["reason"].lower()
