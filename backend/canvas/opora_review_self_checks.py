"""Pre-PR self-check evidence of the agent for the current PR head (docs/oporahub-review-jobs.md).

The evidence is agent-reported, never independently verified: it proves the agent ran the
configured checks (tests, build, lint …) on exactly this head before asking for review. It comes
from the linked execution result (`result.selfChecks`) or, after the head moved (review fixes,
rebase), from a per-head addendum (`POST /api/oporahub/review-jobs/self-checks`). Validation is
pure and deterministic; invalid evidence never counts."""
import re

from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_validation import validate
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_executions import Executions
from database.repositories.opora_review_gate_facts import ReviewGateFacts

SHA = re.compile(r"[0-9a-f]{40}")
NAME = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}")
STATUSES = ("passed", "failed", "skipped")
REQUIRED, OPTIONAL = ("name", "command", "exitCode", "status"), ("summary", "output", "durationSeconds")
MAX_CHECKS, MAX_COMMAND, MAX_SUMMARY, MAX_OUTPUT = 30, 1000, 500, 4000


def _text(value, limit, name, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError(f"Invalid self-check field {name}.")
    return value


def check(value):
    if not isinstance(value, dict) or not set(REQUIRED) <= set(value) or set(value) - set(REQUIRED) - set(OPTIONAL):
        raise ValueError("Invalid self-check fields.")
    if not isinstance(value["name"], str) or NAME.fullmatch(value["name"]) is None:
        raise ValueError("Invalid self-check name.")
    status, code = value["status"], value["exitCode"]
    if status not in STATUSES:
        raise ValueError("Self-check status must be passed, failed or skipped.")
    if status == "skipped" and code is not None:
        raise ValueError("A skipped self-check has exitCode null.")
    if status != "skipped" and (type(code) is not int or not -1024 <= code <= 1024 or (code == 0) != (status == "passed")):
        raise ValueError("Self-check status must match its exit code (passed exactly when 0).")
    duration = value.get("durationSeconds")
    if duration is not None and (type(duration) not in (int, float) or not 0 <= duration <= 86400):
        raise ValueError("Invalid self-check duration.")
    return {"name": value["name"], "command": _text(value["command"], MAX_COMMAND, "command"), "exitCode": code,
            "status": status, "summary": _text(value.get("summary"), MAX_SUMMARY, "summary", False),
            "output": _text(value.get("output"), MAX_OUTPUT, "output", False), "durationSeconds": duration}


def validate_self_checks(value):
    """`{headSha, checks: [{name, command, exitCode, status, summary?, output?, durationSeconds?}]}` → normalized."""
    if not isinstance(value, dict) or set(value) != {"headSha", "checks"}:
        raise ValueError("selfChecks needs exactly headSha and checks.")
    if not isinstance(value["headSha"], str) or SHA.fullmatch(value["headSha"]) is None:
        raise ValueError("selfChecks.headSha must be a full lowercase commit SHA.")
    items = value["checks"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_CHECKS:
        raise ValueError(f"selfChecks.checks needs 1 to {MAX_CHECKS} checks.")
    checks = [check(item) for item in items]
    if len({item["name"] for item in checks}) != len(checks):
        raise ValueError("Duplicate self-check name.")
    return {"headSha": value["headSha"], "checks": checks}


def evaluate(candidates, head, required):
    """`candidates` = [(source, raw selfChecks)] oldest first. The newest valid one for `head` decides.

    Returns `{status: off|ok|missing|failed, source, missing[], failed[], invalid}`."""
    if not required:
        return {"status": "off", "source": None, "missing": [], "failed": [], "invalid": 0}
    chosen, invalid = None, 0
    for source, raw in candidates:
        try:
            value = validate_self_checks(raw)
        except ValueError:
            invalid += 1
            continue
        if value["headSha"] == head:
            chosen = (source, value)
    if chosen is None:
        return {"status": "missing", "source": None, "missing": list(required), "failed": [], "invalid": invalid}
    by_name = {item["name"]: item for item in chosen[1]["checks"]}
    missing = [name for name in required if name not in by_name]
    failed = [name for name in required if name in by_name and by_name[name]["status"] != "passed"]
    status = "failed" if failed else "missing" if missing else "ok"
    return {"status": status, "source": chosen[0], "missing": missing, "failed": failed, "invalid": invalid}


def candidates(db, project, workspace, execution_id):
    """Self-check evidence of the linked execution: result receipts first, then per-head addenda."""
    found = []
    try:
        receipts = Executions(db, project, workspace).receipts(execution_id)
    except ValueError:
        receipts = []
    for receipt in receipts:
        result = receipt.get("result") if isinstance(receipt, dict) else None
        if isinstance(result, dict) and "selfChecks" in result:
            found.append(("result", result["selfChecks"]))
    found += [("addendum", item["selfChecks"]) for item in ReviewGateFacts(db, project, workspace).self_checks(execution_id)]
    return found


def status(db, project, workspace, link, config):
    required = config["selfChecks"]["required"]
    if not required:
        return evaluate([], link["head_sha"], required)
    return evaluate(candidates(db, project, workspace, link["execution_id"]), link["head_sha"], required)


class SelfCheckAddenda:
    """`POST /self-checks`: evidence for a later head of a linked, open PR (agent or human identity)."""

    def __init__(self, jobs):
        self.jobs = jobs

    def submit(self, payload, by):
        config = self.jobs.enabled()
        project, workspace = validate(payload, {"executionId", "selfChecks"})
        execution_id = payload["executionId"]
        if not isinstance(execution_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", execution_id) is None:
            raise ValueError("Invalid executionId.")
        value = validate_self_checks(payload["selfChecks"])
        with self.jobs.transaction(project, workspace) as store:
            link = ExecutionPullRequests(store.db, project, workspace).read(execution_id)
            if link is None or link["state"] != "open":
                raise ValueError("The execution has no open linked pull request.")
            if link["head_sha"] != value["headSha"]:
                raise ValueError("Self-checks must be for the current head of the linked pull request.")
            facts = ReviewGateFacts(store.db, project, workspace)
            if not facts.insert_self_checks(execution_id, value["headSha"], value, by, stamp()):
                existing = next(item for item in facts.self_checks(execution_id) if item["headSha"] == value["headSha"])
                if existing["selfChecks"] != value:
                    raise ValueError("Self-checks for this head were already recorded with different content.")
            return {"executionId": execution_id, "headSha": value["headSha"],
                    "status": evaluate([("addendum", value)], value["headSha"],
                                       config["selfChecks"]["required"])}
