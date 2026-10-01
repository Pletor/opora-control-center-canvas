import pytest

from backend.canvas.commit_pairs import CONFIDENCE, EVIDENCE_ORDER, owned_paths, pair_for_scope


def commit(sha, branches=(), paths=(), trailers=None, task=None, in_main=False, date=None):
    return {
        "sha": sha,
        "branches": list(branches),
        "paths": list(paths),
        "trailers": trailers or {},
        "task": task,
        "inMain": in_main,
        "date": date,
    }


def node(node_id, parent=None, path=None, kind="node"):
    source_ref = {"origin": "repo", "path": path, "kind": "file"} if path else None
    return {"id": node_id, "parentId": parent, "kind": kind, "sourceRef": source_ref}


def pair(commits, *, scope=None, workspace=None, owned=(), revision=1, saved_at="2026-09-01T10:00:00Z"):
    return pair_for_scope(
        scope=scope or {"kind": "node", "id": "node-1"},
        spec_revision=revision,
        spec_saved_at=saved_at,
        workspace=workspace,
        commits=commits,
        owned=list(owned),
    )


def test_evidence_order_and_confidence_are_the_contract():
    assert EVIDENCE_ORDER == ("trailer", "branch", "task", "paths")
    assert CONFIDENCE == {"trailer": "strong", "branch": "strong", "task": "strong", "paths": "weak"}


PAIRING = [
    (
        "branch",
        [commit("aaa", branches=["work/node-1"]), commit("bbb", branches=["other"])],
        {"branch": "work/node-1", "base_sha": "000", "node_id": "node-1"},
        (),
        ["aaa"],
        "branch",
        "strong",
    ),
    (
        "trailer nad vlastněnou cestou",
        [commit("aaa", trailers={"Opora-Node": ["node-1@2"]}, paths=["backend/canvas/graph.py"]),
         commit("bbb")],
        None,
        ("backend/canvas",),
        ["aaa"],
        "trailer",
        "strong",
    ),
    (
        "trailer bez cesty i větve je jen tvrzení",
        [commit("aaa", trailers={"Opora-Node": ["node-1@2"]}), commit("bbb")],
        None,
        (),
        ["aaa"],
        "trailer",
        "weak",
    ),
    (
        "task",
        [commit("aaa", task="HEL-42"), commit("bbb", task="HEL-9")],
        None,
        (),
        ["aaa"],
        "task",
        "strong",
    ),
    (
        "paths only is weak",
        [commit("aaa", paths=["backend/canvas/graph.py"]), commit("bbb", paths=["frontend/x.ts"])],
        None,
        ("backend/canvas",),
        ["aaa"],
        "paths",
        "weak",
    ),
    (
        "no commit at all",
        [],
        {"branch": "work/node-1", "base_sha": None, "node_id": "node-1"},
        ("backend/canvas",),
        [],
        "none",
        "none",
    ),
    (
        "commits but nothing matches",
        [commit("aaa", branches=["main"], paths=["docs/x.md"])],
        None,
        ("backend/canvas",),
        [],
        "none",
        "none",
    ),
    (
        "strongest evidence wins over weaker one",
        [commit("aaa", paths=["backend/canvas/graph.py"], branches=["work/node-1"])],
        {"branch": "work/node-1", "base_sha": None, "node_id": "node-1"},
        ("backend/canvas",),
        ["aaa"],
        "branch",
        "strong",
    ),
]


@pytest.mark.parametrize(
    "label, commits, workspace, owned, expected_shas, expected_evidence, expected_confidence",
    PAIRING,
    ids=[row[0] for row in PAIRING],
)
def test_pairing(label, commits, workspace, owned, expected_shas, expected_evidence, expected_confidence):
    scope = {"kind": "node", "id": "node-1", "task": "HEL-42"}
    result = pair(commits, scope=scope, workspace=workspace, owned=owned)
    assert result["gitCommits"] == expected_shas
    assert result["evidence"] == expected_evidence
    assert result["confidence"] == expected_confidence


def test_task_pairs_only_when_the_caller_supplies_it():
    commits = [commit("aaa", task="HEL-42")]
    assert pair(commits)["gitCommits"] == []
    with_task = pair(commits, scope={"kind": "node", "id": "node-1", "task": "HEL-42"})
    assert with_task["gitCommits"] == ["aaa"]
    assert with_task["task"] == "HEL-42"


