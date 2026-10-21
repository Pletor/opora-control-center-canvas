"""Shared helpers for the merge gate rule tests (security, self-checks, merge queue, template)."""
from backend.canvas import opora_agent_state_reviews as reviews
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_review_gate import review_gates
from backend.canvas.opora_review_risk import parse
from backend.canvas.test_opora_review_gate import observe as observe_reviews
from database.repositories.opora_review_evidence import ReviewEvidenceRepository

BASE_TIP, OLD_BASE = "1" * 40, "2" * 40
JOBS = {"finders": 2, "voters": 2, "required_votes": 2, "max_rounds": 3}


def config(**sections):
    return parse({"enabled": True, "jobs": JOBS, "risk": {"sensitive": [".github/workflows/**"]}, **sections})


class BaseReader:
    """Fake GET-only compare reader: fresh by default, `behind` makes the head stale."""

    def __init__(self, behind=0, sections=("testing", "risk", "revert plan")):
        self.calls, self.behind, self.sections, self.complete = [], behind, list(sections), True

    def base(self, repository, number, head):
        self.calls.append((repository, number, head))
        if not self.complete:
            return {"complete": False, "error": "github-unavailable"}
        return {"complete": True, "baseRef": "main", "baseSha": BASE_TIP,
                "mergeBaseSha": BASE_TIP if self.behind == 0 else OLD_BASE, "behindBy": self.behind, "aheadBy": 1,
                "sections": list(self.sections)}


def use(review, value, reader=None):
    review["jobs"]._config = value
    review["jobs"].base_reader = reader or BaseReader()
    return review


def gate_item(review):
    """The single gate at the review clock (observations carry the same clock)."""
    scope = review["scope"]
    db = review["service"].db_for(scope["project"])
    [item] = review_gates(db, scope["project"], scope["workspace"], review["jobs"].config(), review["clock"].now)
    return item


def take_any(review, role, owner="agent:w"):
    payload = {**review["scope"], "requestId": f"t{int(review['clock'].now)}", "ttlSeconds": 60, "role": role}
    review["clock"].now += 1
    return review["tasks"].claim(payload, owner)["task"]


def submit(review, task, submission):
    return review["tasks"].submit(task["reviewJobId"], task["taskId"], {
        **review["scope"], "token": task["token"], "epoch": task["epoch"], "requestId": "s",
        "submission": submission})


def run_round(review, finders, voters=None):
    """Finish every open slot of both kinds. `finders`/`voters` map job kind → submission / {key: verdict}."""
    while (task := take_any(review, "finder")) is not None:
        submit(review, task, finders.get(task["job"]["kind"], {"findings": []}))
    while (task := take_any(review, "voter")) is not None:
        ballot = (voters or {}).get(task["job"]["kind"], {})
        submit(review, task, {"votes": [{"candidateId": item["candidateId"],
                                         "verdict": ballot.get(item.get("fingerprint") or item["findingId"], "reject")}
                                        for item in task["candidates"]]})


def evidence(review, head, checks=(), minute=0):
    """A complete GitHub snapshot of `head` with the given (name, conclusion) check runs and no reviews."""
    observe_reviews(review, head, [], minute)
    scope = review["scope"]
    db = review["service"].db_for(scope["project"])
    [latest] = ReviewEvidenceRepository(db, scope["project"], scope["workspace"]).list(1)
    data = {key: value for key, value in latest.items() if key != "id"}
    data["checks"] = [{"id": index + 1, "appId": 8, "name": name, "headSha": head, "status": "completed",
                       "conclusion": conclusion} for index, (name, conclusion) in enumerate(checks)]
    data["observedAt"] = f"2026-10-20T14:{minute:02d}:00Z"
    data["pr"] = {**data["pr"], "headSha": head}
    with db:
        db.execute("BEGIN IMMEDIATE")
        ReviewEvidenceRepository(db, scope["project"], scope["workspace"]).insert(data)


def agent_state(review):
    reviews.register(review["jobs"].config())
    try:
        return AgentState(review["service"], clock=review["clock"]).read(**review["scope"])
    finally:
        reviews.register(None)

