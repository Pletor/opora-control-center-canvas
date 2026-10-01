"""Live probes against the installed Opory launchers: actual definition, not initialize-only."""

from pathlib import Path
from urllib.parse import unquote, urlparse

from backend.code_intelligence.scoped_lsp import CodeIntelligence, QueryRequest
from backend.paths import REPO_ROOT


def _definition(root, language, path, line, character):
    adapter = CodeIntelligence(lambda *_: root, server_cwd=REPO_ROOT, operation_timeout=15)
    return adapter.query(QueryRequest("fixture", "draft", language, path, "definition", line, character))


def _same_file_uri(uri, source):
    decoded = unquote(urlparse(uri).path)
    if len(decoded) >= 3 and decoded[0] == "/" and decoded[2] == ":":
        decoded = decoded[1:]
    return Path(decoded).resolve() == source.resolve()


def test_typescript_launcher_returns_definition_from_isolated_fixture(tmp_path):
    source = tmp_path / "symbols.ts"
    source.write_text("export const target = 42;\nexport const use = target;\n", encoding="utf-8")

    response = _definition(tmp_path, "typescript", "symbols.ts", 1, 19)

    assert response["status"] == "ok", response["detail"]
    assert response["results"]
    location = response["results"][0]
    assert _same_file_uri(location.get("targetUri", location.get("uri")), source)


def test_pyright_launcher_returns_definition_from_isolated_fixture(tmp_path):
    source = tmp_path / "symbols.py"
    source.write_text("target = 42\nuse = target\n", encoding="utf-8")

    response = _definition(tmp_path, "python", "symbols.py", 1, 6)

    assert response["status"] == "ok", response["detail"]
    assert response["results"]
    location = response["results"][0]
    assert _same_file_uri(location.get("targetUri", location.get("uri")), source)
