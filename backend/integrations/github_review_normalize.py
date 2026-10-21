"""Validate GitHub JSON before reducing it to immutable evidence fields."""
import re
from datetime import datetime

from backend.integrations.github_review_transport import GitHubReadError

REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_-][A-Za-z0-9._-]*")
SHA = re.compile(r"[a-f0-9]{40}")
LOGIN = re.compile(r"[A-Za-z0-9-]+(?:\[bot\])?")


def require(condition):
    if not condition:
        raise GitHubReadError("GitHub returned malformed or inconsistent observation data.")


def obj(value):
    require(isinstance(value, dict))
    return value


def positive(value):
    require(type(value) is int and value > 0)
    return value


def text(value, *, limit=65536, empty=False):
    require(isinstance(value, str) and len(value) <= limit and "\0" not in value and (empty or bool(value)))
    return value


def sha(value):
    require(isinstance(value, str) and SHA.fullmatch(value))
    return value


def choice(value, values):
    require(isinstance(value, str) and value in values)
    return value


def body(value):
    return text("" if value is None else value, empty=True)


def repository(value, expected):
    value = obj(value)
    full_name = text(value.get("full_name"), limit=200)
    require(full_name.casefold() == expected.casefold())
    return {"id": positive(value.get("id")), "fullName": full_name}


def pull(value, repo, number):
    value = obj(value)
    base, head, user = (obj(value.get(key)) for key in ("base", "head", "user"))
    require(repository(base.get("repo"), repo["fullName"]) == repo)
    require(type(value.get("number")) is int and value["number"] == number)
    require(type(value.get("draft")) is bool)
    return {"id": positive(value.get("id")), "number": number,
            "authorId": positive(user.get("id")), "baseRef": text(base.get("ref"), limit=255),
            "baseSha": sha(base.get("sha")), "headSha": sha(head.get("sha")),
            "headRepoId": positive(obj(head.get("repo")).get("id")),
            "state": choice(value.get("state"), {"open", "closed"}), "draft": value["draft"],
            "body": body(value.get("body"))}


def review(value):
    value = obj(value)
    user = obj(value.get("user"))
    login = text(user.get("login"), limit=100)
    require(LOGIN.fullmatch(login))
    state = choice(value.get("state"), {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"})
    submitted = value.get("submitted_at")
    commit = value.get("commit_id")
    if state != "PENDING":
        text(submitted, limit=50)
        try:
            require(datetime.fromisoformat(submitted).tzinfo is not None)
        except ValueError:
            raise GitHubReadError("GitHub returned an invalid review timestamp.") from None
        sha(commit)
    else:
        require(submitted is None)
        if commit is not None:
            sha(commit)
    return {"id": positive(value.get("id")), "userId": positive(user.get("id")), "login": login,
            "userType": choice(user.get("type"), {"User", "Bot", "Organization", "Mannequin"}),
            "state": state, "commitId": commit, "submittedAt": submitted,
            "body": body(value.get("body"))}


def check(value, expected_sha):
    value = obj(value)
    require(sha(value.get("head_sha")) == expected_sha)
    status = choice(value.get("status"), {"queued", "in_progress", "completed", "waiting", "requested", "pending"})
    conclusion = value.get("conclusion")
    if conclusion is not None:
        choice(conclusion, {"success", "failure", "neutral", "cancelled", "skipped", "timed_out",
                            "action_required", "stale", "startup_failure"})
    require(status != "completed" or conclusion is not None)
    return {"id": positive(value.get("id")), "appId": positive(obj(value.get("app")).get("id")),
            "name": text(value.get("name"), limit=1024), "headSha": expected_sha,
            "status": status, "conclusion": conclusion}


def status(value, expected_sha):
    value = obj(value)
    # List-statuses is fetched by full SHA; GitHub's individual status has no sha field.
    if "sha" in value:
        require(sha(value["sha"]) == expected_sha)
    return {"id": positive(value.get("id")), "context": text(value.get("context"), limit=1024),
            "sha": expected_sha, "state": choice(value.get("state"), {"success", "pending", "failure", "error"})}
