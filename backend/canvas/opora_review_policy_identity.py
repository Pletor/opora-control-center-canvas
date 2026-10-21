"""Policy repository identity comes only from a complete scoped server observation."""
from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_review_policy_validation import github_id, text, timestamp


def pinned_repository(snapshot, current):
    try:
        if snapshot.get("complete") is not True or type(snapshot.get("schemaVersion")) is not int or snapshot["schemaVersion"] not in (1, 2):
            raise ValueError("Policy configuration requires complete server evidence.")
        repository, pr = snapshot["repository"], snapshot["pr"]
        identity = github_id(repository["id"])
        name = text(repository["fullName"], 255).casefold()
        branch = text(pr["baseRef"], 255)
        for key in ("id", "number", "authorId", "headRepoId"):
            github_id(pr[key])
        for key in ("headSha", "baseSha"):
            identifier(pr[key])
        identifier(snapshot["acceptedRevision"])
        github_id(snapshot["prNumber"])
        timestamp(snapshot["observedAt"])
        if (type(pr["draft"]) is not bool or pr["state"] not in ("open", "closed")
                or snapshot["prNumber"] != pr["number"]
                or any(not isinstance(snapshot.get(key), list) or len(snapshot[key]) > 1000 for key in ("reviews", "checks", "statuses"))):
            raise ValueError("Invalid complete identity observation.")
        if (name != current["repository"] or branch != current["config"]["branch"]
                or snapshot["configuredRepository"].casefold() != name or snapshot["configuredBaseBranch"] != branch):
            raise ValueError("Identity evidence does not match the current repository and branch.")
        return {"id": identity, "fullName": name, "baseBranch": branch}
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid server repository identity evidence.") from error
