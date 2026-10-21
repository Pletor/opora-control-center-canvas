"""Review jobs on real SQLite: idempotent enqueue, leases, vote aggregation, dedupe, rounds and cap."""
import pytest

from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.opora_review_findings import HumanRequired, ReviewFindings
from backend.canvas.opora_review_job_tasks import ReviewTasks
from backend.canvas.opora_review_jobs import ReviewJobsDisabled, ReviewJobService
from backend.canvas.opora_review_risk import parse
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA, Reader, body, claim
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401

THIRD_SHA = "f" * 40
CONFIG = parse({"enabled": True, "jobs": {"finders": 3, "voters": 3, "required_votes": 2, "max_rounds": 3},
                "risk": {"sensitive": [".github/workflows/**"]}})


class ChangeReader:
    def __init__(self, files=(("src/app.py", 10, 2),)):
        self.calls, self.files = [], files

    def change(self, repository, number, head):
        self.calls.append((repository, number, head))
        return {"complete": True, "baseSha": "b" * 40,
                "files": [{"path": path, "additions": a, "deletions": d} for path, a, d in self.files]}


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture(name="review")
def review_fixture(world):  # noqa: F811
    service, scope, executions = world
    record = claim(executions, scope)
    links = ExecutionPullRequestLinks(service, Reader())
    links.link(record["executionId"], body(record), "agent")
    clock, reader = Clock(), ChangeReader()
    jobs = ReviewJobService(service, reader, config=CONFIG, clock=clock)
    return {"service": service, "scope": scope, "record": record, "links": links, "jobs": jobs, "clock": clock,
            "reader": reader, "tasks": ReviewTasks(jobs), "findings": ReviewFindings(jobs)}


def push(review, sha, request):
    review["links"].link(review["record"]["executionId"], body(review["record"], request, headSha=sha), "agent")


def take(review, role=None, owner="agent:w", request=None):
    payload = {**review["scope"], "requestId": request or f"c{int(review['clock'].now)}-{owner[-1]}", "ttlSeconds": 60}
    if role:
        payload["role"] = role
    review["clock"].now += 1
    return review["tasks"].claim(payload, owner)["task"]


def send(review, task, submission, request="s"):
    return review["tasks"].submit(task["reviewJobId"], task["taskId"], {
        **review["scope"], "token": task["token"], "epoch": task["epoch"], "requestId": request,
        "submission": submission})


def found(fingerprint, severity="important", path="src/app.py"):
    return {"path": path, "line": 3, "severity": severity, "fingerprint": fingerprint, "title": "Bug " + fingerprint,
            "rationale": "Because."}


def run_finders(review, *submissions):
    for submission in submissions:
        send(review, take(review, "finder"), submission)


def run_voters(review, verdicts):
    """`verdicts` = one {fingerprint-or-findingId: verdict} per voter."""
    for ballot in verdicts:
        task = take(review, "voter")
        votes = [{"candidateId": item["candidateId"],
                  "verdict": ballot.get(item.get("fingerprint") or item["findingId"], "reject")}
                 for item in task["candidates"]]
        send(review, task, {"votes": votes})


def test_enqueue_is_idempotent_per_head_and_carries_the_job_spec(review):
    jobs, scope = review["jobs"], review["scope"]
    [job_id] = jobs.sync(**scope)
    assert jobs.sync(**scope) == [] and len(review["reader"].calls) == 1
    [job] = jobs.list(**scope)["jobs"]
    assert {key: job[key] for key in ("reviewJobId", "executionId", "cardId", "repository", "number", "baseSha",
                                      "headSha", "round", "sinceSha", "riskTier", "finders", "requiredVotes")} == {
        "reviewJobId": job_id, "executionId": review["record"]["executionId"], "cardId": "card",
        "repository": "owner/repo", "number": 7, "baseSha": "b" * 40, "headSha": SHA, "round": 1, "sinceSha": None,
        "riskTier": "low", "finders": 3, "requiredVotes": 2}
    assert [task["role"] for task in job["tasks"]] == ["finder"] * 3 and job["phase"] == "find"
    disabled = ReviewJobService(review["service"], ChangeReader(), config={**CONFIG, "enabled": False})
    with pytest.raises(ReviewJobsDisabled):
        disabled.sync(**scope)