def test_trailer_carries_revision_in_code():
    # Revizi hlásí jen commit, který se rozsahu dotkl cestou; cizí trailer nepočítá.
    owned = ("backend/canvas",)
    commits = [
        commit("aaa", trailers={"Opora-Node": ["node-1@1"]}, paths=["backend/canvas/a.py"]),
        commit("bbb", trailers={"Opora-Node": ["node-1@3", "node-2@9"]},
               paths=["backend/canvas/b.py"]),
        commit("ccc", trailers={"Opora-Node": ["node-2@7"]}),
    ]
    result = pair(commits, revision=3, owned=owned)
    assert result["gitCommits"] == ["aaa", "bbb"]
    assert result["revisionInCode"] == 3
    assert result["specRevision"] == 3


def test_forged_trailer_without_a_touched_path_carries_no_revision():
    # Kritik napíše revizi do zprávy commitu, ale na vlastněnou cestu nesáhne.
    result = pair([commit("aaa", trailers={"Opora-Node": ["node-1@99"]}, paths=["tools/nic.py"])],
                  revision=1, owned=("backend/canvas",))
    assert result["revisionInCode"] is None
    assert result["confidence"] == "weak"


def test_revision_in_code_is_none_without_a_trailer():
    result = pair([commit("aaa", branches=["w"])], workspace={"branch": "w"})
    assert result["revisionInCode"] is None


DIRECTORY_COVERAGE = [
    ("file directly inside", "backend/canvas", "backend/canvas/graph.py", True),
    ("file deeper inside", "backend/canvas", "backend/canvas/sub/deep.py", True),
    ("the directory itself", "backend/canvas", "backend/canvas", True),
    ("sibling with the same name prefix", "backend/canvas", "backend/canvas-old/x.py", False),
    ("sibling directory", "backend/canvas", "backend/editor/graph.py", False),
    ("exact file", "backend/canvas/graph.py", "backend/canvas/graph.py", True),
    ("file is not a directory", "backend/canvas/graph.py", "backend/canvas/graph.py.bak", False),
    ("trailing slash means the same", "backend/canvas/", "backend/canvas/graph.py", True),
    ("parent is not owned by a child", "backend/canvas/graph.py", "backend/canvas", False),
]


@pytest.mark.parametrize(
    "label, owned_path, commit_path, covered",
    DIRECTORY_COVERAGE,
    ids=[row[0] for row in DIRECTORY_COVERAGE],
)
def test_directory_covers_its_children_only(label, owned_path, commit_path, covered):
    result = pair([commit("aaa", paths=[commit_path])], owned=(owned_path,))
    assert result["gitCommits"] == (["aaa"] if covered else [])
    assert result["evidence"] == ("paths" if covered else "none")


def test_merged_to_main_and_last_commit_at():
    commits = [
        commit("aaa", branches=["w"], in_main=True, date="2026-09-01T10:00:00Z"),
        commit("bbb", branches=["w"], in_main=False, date="2026-09-30T10:00:00Z"),
        commit("ccc", branches=["w"], in_main=True, date="2026-09-12T08:00:00Z"),
    ]
    result = pair(commits, workspace={"branch": "w"})
    assert result["mergedToMain"] is True
    assert result["lastCommitAt"] == "2026-09-12T08:00:00Z"


def test_nothing_in_main_leaves_the_pair_open():
    commits = [commit("aaa", branches=["w"], in_main=False, date="2026-09-30T10:00:00Z")]
    result = pair(commits, workspace={"branch": "w"})
    assert result["mergedToMain"] is False
    assert result["lastCommitAt"] is None


def test_last_commit_at_compares_across_time_zones_and_survives_junk():
    across = [
        commit("aaa", branches=["w"], in_main=True, date="2026-09-12T09:00:00+02:00"),
        commit("bbb", branches=["w"], in_main=True, date="2026-09-12T08:30:00Z"),
    ]
    assert pair(across, workspace={"branch": "w"})["lastCommitAt"] == "2026-09-12T08:30:00Z"

    junk = [
        commit("aaa", branches=["w"], in_main=True, date="vcera"),
        commit("bbb", branches=["w"], in_main=True, date="predevcirem"),
    ]
    assert pair(junk, workspace={"branch": "w"})["lastCommitAt"] == "vcera"


