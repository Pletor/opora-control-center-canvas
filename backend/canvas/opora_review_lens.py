"""PR Lens review evidence (`evidence.review.lens`, docs/oporahub-review-jobs.md, "Diagram PR Lens").

The worker that makes a change draws it with PR Lens locally (docs/cista-linie.md §4): a validated
graph document, the spec (lanes, cards with files and lines, edges, flow steps with payloads). The
spec is the source of truth agents read as data; pictures are optional. The worker posts it during
its run with its execution lease (`POST /api/oporahub/review-jobs/lens`), either as an **area map**
before code exists (`kind: area`, keyed to the execution's accepted plan revision, `headSha` null) or
for the current head of its open linked PR (`kind: pr`). It is optional and NEVER blocking: the merge
gate only shows it and adds no reason. Agents read it through `GET /api/oporahub/review-lens`.
Validation is pure; invalid evidence is refused, never repaired."""
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
PR_FIELDS = {"kind", "prNumber", "headSha", "validatedAt", "url", "specUrl", "specSha256", "specBytes", "spec"}
AREA_FIELDS = {"kind", "validatedAt", "spec"}
MAX_URL, MAX_SPEC_BYTES, MAX_INLINE_SPEC = 2000, 512 * 1024, 64 * 1024
AREA = "area"  # the storage slot of an execution's pre-code map (a PR lens uses its head SHA)


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


def _spec(spec):
    if not isinstance(spec, dict) or spec.get("kind") != "graph" or len(canonical(spec).encode()) > MAX_INLINE_SPEC:
        raise ValueError(f"lens.spec must be a PR Lens graph document of at most {MAX_INLINE_SPEC} bytes.")
    return spec


def validate_lens(value):
    """PR lens `{kind?: pr, prNumber, headSha, validatedAt, spec?, url?, specUrl?, specSha256?, specBytes?}`
    (spec or url required) or area map `{kind: area, validatedAt, spec}` → normalized with `kind`."""
    kind = value.get("kind", "pr") if isinstance(value, dict) else None
    if kind == AREA:
        if set(value) != AREA_FIELDS:
            raise ValueError("An area lens needs exactly kind, validatedAt and spec.")
        return {"kind": AREA, "headSha": None, "validatedAt": _stamp(value["validatedAt"]), "spec": _spec(value["spec"])}
    if kind != "pr" or not {"prNumber", "headSha", "validatedAt"} <= set(value) or set(value) - PR_FIELDS \
            or not {"spec", "url"} & set(value):
        raise ValueError("Invalid lens fields.")
    number = value["prNumber"]
    if type(number) is not int or not 0 < number < 10**9:
        raise ValueError("Invalid lens prNumber.")
    if not isinstance(value["headSha"], str) or SHA.fullmatch(value["headSha"]) is None:
        raise ValueError("lens.headSha must be a full lowercase commit SHA.")
    result = {"kind": "pr", "prNumber": number, "headSha": value["headSha"], "validatedAt": _stamp(value["validatedAt"])}
    for name in ("url", "specUrl"):
        if name in value:
            result[name] = _url(value[name], name)
    if "specSha256" in value:
        if not isinstance(value["specSha256"], str) or SHA256.fullmatch(value["specSha256"]) is None:
            raise ValueError("Invalid lens specSha256.")
        result["specSha256"] = value["specSha256"]
    if "specBytes" in value:
        if type(value["specBytes"]) is not int or not 0 < value["specBytes"] <= MAX_SPEC_BYTES:
            raise ValueError("Invalid lens specBytes.")
        result["specBytes"] = value["specBytes"]
    if "spec" in value:
        result["spec"] = _spec(value["spec"])
    return result


def _rows(db, where, parameters):
    rows = db.execute("SELECT execution_id,kind,head_sha,accepted_revision,record,by,created_at FROM opora_review_lens "
                      f"WHERE {where} ORDER BY created_at, rowid", parameters).fetchall()
    return [{"executionId": row[0], "kind": row[1], "headSha": row[2], "acceptedRevision": row[3],
             "lens": json.loads(row[4]), "by": row[5], "createdAt": row[6]} for row in rows]