def test_lease_epoch_heartbeat_release_and_submit_replay(review):
    tasks, scope, clock = review["tasks"], review["scope"], review["clock"]
    first = take(review, "finder", request="one")
    assert first["epoch"] == 1 and first["slot"] == 1 and first["job"]["headSha"] == SHA
    assert tasks.claim({**scope, "requestId": "one", "ttlSeconds": 60, "role": "finder"}, "agent:w")["task"]["taskId"] == first["taskId"]
    credentials = {**scope, "token": first["token"], "epoch": first["epoch"]}
    assert tasks.heartbeat(first["reviewJobId"], first["taskId"], {**credentials, "ttlSeconds": 120})["expiresAt"] == clock.now + 120
    clock.now += 500  # Lease expired: the slot is claimable again with a higher epoch.
    again = take(review, "finder", owner="agent:x")
    assert again["taskId"] == first["taskId"] and again["epoch"] == 2
    with pytest.raises(ValueError, match="credential or epoch"):
        tasks.heartbeat(first["reviewJobId"], first["taskId"], {**credentials, "ttlSeconds": 60})
    receipt = send(review, again, {"findings": []}, "r1")
    assert receipt["state"] == "submitted" and send(review, again, {"findings": []}, "r1") == receipt
    with pytest.raises(ValueError, match="different content"):
        send(review, again, {"findings": [found("fp-00000001")]}, "r2")
    second = take(review, "finder")
    released = tasks.release(second["reviewJobId"], second["taskId"], {**scope, "token": second["token"],
                                                                         "epoch": second["epoch"]})
    assert released["state"] == "open"
    with pytest.raises(ValueError, match="severity must"):
        send(review, take(review, "finder"), {"findings": [{**found("fp-00000001"), "severity": "critical"}]})


def test_vote_aggregation_posts_only_confirmed_candidates(review):
    review["jobs"].sync(**review["scope"])
    run_finders(review, {"findings": [found("fp-aaaaaaaa"), found("fp-bbbbbbbb", "nit")]},
                {"findings": [found("fp-aaaaaaaa", "nit")]}, {"findings": [found("fp-cccccccc", "pre_existing")]})
    voter = take(review, "voter")
    assert [(item["fingerprint"], item["severity"], item["finders"]) for item in voter["candidates"]] == [
        ("fp-aaaaaaaa", "important", [1, 2]), ("fp-bbbbbbbb", "nit", [1]), ("fp-cccccccc", "pre_existing", [3])]
    with pytest.raises(ValueError, match="every candidate"):
        send(review, voter, {"votes": [{"candidateId": voter["candidates"][0]["candidateId"], "verdict": "confirm"}]})
    review["tasks"].release(voter["reviewJobId"], voter["taskId"], {**review["scope"], "token": voter["token"],
                                                                      "epoch": voter["epoch"]})
    run_voters(review, [{"fp-aaaaaaaa": "confirm", "fp-cccccccc": "confirm"},
                        {"fp-aaaaaaaa": "confirm", "fp-bbbbbbbb": "confirm", "fp-cccccccc": "confirm"},
                        {"fp-cccccccc": "confirm"}])
    listing = review["jobs"].list(**review["scope"])
    assert listing["jobs"][0]["phase"] == "completed"
    posted = {item["fingerprint"]: (item["severity"], item["status"], item["confirms"]) for item in listing["findings"]}
    assert posted == {"fp-aaaaaaaa": ("important", "open", 2), "fp-cccccccc": ("pre_existing", "open", 3)}


