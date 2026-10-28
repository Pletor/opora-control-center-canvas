"""Lokální sloučení karty v projektu bez GitHubu (docs/lokalni-slouceni.md).

Agent nebo člověk ohlásí commit, který už je v cílové větvi repozitáře projektu (lokální projekt =
aktuální větev jeho repa). Server to ověří přes git (mimo zámky), zapíše vazbu stejného tvaru jako PR
(`state: "merged"`, `source: "local"`, `commit`) do tabulky vazeb PR a provede tentýž zápis plánu zpět
jako po sloučeném PR (`opora_execution_pr_closure.write_back`). Schéma tabulky se nemění: `repository`
= "local", `number` = 0, `head_sha` = `merge_sha` = commit, `head_ref` = větev.
"""
import re

from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_pr_closure import write_back
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.opora_execution_validation import validate
from backend.integrations.gitio import git
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests

FIELDS = {"commit"}
CREDENTIALS = {"token", "epoch"}
COMMIT = re.compile(r"[0-9a-f]{7,64}")
LOCAL = "local"


class InvalidCommit(ValueError):
    """Commit není platný nebo v repozitáři projektu neexistuje (HTTP 422)."""


class CommitOffBranch(ValueError):
    """Commit existuje, ale není předkem HEAD cílové větve projektu (HTTP 409)."""


def repository_path(service, project):
    """Složka repozitáře projektu: zdroj lokální složky, jinak klon projektu; vestavěný návrh žádný nemá."""
    if project == "draft":
        raise ValueError("Vestavěný návrh nemá repozitář; lokální sloučení potřebuje projekt se složkou v Gitu.")
    row = service.row("projects", project)
    source = service.project_hub.source_info(row)
    path = source.get("sourcePath") or row.get("repo")
    if not path:
        raise ValueError("Projekt nemá složku s repozitářem.")
    return path


def verify_commit(path, commit):
    """`(plný commit, větev)`; 422 neexistující commit, 409 commit mimo HEAD cílové větve."""
    full = git(path, "rev-parse", "--verify", "--quiet", commit + "^{commit}", timeout=10, optional=True)
    if not full or not COMMIT.fullmatch(full):
        raise InvalidCommit("Commit v repozitáři projektu neexistuje.")
    branch = git(path, "rev-parse", "--abbrev-ref", "HEAD", timeout=10, optional=True) or "HEAD"
    if git(path, "merge-base", "--is-ancestor", full, "HEAD", timeout=10, optional=True) is None:
        raise CommitOffBranch(f"Commit není ve větvi {branch} projektu (není předkem HEAD); nejdřív ho slučte.")
    return full, branch


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise InvalidCommit("Tělo musí být objekt {project, workspace, commit}.")
    keys = FIELDS | (CREDENTIALS if CREDENTIALS & set(payload) else set())
    commit = payload.get("commit")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise InvalidCommit("commit musí být 7–64 malých hex znaků.")
    return validate(payload, keys)


class LocalMerge:
    def __init__(self, service, links=None):
        self.service = service
        self.links = links or ExecutionPullRequestLinks(service)

    def merge(self, execution_id, payload, actor):
        from backend.canvas.authority import acts_as_human
        from backend.canvas.opora_card_done import local_mode

        project, workspace = validate_payload(payload)
        if not local_mode(self.service, project):
            raise ValueError("Projekt má vazbu na GitHub; sloučení se hlásí přes PR (brána review/external).")
        full, branch = verify_commit(repository_path(self.service, project), payload["commit"])
        executions = self.links.executions
        with self.links.transaction(project, workspace) as repo:
            links = ExecutionPullRequests(repo.db, project, workspace)
            record = repo.read(execution_id)
            if "token" in payload:
                executions.authenticate(record, payload["token"], payload["epoch"])
            if actor == "agent":
                try:
                    self.links.authorize(repo, record)
                except ValueError:
                    if not acts_as_human(actor):  # cizí nebo propadlý běh smí ohlásit jen s plnou autonomií
                        raise
            row = links.read(execution_id)
            if row is not None and row["source"] != LOCAL:
                raise ValueError("Execution already has a linked pull request; a local merge cannot replace it.")
            if row is None or row["merge_sha"] != full:
                now = stamp()
                if row is None:
                    row = links.insert({
                        "execution_id": execution_id, "node_id": record["nodeId"],
                        "accepted_revision": record["acceptedRevision"], "repository": LOCAL, "number": 0,
                        "head_ref": branch, "head_sha": full, "state": "merged", "binding_id": None,
                        "enrollment": "unavailable", "enrollment_error": None, "enrollment_retry_at": None,
                        "enrollment_failures": 0, "merge_sha": None, "merged_at": None, "awaiting_human_close": 0,
                        "attention": None, "source": LOCAL, "linked_by": actor, "created_at": now, "updated_at": now})
                else:  # jiný commit nahradí starší lokální vazbu
                    row = links.update(execution_id, head_ref=branch, linked_by=actor, updated_at=now)
                content = {"executionId": execution_id, "cardId": record["nodeId"],
                           "acceptedRevision": record["acceptedRevision"], "source": LOCAL, "commit": full,
                           "branch": branch, "actor": actor, "createdAt": now}
                write_back(repo.db, project, workspace, row, f"execution.merged:{execution_id}:{full}", content,
                           full, now, full)
        return self.links.read(project, workspace, execution_id)
