"""Detail commitu (docs/navrhy/2026-11-06-linie-detail-commitu.md): ticket podle větve a rozsahu, bez ticketu pravda."""
import pytest

from backend.agi_pletor.linie import commit as commit_mod
from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_work import agent_commit, setup  # noqa: F401 (fixture)
from backend.brain_opora.determinism.gate_payloads import GateError

NO_PR = {"pr_lookup": lambda root: {}}


def test_commit_with_ticket_and_without(setup, tmp_path):  # noqa: F811
    service, repo, tid = setup
    sha = agent_commit(repo)  # na feat/uzel z develop = rozsah ticketu
    found = commit_mod.detail(service, "draft", "main", repo, sha[:7], tmp_path, **NO_PR)
    assert found["commit"]["sha"] == sha and found["commit"]["files"] == 1 and found["commit"]["paths"] == ["u.txt"]
    assert found["commit"]["branches"] == ["feat/uzel"] and found["commit"]["stat"].startswith("1 file changed")
    ticket = found["ticket"]
    assert ticket["ticketId"] == tid and ticket["state"] == "open" and ticket["body"]["essence"] == "Proč a k čemu."
    assert ticket["card"] is None and ticket["office"] is None and ticket["plan"] == []
    assert found["sentence"].startswith(f"Commit {sha[:7]} na feat/uzel: přidán u.txt. Plán: Proč a k čemu. (karta bez karty")

    base = run(repo, "rev-parse", "develop")  # výchozí commit větve není prací ticketu
    found = commit_mod.detail(service, "draft", "main", repo, base, tmp_path, pr_lookup=lambda root: {"feat/uzel": {"number": 3, "state": "OPEN", "url": "u"}})
    assert found["ticket"] is None and found["pr"] == {"number": 3, "state": "OPEN", "url": "u"}
    assert found["sentence"].endswith("Bez evidovaného plánu (žádný ticket). PR #3 OPEN.")
    with pytest.raises(GateError) as caught:
        commit_mod.detail(service, "draft", "main", repo, "0000000", tmp_path, **NO_PR)
    assert caught.value.status == 404


def test_trailer_names_card_and_preview_matches_branch(setup, tmp_path):  # noqa: F811
    service, repo, _ = setup
    run(repo, "checkout", "-q", "-b", "feat/uzel", "develop")
    (repo / "k.txt").write_text("k", encoding="utf-8")
    run(repo, "add", "k.txt"), run(repo, "commit", "-q", "-m", "karta\n\nOpora-Node: hero")
    sha = run(repo, "rev-parse", "HEAD")
    run(repo, "checkout", "-q", "main")
    folder = tmp_path / "pletor"
    (folder / "linie").mkdir(parents=True)
    (folder / "linie" / "previews.json").write_text(
        f'{{"p": {{"slug": "p", "branch": "feat/uzel", "state": "running", "sha": "{sha}", "port": 1, "url": "http://x"}}}}',
        encoding="utf-8")
    found = commit_mod.detail(service, "draft", "main", repo, sha, folder, **NO_PR)
    assert found["commit"]["trailers"] == {"node": "hero", "execution": None}
    assert found["ticket"]["card"]["id"] == "hero" and "ohCard=hero" in found["ticket"]["card"]["link"]
    assert found["preview"] is None  # port 1 neposlouchá → náhled není živý
