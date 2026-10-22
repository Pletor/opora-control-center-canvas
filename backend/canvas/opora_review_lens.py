"""PR Lens review evidence (`evidence.review.lens`, docs/oporahub-review-jobs.md, "Diagram PR Lens").

The worker that made a change draws it with PR Lens locally (docs/cista-linie.md §4): a validated
graph document (the spec: lanes, cards with files and lines, edges, flow steps with payloads) and a
rendered SVG for people. Agent Office publishes both next to the pull request and posts where they
are (`POST /api/oporahub/review-jobs/lens`). It is optional and NEVER blocking: the merge gate only
shows it and adds no reason, so its rule order is untouched. Agents read the spec through
`GET /api/oporahub/review-lens`. Validation is pure; invalid evidence is refused, never repaired."""
import json
import re
from datetime import datetime
from urllib.parse import urlsplit

from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_hub_store import canonical
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests

SHA, SHA256 = re.compile(r"[0-9a-f]{40}"), re.compile(r"[0-9a-f]{64}")
EXECUTION = re.compile(r"[A-Za-z0-9_-]{1,80}")
HOSTS = ("github.com", "raw.githubusercontent.com")
REQUIRED, OPTIONAL = {"url", "prNumber", "headSha", "validatedAt"}, {"specUrl", "specSha256", "specBytes", "spec"}
MAX_URL, MAX_SPEC_BYTES, MAX_INLINE_SPEC = 2000, 512 * 1024, 64 * 1024


def _url(value, name):
    """https only, on github.com (blob/raw links and user-attachments) or raw.githubusercontent.com."""
    if not isinstance(value, str) or not 0 < len(value) <= MAX_URL or re.search(r"[\s\x00-\x1f\\]", value):
        raise ValueError(f"Invalid lens {name}.")
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.netloc not in HOSTS or parts.username or parts.port or not parts.path.strip("/"):
        raise ValueError(f"lens.{name} must be an https link on github.com or raw.githubusercontent.com.")
    return value


def _stamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("Invalid lens validatedAt.")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("lens.validatedAt must be an ISO 8601 time.") from None
    return value


def validate_lens(value):
    """`{url, prNumber, headSha, validatedAt, specUrl?, specSha256?, specBytes?, spec?}` → normalized."""
    if not isinstance(value, dict) or not REQUIRED <= set(value) or set(value) - REQUIRED - OPTIONAL:
        raise ValueError("Invalid lens fields.")
    number = value["prNumber"]
    if type(number) is not int or not 0 < number < 10**9:
        raise ValueError("Invalid lens prNumber.")
    if not isinstance(value["headSha"], str) or SHA.fullmatch(value["headSha"]) is None:
        raise ValueError("lens.headSha must be a full lowercase commit SHA.")
    result = {"url": _url(value["url"], "url"), "prNumber": number, "headSha": value["headSha"],
              "validatedAt": _stamp(value["validatedAt"])}
    if "specUrl" in value:
        result["specUrl"] = _url(value["specUrl"], "specUrl")
    if "specSha256" in value:
        if not isinstance(value["specSha256"], str) or SHA256.fullmatch(value["specSha256"]) is None:
            raise ValueError("Invalid lens specSha256.")
        result["specSha256"] = value["specSha256"]
    if "specBytes" in value:
        if type(value["specBytes"]) is not int or not 0 < value["specBytes"] <= MAX_SPEC_BYTES:
            raise ValueError("Invalid lens specBytes.")
        result["specBytes"] = value["specBytes"]
    if "spec" in value:
        spec = value["spec"]
        if not isinstance(spec, dict) or spec.get("kind") != "graph" or len(canonical(spec).encode()) > MAX_INLINE_SPEC:
            raise ValueError(f"lens.spec must be a PR Lens graph document of at most {MAX_INLINE_SPEC} bytes.")
        result["spec"] = spec
    return result


def records(db, project, workspace, execution_id):
    """Stored lens evidence of one execution, oldest first."""
    rows = db.execute("SELECT head_sha,record,by,created_at FROM opora_review_lens WHERE project_id=? AND workspace_id=? "
                      "AND execution_id=? ORDER BY created_at, rowid", (project, workspace, execution_id)).fetchall()
    return [{"headSha": row[0], "lens": json.loads(row[1]), "by": row[2], "createdAt": row[3]} for row in rows]


def for_link(db, project, workspace, link):
    """The gate's read: the lens for the PR's current head, or None. Optional, never a gate reason."""
    found = [item["lens"] for item in records(db, project, workspace, link["execution_id"]) if item["headSha"] == link["head_sha"]]
    return found[-1] if found else None


def for_node(db, project, workspace, node_id):
    """`GET /review-lens`: the newest lens of any execution of the card, and whether it is for that PR's current head."""
    best = None
    for link in ExecutionPullRequests(db, project, workspace).listing():
        if link["node_id"] != node_id:
            continue
        for item in records(db, project, workspace, link["execution_id"]):
            if best is None or item["createdAt"] >= best[1]["createdAt"]:
                best = (link, item)
    if best is None:
        return {"nodeId": node_id, "lens": None}
    link, item = best
    return {"nodeId": node_id, "executionId": link["execution_id"], "repository": link["repository"], "number": link["number"],
            "prState": link["state"], "current": item["headSha"] == link["head_sha"], "by": item["by"],
            "createdAt": item["createdAt"], "lens": item["lens"]}


class LensAddenda:
    """`POST /lens`: lens evidence for the current head of a linked, open PR (agent or human identity)."""

    def __init__(self, jobs):
        self.jobs = jobs

    def submit(self, payload, by):
        project, workspace = validate(payload, {"executionId", "lens"})
        execution_id = payload["executionId"]
        if not isinstance(execution_id, str) or EXECUTION.fullmatch(execution_id) is None:
            raise ValueError("Invalid executionId.")
        value = validate_lens(payload["lens"])
        with self.jobs.transaction(project, workspace) as store:
            link = ExecutionPullRequests(store.db, project, workspace).read(execution_id)
            if link is None or link["state"] != "open":
                raise ValueError("The execution has no open linked pull request.")
            if link["head_sha"] != value["headSha"] or link["number"] != value["prNumber"]:
                raise ValueError("Lens evidence must be for the current head of the linked pull request.")
            inserted = store.db.execute("INSERT OR IGNORE INTO opora_review_lens VALUES(?,?,?,?,?,?,?)",
                                        (project, workspace, execution_id, value["headSha"], canonical(value), by,
                                         stamp())).rowcount == 1
            if not inserted:
                existing = next(item for item in records(store.db, project, workspace, execution_id)
                                if item["headSha"] == value["headSha"])
                if existing["lens"] != value:
                    raise ValueError("Lens evidence for this head was already recorded with different content.")
            return {"executionId": execution_id, "headSha": value["headSha"], "recorded": inserted}
