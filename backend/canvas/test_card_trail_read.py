"""Sběr faktů stopy: commity z hlášení (ohraničeně) a jejich soubory z gitu."""
import subprocess

from backend.canvas.card_trail_read import COMMITS, commit_files, commit_shas


def test_commit_shas_unique_valid_and_bounded():
    evidence = {"notes": "", "commits": ["a" * 40, "not a sha", "a" * 40]}
    runs = [{"receipts": [{"result": {"stepResults": [{"stepId": "s1", "evidence": evidence}]}}],
             "checkpoints": [{"stepId": "s1", "evidence": {"commits": ["b" * 40]}}]}]
    tickets = [{"delivery": {"sha": "c" * 40}}, {"delivery": None}]
    assert commit_shas(runs, tickets) == ["a" * 40, "b" * 40, "c" * 40]
    many = [{"receipts": [], "checkpoints": [{"evidence": {"commits": [f"{index:040x}"]}} for index in range(50)]}]
    assert len(commit_shas(many, [])) == COMMITS


def test_commit_files_from_git_or_none_without_repo(tmp_path):
    assert commit_files(None, ["a" * 40]) is None

    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True).stdout

    git("init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init")
    sha = git("rev-parse", "HEAD").strip()
    assert commit_files(str(tmp_path), [sha, "d" * 40]) == {sha: ["src/a.py"], "d" * 40: []}
