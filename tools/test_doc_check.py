"""Testy pro doc_check běží výhradně nad dočasným stromem v tmp_path, nikdy nad skutečným repozitářem."""

from pathlib import Path

from tools.doc_check import (
    check_file,
    check_repo,
    collect_references,
    is_repo_path,
    main,
    markdown_files,
)


def _write(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_markdown_files_skips_skip_dirs(tmp_path):
    _write(tmp_path, "docs/a.md", "a")
    _write(tmp_path, "node_modules/pkg/README.md", "b")
    _write(tmp_path, ".git/COMMIT_EDITMSG.md", "c")
    _write(tmp_path, "backend/README.md", "d")

    found = markdown_files(tmp_path)

    rels = sorted(str(p.relative_to(tmp_path)).replace("\\", "/") for p in found)
    assert rels == ["backend/README.md", "docs/a.md"]


def test_collect_references_markdown_link_with_title():
    text = 'See [the doc](docs/guide.md "Guide title") for more.'
    assert collect_references(text) == [(1, "docs/guide.md")]


def test_collect_references_backtick_path():
    text = "Run `tools/opora.py` first."
    assert collect_references(text) == [(1, "tools/opora.py")]


def test_collect_references_ignores_code_block():
    text = "\n".join(
        [
            "before",
            "```",
            "`tools/inside_block.py` should not count",
            "```",
            "after `tools/outside_block.py` counts",
        ]
    )
    refs = collect_references(text)
    assert refs == [(5, "tools/outside_block.py")]


def test_collect_references_strips_anchor_and_punctuation():
    text = "See `docs/plan.md#section`, then `docs/other.md`."
    assert collect_references(text) == [(1, "docs/plan.md"), (1, "docs/other.md")]


def test_is_repo_path_wants_at_least_two_segments():
    assert is_repo_path("tools/doc_check.py") is True
    assert is_repo_path("docs/architecture/") is True
    # Samotné jméno souboru je zmínka, ne odkaz na místo.
    assert is_repo_path("README.md") is False
    assert is_repo_path("just_a_word") is False
    # Jedno jméno s lomítkem je konvence složky, ne cesta.
    assert is_repo_path("logic/") is False


def test_is_repo_path_rejects_mime_types_and_git_refs():
    assert is_repo_path("application/x-opora-catalog-item") is False
    assert is_repo_path("refs/heads/main") is False
    assert is_repo_path("~/.claude/skills/opora") is False


def test_is_repo_path_rejects_urls_anchors_and_wildcards():
    assert is_repo_path("https://example.com/x.py") is False
    assert is_repo_path("mailto:foo@example.com") is False
    assert is_repo_path("#anchor-only") is False
    assert is_repo_path("docs/<name>/file.md") is False
    assert is_repo_path("docs/*.md") is False


def test_is_repo_path_rejects_api_routes_outside_repo_and_skip_dirs():
    assert is_repo_path("/api/projects/{id}") is False
    assert is_repo_path("../outside/repo.md") is False
    assert is_repo_path("node_modules/pkg/index.js") is False


def test_check_file_existing_and_missing_path(tmp_path):
    _write(tmp_path, "tools/real.py", "print('hi')")
    doc = _write(
        tmp_path,
        "docs/plan.md",
        "\n".join(
            [
                "See `tools/real.py` for the real thing.",
                "See `tools/missing.py` for the missing one.",
            ]
        ),
    )

    findings = check_file(tmp_path, doc)

    assert findings == [{"doc": "docs/plan.md", "line": 2, "path": "tools/missing.py"}]


def test_check_file_resolves_relative_to_doc_folder(tmp_path):
    _write(tmp_path, "docs/sibling.md", "content")
    doc = _write(tmp_path, "docs/plan.md", "See `sibling.md` next to this doc.")

    findings = check_file(tmp_path, doc)

    assert findings == []


def test_check_repo_sorted_by_doc_then_line(tmp_path):
    _write(
        tmp_path,
        "docs/b.md",
        "\n".join(["ok line", "See `docs/missing_b.md` here."]),
    )
    _write(tmp_path, "docs/a.md", "See `docs/missing_a.md` here.")

    findings = check_repo(tmp_path)

    assert findings == [
        {"doc": "docs/a.md", "line": 1, "path": "docs/missing_a.md"},
        {"doc": "docs/b.md", "line": 2, "path": "docs/missing_b.md"},
    ]


def test_main_returns_zero_on_clean_tree(tmp_path, capsys):
    _write(tmp_path, "tools/real.py", "print('hi')")
    _write(tmp_path, "docs/plan.md", "See `tools/real.py` for the real thing.")

    exit_code = main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "0" in out


def test_main_returns_one_on_broken_tree(tmp_path, capsys):
    _write(tmp_path, "docs/plan.md", "See `tools/missing.py` for the missing one.")

    exit_code = main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "tools/missing.py" in out


def test_line_suffix_in_reference_is_stripped():
    assert collect_references("viz `backend/canvas/graph.py:42`") == [(1, "backend/canvas/graph.py")]
    assert collect_references("viz `backend/canvas/graph.py:42-60`") == [
        (1, "backend/canvas/graph.py")
    ]


def test_reference_may_resolve_against_any_parent_folder(tmp_path):
    # README uvnitř frontendu píše cesty od kořene frontendu.
    _write(tmp_path, "frontend/layout/navbar/logic/navbar.ts", "export {};")
    doc = _write(tmp_path, "frontend/ui-kit/icon/README.md", "viz `layout/navbar/logic/navbar.ts`")
    assert check_file(tmp_path, doc) == []


def test_two_words_with_slash_are_not_a_path(tmp_path):
    doc = _write(tmp_path, "docs/note.md", "metody `GET/POST` a `incoming/outgoing`")
    assert check_file(tmp_path, doc) == []


def test_pytest_node_id_is_reduced_to_its_file(tmp_path):
    _write(tmp_path, "backend/memory/test_roles.py", "print('x')")
    doc = _write(tmp_path, "docs/note.md", "viz `backend/memory/test_roles.py::test_reload`")
    assert check_file(tmp_path, doc) == []
