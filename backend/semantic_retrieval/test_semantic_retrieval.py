import json
from pathlib import Path

import pytest

from backend.semantic_retrieval.service import SemanticRetrieval


class Roots:
    def __init__(self, root: Path):
        self.root_path = root

    def root(self, project, workspace):
        assert (project, workspace) == ("project-1", "draft")
        return self.root_path


def configured_model(tmp_path: Path) -> Path:
    model = tmp_path / "model"
    model.mkdir()
    (model / "manifest.json").write_text(json.dumps({
        "repo": "Xenova/multilingual-e5-small",
        "revision": "761b726dd34fb83930e26aab4e9ac3899aa1fa78",
        "files": {"onnx/model_quantized.onnx": "hash", "tokenizer.json": "hash", "config.json": "hash"},
    }), encoding="utf-8")
    for name in ("onnx/model_quantized.onnx", "tokenizer.json", "config.json"):
        target = model / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture")
    return model


def test_status_is_cold_and_never_starts_inference(tmp_path):
    calls = []
    retrieval = SemanticRetrieval(Roots(tmp_path), model_dir=configured_model(tmp_path), runner=lambda *args: calls.append(args))

    result = retrieval.status("project-1", "draft")

    assert result == {
        "status": "configured",
        "model": "Xenova/multilingual-e5-small@761b726dd34fb83930e26aab4e9ac3899aa1fa78",
        "detail": "Local model files are configured; inference remains cold until an explicit query.",
        "localOnly": True,
    }
    assert calls == []


def test_query_scans_only_scoped_safe_sources_and_ranks_worker_scores(tmp_path):
    root = tmp_path / "source"
    (root / "src").mkdir(parents=True)
    (root / "src" / "relevant.py").write_text("def hatch_bird():\n    return 'egg opens into a chick'\n", encoding="utf-8")
    (root / "src" / "other.ts").write_text("export const weather = 'rain';\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude" / "secret.md").write_text("must never be read", encoding="utf-8")
    received = []

    def runner(query, chunks):
        received.extend(chunks)
        assert query == "how does an egg become a baby bird"
        return [0.92 if chunk["path"] == "src/relevant.py" else 0.03 for chunk in chunks]

    retrieval = SemanticRetrieval(Roots(root), model_dir=configured_model(tmp_path), runner=runner)
    result = retrieval.query({"project": "project-1", "workspace": "draft", "path": "src", "query": "how does an egg become a baby bird", "limit": 4})

    assert [item["path"] for item in result["results"]] == ["src/relevant.py", "src/other.ts"]
    assert result["results"][0]["startLine"] == 1 and result["results"][0]["endLine"] == 2
    assert result["results"][0]["score"] == 0.92
    assert result["filesScanned"] == 2 and result["chunksIndexed"] == 2 and result["truncated"] is False
    assert all("secret" not in item["path"] and "must never" not in item["text"] for item in received)


@pytest.mark.parametrize("path", ["", "../outside", ".claude", "src/../other.py", "node_modules"])
def test_query_rejects_unscoped_or_protected_paths_before_filesystem_access(tmp_path, path):
    retrieval = SemanticRetrieval(Roots(tmp_path), model_dir=configured_model(tmp_path), runner=lambda *_: pytest.fail("worker must not run"))

    with pytest.raises(ValueError):
        retrieval.query({"project": "project-1", "workspace": "draft", "path": path, "query": "hello", "limit": 1})


def test_query_skips_symlink_and_oversized_sources(tmp_path):
    root = tmp_path / "source"
    scope = root / "scope"
    scope.mkdir(parents=True)
    (scope / "safe.py").write_text("def safe():\n    return True\n", encoding="utf-8")
    (scope / "oversized.md").write_bytes(b"x" * (128 * 1024 + 1))
    linked = scope / "linked.py"
    try:
        linked.symlink_to(scope / "safe.py")
    except OSError:
        pytest.skip("Symlink permissions are unavailable to this Windows user.")
    retrieval = SemanticRetrieval(Roots(root), model_dir=configured_model(tmp_path), runner=lambda _query, chunks: [0.7] * len(chunks))

    result = retrieval.query({"project": "project-1", "workspace": "draft", "path": "scope", "query": "safe", "limit": 5})

    assert result["filesScanned"] == 1 and [item["path"] for item in result["results"]] == ["scope/safe.py"]


def test_query_caps_files_and_chunks_deterministically(tmp_path):
    root = tmp_path / "source"
    scope = root / "scope"
    scope.mkdir(parents=True)
    for index in range(70):
        (scope / f"{index:03}.md").write_text("\n".join(f"line {line}" for line in range(41)), encoding="utf-8")

    retrieval = SemanticRetrieval(Roots(root), model_dir=configured_model(tmp_path), runner=lambda _query, chunks: [0.5] * len(chunks))
    result = retrieval.query({"project": "project-1", "workspace": "draft", "path": "scope", "query": "line", "limit": 20})

    assert result["filesScanned"] == 64 and result["chunksIndexed"] == 128 and result["truncated"] is True
    assert [item["path"] for item in result["results"]][:2] == ["scope/000.md", "scope/000.md"]