def test_git_commits_keep_the_incoming_order_without_duplicates():
    commits = [
        commit("ccc", branches=["w"]),
        commit("aaa", branches=["w"]),
        commit("ccc", branches=["w"]),
        commit("bbb", branches=["w"]),
    ]
    assert pair(commits, workspace={"branch": "w"})["gitCommits"] == ["ccc", "aaa", "bbb"]


EMPTY_INPUTS = [
    ("no commits", [], None, ()),
    ("no workspace", [commit("aaa", branches=["w"])], None, ()),
    ("no owned paths", [commit("aaa", paths=["backend/canvas/graph.py"])], None, ()),
    ("empty owned path does not own the repository", [commit("aaa", paths=["x.py"])], None, ("",)),
    ("workspace without a branch", [commit("aaa", branches=["w"])], {"branch": None}, ()),
]


@pytest.mark.parametrize(
    "label, commits, workspace, owned", EMPTY_INPUTS, ids=[row[0] for row in EMPTY_INPUTS]
)
def test_empty_and_missing_inputs_do_not_fall_over(label, commits, workspace, owned):
    result = pair(commits, workspace=workspace, owned=owned, revision=0)
    assert result["gitCommits"] == []
    assert result["evidence"] == "none"
    assert result["confidence"] == "none"
    assert result["revisionInCode"] is None
    assert result["mergedToMain"] is False
    assert result["lastCommitAt"] is None
    assert result["specRevision"] == 0
    assert result["branch"] is None


def test_pair_repeats_the_scope_it_was_asked_about():
    scope = {"kind": "sector", "id": "sector-1"}
    result = pair([], scope=scope)
    assert result["scope"] == scope


def test_owned_paths_collects_the_scope_and_its_children():
    nodes = [
        node("sector-1", path="backend/canvas"),
        node("node-1", parent="sector-1", path="backend/canvas/graph.py"),
        node("node-2", parent="sector-1", path="backend/canvas/areas.py"),
        node("node-3", parent="node-1", path="backend/canvas/deep.py"),
        node("node-4", parent="node-1"),
        node("outside", path="frontend/app.tsx"),
    ]
    assert owned_paths("sector-1", nodes) == [
        "backend/canvas",
        "backend/canvas/areas.py",
        "backend/canvas/deep.py",
        "backend/canvas/graph.py",
    ]
    assert owned_paths("node-1", nodes) == ["backend/canvas/deep.py", "backend/canvas/graph.py"]
    assert owned_paths("node-4", nodes) == []
    assert owned_paths("missing", nodes) == []
    assert owned_paths("sector-1", []) == []


def test_owned_paths_does_not_loop_on_a_broken_graph():
    self_parent = [node("node-1", parent="node-1", path="a.py")]
    assert owned_paths("node-1", self_parent) == ["a.py"]

    ring = [
        node("node-1", parent="node-3", path="a.py"),
        node("node-2", parent="node-1", path="b.py"),
        node("node-3", parent="node-2", path="c.py"),
    ]
    assert owned_paths("node-1", ring) == ["a.py", "b.py", "c.py"]


def test_owned_paths_drops_duplicates_and_empty_paths():
    nodes = [
        node("sector-1", path="backend/canvas"),
        node("node-1", parent="sector-1", path="backend/canvas"),
        node("node-2", parent="sector-1", path="   "),
        node("node-3", parent="sector-1"),
    ]
    assert owned_paths("sector-1", nodes) == ["backend/canvas"]


def test_owned_paths_feeds_the_pair():
    nodes = [
        node("sector-1", path="backend/canvas"),
        node("node-1", parent="sector-1", path="backend/canvas/graph.py"),
    ]
    owned = owned_paths("sector-1", nodes)
    commits = [commit("aaa", paths=["backend/canvas/graph.py"]), commit("bbb", paths=["docs/x.md"])]
    result = pair(commits, scope={"kind": "sector", "id": "sector-1"}, owned=owned)
    assert result["gitCommits"] == ["aaa"]
    assert result["confidence"] == "weak"