def records(db, project, workspace, execution_id):
    """Stored lens evidence of one execution, oldest first."""
    return _rows(db, "project_id=? AND workspace_id=? AND execution_id=?", (project, workspace, execution_id))


def for_link(db, project, workspace, link):
    """The gate's read: the PR lens for the PR's current head, or None. Optional, never a gate reason."""
    found = [item["lens"] for item in records(db, project, workspace, link["execution_id"])
             if item["kind"] == "pr" and item["headSha"] == link["head_sha"]]
    return found[-1] if found else None


def for_node(db, project, workspace, node_id):
    """`GET /review-lens`: the card's newest PR lens (with its PR and whether it is for the current head)
    and its newest area map. Either may be null; for people the PR lens replaces the area map."""
    items = _rows(db, "project_id=? AND workspace_id=? AND node_id=?", (project, workspace, node_id))
    area = next((item for item in reversed(items) if item["kind"] == AREA), None)
    result = {"nodeId": node_id, "lens": None,
              "area": area and {key: area[key] for key in ("executionId", "acceptedRevision", "by", "createdAt", "lens")}}
    pr = next((item for item in reversed(items) if item["kind"] == "pr"), None)
    link = pr and ExecutionPullRequests(db, project, workspace).read(pr["executionId"])
    if not pr or link is None:
        return result
    return result | {"executionId": pr["executionId"], "repository": link["repository"], "number": link["number"],
                     "prState": link["state"], "current": pr["headSha"] == link["head_sha"], "by": pr["by"],
                     "createdAt": pr["createdAt"], "lens": pr["lens"]}


class LensAddenda:
    """`POST /lens`: lens evidence from the running execution itself (its lease token and epoch, the
    same credential and checks as `stepResults`); a PR lens only for the current head of its open PR."""

    def __init__(self, jobs):
        self.executions = jobs.executions

    def submit(self, payload, by):
        project, workspace = validate(payload, {"executionId", "token", "epoch", "lens"})
        execution_id = payload["executionId"]
        if not isinstance(execution_id, str) or EXECUTION.fullmatch(execution_id) is None:
            raise ValueError("Invalid executionId.")
        value = validate_lens(payload["lens"])
        with self.executions.transaction(project, workspace) as repo:
            record = repo.read(execution_id)
            self.executions.authenticate(record, payload["token"], payload["epoch"])
            self.executions.active(repo, record)  # running, valid lease, within budget
            if value["kind"] == "pr":
                link = ExecutionPullRequests(repo.db, project, workspace).read(execution_id)
                if link is None or link["state"] != "open":
                    raise ValueError("The execution has no open linked pull request.")
                if link["head_sha"] != value["headSha"] or link["number"] != value["prNumber"]:
                    raise ValueError("Lens evidence must be for the current head of the linked pull request.")
            row = (project, workspace, execution_id, value["headSha"] or AREA, record["nodeId"], value["kind"],
                   value["headSha"], record["acceptedRevision"], canonical(value), by, stamp())
            if value["kind"] == AREA:  # a plan map may be redrawn while the run lasts
                repo.db.execute("INSERT OR REPLACE INTO opora_review_lens VALUES(?,?,?,?,?,?,?,?,?,?,?)", row)
                return {"executionId": execution_id, "kind": AREA, "headSha": None, "recorded": True}
            inserted = repo.db.execute("INSERT OR IGNORE INTO opora_review_lens VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                       row).rowcount == 1
            if not inserted:
                existing = next(item for item in records(repo.db, project, workspace, execution_id)
                                if item["headSha"] == value["headSha"])
                if existing["lens"] != value:
                    raise ValueError("Lens evidence for this head was already recorded with different content.")
            return {"executionId": execution_id, "kind": "pr", "headSha": value["headSha"], "recorded": inserted}
