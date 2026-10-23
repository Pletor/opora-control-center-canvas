"""GitHub jako jediná simulovaná část varianty B: čtení PR a ohlášení sloučení, offline a deterministicky."""
from __future__ import annotations

import subprocess

REPOSITORY = "sim/ample"


def _configure(service, pid, url="https://github.com/sim/ample.git", branch="main"):
    with service.registry_lock, service.db:
        service.db.execute("UPDATE projects SET url=?,branch=? WHERE id=?", (url, branch, pid))
    folder = service.folder(pid)
    identity = folder.read()
    identity["source"] = {"kind": "git", "value": url, "branch": branch}
    folder._write(identity)


def managed_project(root, upstream, first_card):
    """Spravovaný projekt s gitem a pracovní větví (bez toho OporaHub nepřipojí PR)."""
    from backend.canvas.canvas_service import CanvasService

    service = CanvasService(root / "data")
    managed = root / "data" / "projects" / "sim" / "main"
    managed.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", str(upstream.path), str(managed)], check=True, capture_output=True)
    project = service.register_repository("sim", "Sim ample", str(managed), "fixture://local", "main")
    _configure(service, project["id"])
    workspace = service._add_worktree(project["id"], first_card, "sim agent")["id"]
    service.close()
    return {"project": project["id"], "workspace": workspace}


class FakeGitHub:
    """Odpověď GitHubu na čtení PR: číslo a hlava přesně podle toho, co office ohlásí."""
    heads: dict = {}  # noqa: RUF012 - sdílené mezi instalací a čtením

    @classmethod
    def install(cls):
        from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader

        def pull_request(self, repository, number):
            return {"repository": {"id": 1, "fullName": REPOSITORY}, "id": 1000 + number, "number": number,
                    "baseRef": "main", "headRef": f"work/card-{number}", "headSha": cls.heads[number],
                    "headRepoId": 2, "state": "open", "body": ""}
        original = GitHubPullRequestLinkReader.pull_request
        GitHubPullRequestLinkReader.pull_request = pull_request
        return lambda: setattr(GitHubPullRequestLinkReader, "pull_request", original)


def merged(service, scope, index, link):
    """GitHub ohlásí sloučení; smyčka uzavření běhu zapíše plán zpět (jako backendové testy)."""
    from backend.canvas.opora_execution_pr_closure import close_loop
    from database.repositories.opora_reconciliation import ReconciliationRepository
    from database.repositories.opora_reconciliation_jobs import stamp

    s, number = scope, 100 + index
    db = service.db_for(s["project"])
    with service.graph_lock_for(s["project"]), service.lock_for(s["project"]):
        repo = ReconciliationRepository(db, s["project"], s["workspace"])
        with db:
            db.execute("BEGIN IMMEDIATE")
            repo.insert("observation", {"schemaVersion": 1, **s, "bindingId": link["bindingId"], "createdAt": stamp(2000 + index),
                "data": {"complete": True, "observedFrom": stamp(1999 + index), "observedUntil": stamp(2000 + index),
                         "repository": {"id": 1, "fullName": REPOSITORY},
                         "pr": {"id": 1000 + number, "number": number, "baseRef": "main", "headSha": FakeGitHub.heads[number],
                                "headRepoId": 2, "state": "merged", "draft": False, "merged": True,
                                "mergedAt": stamp(1990 + index), "mergeCommitSha": FakeGitHub.heads[number]}}})
        with db:
            db.execute("BEGIN IMMEDIATE")
            return close_loop(db, s["project"], s["workspace"])
