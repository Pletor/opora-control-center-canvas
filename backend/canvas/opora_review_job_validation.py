"""Strict bounded review worker messages (docs/oporahub-review-jobs.md, "Kontrakt pracovníka").

Workers are model processes; their output is data, never instructions. Every field is typed
and bounded, unknown keys are rejected, so aggregation stays deterministic."""
import re

from backend.canvas.opora_execution_validation import validate

SEVERITIES = ("important", "nit", "pre_existing")
ROLES = ("finder", "voter")
VERDICTS = ("confirm", "reject")
FINGERPRINT = re.compile(r"[A-Za-z0-9_.:/#@-]{8,160}")
MAX_FINDINGS, MAX_FIXED, MAX_TEXT, MAX_TITLE = 50, 100, 4000, 200


def _text(value, limit, name, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError(f"Invalid review field {name}.")
    return value


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise ValueError("Invalid review submission fields.")


def claim_scope(payload):
    """`{project, workspace, requestId, ttlSeconds, role?}` → (project, workspace, role)."""
    extra = {"requestId", "ttlSeconds"} | ({"role"} if isinstance(payload, dict) and "role" in payload else set())
    project, workspace = validate(payload, extra)
    role = payload.get("role")
    if role is not None and role not in ROLES:
        raise ValueError("role must be finder, voter or null.")
    return project, workspace, role


def finding(value):
    _keys(value, ("path", "severity", "fingerprint", "title", "rationale"), ("line",))
    line = value.get("line")
    if line is not None and (type(line) is not int or not 1 <= line <= 10_000_000):
        raise ValueError("Invalid review finding line.")
    if value["severity"] not in SEVERITIES:
        raise ValueError("severity must be important, nit or pre_existing.")
    if not isinstance(value["fingerprint"], str) or FINGERPRINT.fullmatch(value["fingerprint"]) is None:
        raise ValueError("Invalid review finding fingerprint.")
    path = _text(value["path"], 500, "path")
    if path.startswith("/") or ".." in path.split("/"):
        raise ValueError("Finding path must be repository-relative.")
    return {"path": path, "line": line, "severity": value["severity"], "fingerprint": value["fingerprint"],
            "title": _text(value["title"], MAX_TITLE, "title"), "rationale": _text(value["rationale"], MAX_TEXT, "rationale")}


def finder_submission(value, open_findings):
    """`{findings: [...], fixed: [{findingId, rationale}]}`; fix claims only for this PR's open findings."""
    _keys(value, ("findings",), ("fixed",))
    items, fixed = value["findings"], value.get("fixed", [])
    if not isinstance(items, list) or len(items) > MAX_FINDINGS or not isinstance(fixed, list) or len(fixed) > MAX_FIXED:
        raise ValueError("Too many review findings.")
    findings = [finding(item) for item in items]
    if len({item["fingerprint"] for item in findings}) != len(findings):
        raise ValueError("Duplicate fingerprint in one submission.")
    claims = []
    for item in fixed:
        _keys(item, ("findingId", "rationale"))
        if not isinstance(item["findingId"], str) or item["findingId"] not in open_findings:
            raise ValueError("Fix claim must reference an open finding of this pull request.")
        claims.append({"findingId": item["findingId"], "rationale": _text(item["rationale"], MAX_TEXT, "rationale")})
    if len({item["findingId"] for item in claims}) != len(claims):
        raise ValueError("Duplicate fix claim in one submission.")
    return {"findings": findings, "fixed": claims}


def voter_submission(value, candidate_ids):
    """`{votes: [{candidateId, verdict, rationale?}]}` covering every candidate exactly once."""
    _keys(value, ("votes",))
    votes = value["votes"]
    if not isinstance(votes, list):
        raise ValueError("votes must be a list.")  # noqa: TRY004 - every invalid message is a 409
    result = []
    for item in votes:
        _keys(item, ("candidateId", "verdict"), ("rationale",))
        if not isinstance(item["candidateId"], str) or item["verdict"] not in VERDICTS:
            raise ValueError("Vote needs a candidateId and a confirm or reject verdict.")
        result.append({"candidateId": item["candidateId"], "verdict": item["verdict"],
                       "rationale": _text(item.get("rationale"), MAX_TEXT, "rationale", required=False)})
    if sorted(item["candidateId"] for item in result) != sorted(candidate_ids):
        raise ValueError("Votes must cover every candidate exactly once.")
    return {"votes": result}


def reason(payload, extra=()):
    project, workspace = validate(payload, {"reason", *extra})
    return project, workspace, _text(payload["reason"], 2000, "reason")