def test_incremental_rounds_dedupe_fingerprints_and_vote_fixes(review):
    jobs, scope = review["jobs"], review["scope"]
    jobs.sync(**scope)
    run_finders(review, *[{"findings": [found("fp-aaaaaaaa"), found("fp-nnnnnnnn", "nit")]}] * 3)
    run_voters(review, [{"fp-aaaaaaaa": "confirm", "fp-nnnnnnnn": "confirm"}] * 3)
    findings = {item["fingerprint"]: item for item in jobs.list(**scope)["findings"]}
    review["findings"].resolve(findings["fp-nnnnnnnn"]["findingId"], {**scope, "reason": "Style only."}, "agent")
    with pytest.raises(HumanRequired):
        review["findings"].resolve(findings["fp-aaaaaaaa"]["findingId"], {**scope, "reason": "No."}, "agent")
    push(review, NEXT_SHA, "push")
    jobs.sync(**scope)
    task = take(review, "finder")
    assert task["job"]["round"] == 2 and task["job"]["sinceSha"] == SHA and task["job"]["headSha"] == NEXT_SHA
    assert {item["fingerprint"]: item["status"] for item in task["knownFindings"]} == {
        "fp-aaaaaaaa": "open", "fp-nnnnnnnn": "resolved"}
    target = findings["fp-aaaaaaaa"]["findingId"]
    repeat = {"findings": [found("fp-aaaaaaaa"), found("fp-nnnnnnnn", "nit")], "fixed": [{"findingId": target,
                                                                                         "rationale": "Guarded."}]}
    send(review, task, repeat)
    run_finders(review, repeat, {"findings": []})
    voter = take(review, "voter")
    assert [(item["kind"], item.get("findingId")) for item in voter["candidates"]] == [("fix", target)]
    review["tasks"].release(voter["reviewJobId"], voter["taskId"], {**scope, "token": voter["token"], "epoch": voter["epoch"]})
    run_voters(review, [{target: "confirm"}] * 2 + [{}])
    after = {item["fingerprint"]: item for item in jobs.list(**scope)["findings"]}
    assert len(after) == 2 and after["fp-aaaaaaaa"]["status"] == "fixed"
    assert after["fp-aaaaaaaa"]["resolution"]["headSha"] == NEXT_SHA and after["fp-nnnnnnnn"]["status"] == "resolved"


def test_new_head_supersedes_unfinished_round_and_cap_needs_a_human(review):
    jobs, scope, tasks = review["jobs"], review["scope"], review["tasks"]
    jobs.config = lambda: {**CONFIG, "maxRounds": 2}
    jobs.sync(**scope)
    stale = take(review, "finder")
    push(review, NEXT_SHA, "push-1")
    jobs.sync(**scope)
    with pytest.raises(ValueError, match="no longer authoritative"):
        send(review, stale, {"findings": []})
    current = [job for job in jobs.list(**scope)["jobs"] if job["phase"] != "superseded"]
    assert [(job["headSha"], job["round"], job["sinceSha"]) for job in current] == [(NEXT_SHA, 1, None)]
    run_finders(review, *[{"findings": []}] * 3)
    push(review, THIRD_SHA, "push-2")
    jobs.sync(**scope)
    run_finders(review, *[{"findings": []}] * 3)
    rounds = sorted((job["round"], job["sinceSha"]) for job in jobs.list(**scope)["jobs"] if job["phase"] == "completed")
    assert rounds == [(1, None), (2, NEXT_SHA)]
    push(review, SHA, "push-3")
    assert jobs.sync(**scope) == []
    decision = {**scope, "repository": "owner/repo", "number": 7, "headSha": SHA, "reason": "Reviewed manually."}
    with pytest.raises(HumanRequired):
        review["findings"].decide(decision, "agent")
    with pytest.raises(ValueError, match="No linked pull request"):
        review["findings"].decide({**decision, "headSha": NEXT_SHA}, "human")
    assert review["findings"].decide(decision, "human")["decision"] == "accept_unreviewed_head"
