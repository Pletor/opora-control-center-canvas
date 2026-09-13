import subprocess

from backend.domain.service import CanvasService


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_sync_picks_up_only_merged_upstream_revision(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "Fixture")
    git(upstream, "config", "user.email", "fixture@example.invalid")
    (upstream / "README.md").write_text("base")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "base")
    service = CanvasService(tmp_path / "data")
    repo = tmp_path / "data" / "projects" / "fixture" / "main"
    repo.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(upstream), str(repo)], check=True, capture_output=True)
    service.register_repository("fixture", "Fixture", str(repo), str(upstream), "main")
    git(upstream, "checkout", "-b", "verified-change")
    (upstream / "README.md").write_text("verified merge fixture")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "verified change")
    git(upstream, "checkout", "main")
    git(upstream, "merge", "--ff-only", "verified-change")
    expected = git(upstream, "rev-parse", "HEAD")
    assert git(repo, "rev-parse", "HEAD") != expected
    service.sync("fixture")
    service.pool.shutdown(wait=True)
    assert service.bootstrap()["jobs"][0]["status"] == "complete"
    assert git(repo, "rev-parse", "HEAD") == expected
    assert (repo / "README.md").read_text() == "verified merge fixture"
    service.close()


def test_dirty_main_is_never_reset_by_sync(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "Fixture")
    git(upstream, "config", "user.email", "fixture@example.invalid")
    (upstream / "README.md").write_text("base")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "base")
    service = CanvasService(tmp_path / "data")
    repo = tmp_path / "data" / "projects" / "fixture" / "main"
    repo.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(upstream), str(repo)], check=True, capture_output=True)
    service.register_repository("fixture", "Fixture", str(repo), str(upstream), "main")
    (repo / "README.md").write_text("do not overwrite")
    service.sync("fixture")
    service.pool.shutdown(wait=True)
    assert service.bootstrap()["jobs"][0]["status"] == "failed"
    assert (repo / "README.md").read_text() == "do not overwrite"
    service.close()
