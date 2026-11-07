"""Cesta podle vodotisku (docs/navrhy/2026-11-06-linie-vodotisk-cesty.md): verified / claimed / inferred / missing."""
import pytest

from backend.agi_pletor.linie import trace as trace_mod
from backend.agi_pletor.linie import work
from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_work import NOW, agent_commit, setup  # noqa: F401 (fixture)
from backend.brain_opora.determinism.gate_payloads import GateError

NO_PR = {"pr_lookup": lambda root: {}}


def marked(repo, mark, name, branch="feat/uzel", text="x", base="develop"):
    exists = run(repo, "branch", "--list", branch)
    run(repo, "checkout", "-q", *([branch] if exists else ["-b", branch, base]))
    (repo / name).write_text(text, encoding="utf-8")
    run(repo, "add", name)
    run(repo, "commit", "-q", "-m", f"zápis {name}\n\nOpora-Mark: {mark}")
    sha = run(repo, "rev-parse", "HEAD")
    run(repo, "checkout", "-q", "main")
    return sha


def traced(service, repo, tmp_path, mark):
    return trace_mod.trace(service, "draft", "main", repo, mark, tmp_path, **NO_PR)


def test_verified_foreign_inferred_and_run(setup, tmp_path):  # noqa: F811
    service, repo, tid = setup
    mark = work.get(service, "draft", tid)["work"]["mark"]
    first = marked(repo, mark, "k.py", text=f"def hlavni():\n    pass\n\n\n# {mark}.2: proč tady\nx = 1\n")
    foreign = marked(repo, mark, "f.txt", branch="feat/cizi")
    plain = agent_commit(repo, name="bez.txt")
    work.run(service, "draft", tid, {"sessionId": "s1", "agent": "dev"}, NOW)  # fromSha = plain
    later = marked(repo, mark, "pozdeji.txt")
    work.report(service, "draft", tid, later, [], None, NOW, "agent:dev")

    found = traced(service, repo, tmp_path, mark)
    status = {c["sha"]: c["status"] for c in found["commits"]}
    assert status == {first: "verified", foreign: "claimed", plain: "inferred", later: "verified"}
    by_sha = {c["sha"]: c for c in found["commits"]}
    assert by_sha[later]["runId"] == found["runs"][0]["runId"] and by_sha[first]["runId"] is None
    assert found["runs"][0]["status"] == "verified" and found["revision"] is None
    (place,) = found["code"]
    assert (place["path"], place["line"], place["step"], place["symbol"], place["status"]) == ("k.py", 5, 2, "hlavni", "verified")
    kinds = {(g["kind"], g["ref"]) for g in found["gaps"]}
    assert ("commit_without_run", first[:7]) in kinds and ("mark_on_foreign_branch", foreign[:7]) in kinds
    assert ("no_card", "") in kinds and ("commit_without_run", later[:7]) not in kinds
    assert found["sentence"].startswith(f"{mark}: Proč a k čemu. (bez plánu, 1 relace, 4 commity, 1 místo v kódu)")
    assert set(found) == {"mark", "ticket", "card", "revision", "plan", "link", "runs", "commits", "code", "pr", "checks",
                          "acceptance", "merged", "preview", "gaps", "sentence"}


def test_code_in_file_untouched_by_task_is_claimed(setup, tmp_path):  # noqa: F811
    service, repo, tid = setup
    mark = work.get(service, "draft", tid)["work"]["mark"]
    run(repo, "checkout", "-q", "-b", "feat/uzel", "develop")
    (repo / "stary.py").write_text(f"def stary():\n    pass  # {mark}.1: jen tvrzení\n", encoding="utf-8")
    run(repo, "add", "stary.py"), run(repo, "commit", "-q", "-m", "cizí soubor")
    run(repo, "checkout", "-q", "main")  # commit je jen inferred, soubor tedy není změněn verified commitem
    head = run(repo, "rev-parse", "feat/uzel")
    work.report(service, "draft", tid, head, [], None, NOW, "human")
    found = traced(service, repo, tmp_path, mark)
    assert found["code"][0]["status"] == "claimed" and found["code"][0]["symbol"] == "stary"
    assert any(g["kind"] == "code_without_commit" for g in found["gaps"])


def test_unknown_mark_is_404(setup, tmp_path):  # noqa: F811
    service, _, _ = setup
    for mark in ("OP-000000", "--all", "OP-3f9a1c"):
        with pytest.raises(GateError) as caught:
            traced(service, setup[1], tmp_path, mark)
        assert caught.value.status == 404 and caught.value.code == "mark_not_found"
