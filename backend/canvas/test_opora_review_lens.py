"""PR Lens evidence: shape validation, per-head storage, the card read, and a gate that never blocks on it."""
import pytest

from backend.canvas import opora_review_lens as review_lens
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_review_lens import LensAddenda, validate_lens
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import config, gate_item, run_round, use
from backend.canvas.test_opora_review_jobs import push
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests

URL = f"https://github.com/owner/repo/raw/{'e' * 40}/.pr-lens/overview-light-0123.svg"
SPEC = {"kind": "graph", "title": "Batch sends", "nodes": [{"id": "n", "files": [{"path": "src/a.ts", "startLine": 1, "endLine": 9}]}]}


def lens(head=SHA, number=7, **extra):
    return {"url": URL, "prNumber": number, "headSha": head, "validatedAt": "2026-10-22T11:50:00.000Z", **extra}


def credential(review):  # noqa: F811
    record = review["record"]
    return {**review["scope"], "executionId": record["executionId"], "token": record["token"], "epoch": record["epoch"]}


def test_valid_lens_is_normalized_with_its_optional_spec():
    value = validate_lens(lens(specUrl=URL.replace("overview-light-0123.svg", "spec.json"), specSha256="a" * 64,
                               specBytes=900, spec=SPEC))
    assert value["spec"] == SPEC and value["specBytes"] == 900 and value["kind"] == "pr"
    assert validate_lens(lens()) == {"kind": "pr", **lens()}
    spec_only = {k: v for k, v in lens(spec=SPEC).items() if k != "url"}
    assert validate_lens(spec_only) == {"kind": "pr", **spec_only}  # url is optional, the spec is the main path
    for url in ("https://github.com/user-attachments/assets/0f1e", "https://raw.githubusercontent.com/o/r/abc/x.svg"):
        assert validate_lens(lens(url=url))["url"] == url
    area = {"kind": "area", "validatedAt": "2026-10-22T11:50:00Z", "spec": SPEC}
    assert validate_lens(area) == {**area, "headSha": None}


@pytest.mark.parametrize("value", [
    None, {}, lens(extra=1), {k: v for k, v in lens().items() if k != "url"}, lens(kind="other"),
    lens(url="http://github.com/o/r/x.svg"), lens(url="https://evil.example/x.svg"),
    lens(url="https://github.com.evil.example/x.svg"), lens(url="https://user@github.com/o/r/x.svg"),
    lens(url="https://github.com:8443/o/r/x.svg"), lens(url="https://github.com/"), lens(url="https://github.com/o r"),
    lens(url="javascript:alert(1)"), lens(head="C" * 40), lens(number=0), lens(number=True),
    lens(validatedAt="yesterday"), lens(specSha256="xyz"), lens(specBytes=0), lens(specBytes=600 * 1024),
    lens(spec={"kind": "patch"}), lens(spec={"kind": "graph", "pad": "x" * 70_000}), lens(specUrl="ftp://github.com/x"),
    {"kind": "area", "validatedAt": "2026-10-22T11:50:00Z"}, {"kind": "area", "validatedAt": "x", "spec": SPEC},
    {"kind": "area", "validatedAt": "2026-10-22T11:50:00Z", "spec": SPEC, "headSha": SHA},
])
def test_invalid_lens_is_rejected(value):
    with pytest.raises(ValueError):
        validate_lens(value)


def test_lens_is_stored_per_head_read_by_card_and_never_blocks_the_gate(review):  # noqa: F811
    use(review, config())
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    before = gate_item(review)
    assert "evidence" not in before
    addenda = LensAddenda(review["jobs"])
    payload = credential(review)
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**payload, "lens": lens(NEXT_SHA)}, "agent:w")
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**payload, "lens": lens(number=8)}, "agent:w")
    receipt = addenda.submit({**payload, "lens": lens(spec=SPEC)}, "agent:w")
    assert receipt == {"executionId": review["record"]["executionId"], "kind": "pr", "headSha": SHA, "recorded": True}
    assert addenda.submit({**payload, "lens": lens(spec=SPEC)}, "agent:w")["recorded"] is False  # idempotent
    with pytest.raises(ValueError, match="different content"):
        addenda.submit({**payload, "lens": lens(url=URL + "?v=2")}, "agent:w")
    item = gate_item(review)
    assert item["evidence"]["review"]["lens"] == {"kind": "pr", **lens(spec=SPEC)}
    # Optional and non-blocking: the gate's status and reasons are exactly what they were without it.
    assert item["reviewGate"] == before["reviewGate"] and item["mergeReadiness"] == before["mergeReadiness"]
    db = review["service"].db_for(review["scope"]["project"])
    read = review_lens.for_node(db, review["scope"]["project"], review["scope"]["workspace"], "card")
    assert (read["current"], read["number"], read["lens"]["spec"], read["area"]) == (True, 7, SPEC, None)
    assert review_lens.for_node(db, review["scope"]["project"], review["scope"]["workspace"], "other") ==         {"nodeId": "other", "lens": None, "area": None}
    # A new head: the gate shows no lens for it, the card read still finds the old one, marked not current.
    push(review, NEXT_SHA, "push")
    assert "evidence" not in gate_item(review)
    assert review_lens.for_node(db, review["scope"]["project"], review["scope"]["workspace"], "card")["current"] is False


def test_area_map_is_keyed_to_the_plan_revision_and_may_be_redrawn(review):  # noqa: F811
    addenda = LensAddenda(review["jobs"])
    area = {"kind": "area", "validatedAt": "2026-10-22T11:50:00Z", "spec": SPEC}
    assert addenda.submit({**credential(review), "lens": area}, "agent:w")["headSha"] is None
    redrawn = {**area, "spec": {**SPEC, "title": "Batch sends, v2"}}
    assert addenda.submit({**credential(review), "lens": redrawn}, "agent:w")["recorded"] is True
    db = review["service"].db_for(review["scope"]["project"])
    read = review_lens.for_node(db, review["scope"]["project"], review["scope"]["workspace"], "card")
    assert read["lens"] is None and read["area"]["lens"]["spec"]["title"] == "Batch sends, v2"
    assert read["area"]["acceptedRevision"] == review["record"]["acceptedRevision"]
    assert "evidence" not in gate_item(review)  # an area map is never PR evidence


def test_lens_needs_the_running_lease_and_an_open_linked_pull_request(review):  # noqa: F811
    addenda = LensAddenda(review["jobs"])
    with pytest.raises(ValueError, match="does not exist"):
        addenda.submit({**credential(review), "executionId": "missing", "lens": lens()}, "agent:w")
    with pytest.raises(ValueError):
        addenda.submit({**credential(review), "executionId": "bad id!", "lens": lens()}, "agent:w")
    with pytest.raises(ValueError):  # identity alone is not enough: the lease token is required
        addenda.submit({**review["scope"], "executionId": review["record"]["executionId"], "lens": lens()}, "agent:w")
    with pytest.raises(ValueError, match="credential"):
        addenda.submit({**credential(review), "token": "0" * 64, "lens": lens()}, "agent:w")
    with pytest.raises(ValueError, match="credential"):
        addenda.submit({**credential(review), "epoch": review["record"]["epoch"] + 1, "lens": lens()}, "agent:w")
    review["links"].executions.release(review["record"]["executionId"], {
        **review["scope"], "token": review["record"]["token"], "epoch": review["record"]["epoch"]})
    with pytest.raises(ValueError, match="no longer authoritative"):
        addenda.submit({**credential(review), "lens": lens()}, "agent:w")


def test_pr_lens_after_the_reported_result_needs_the_runs_credential_open_pr_and_same_head(review):  # noqa: F811
    """N1 (Opora #61): the office opens the PR after the result, so a reported run may still post its PR lens."""
    record, scope = review["record"], review["scope"]
    ExecutionResults(review["service"]).submit(record["executionId"], {
        **scope, "token": record["token"], "epoch": record["epoch"], "requestId": "result",
        "result": {"summary": "Done"}})
    addenda = LensAddenda(review["jobs"])
    with pytest.raises(ValueError, match="credential"):
        addenda.submit({**credential(review), "token": "0" * 64, "lens": lens()}, "agent:w")
    with pytest.raises(ValueError, match="credential"):
        addenda.submit({**credential(review), "epoch": record["epoch"] + 1, "lens": lens()}, "agent:w")
    area = {"kind": "area", "validatedAt": "2026-10-22T11:50:00Z", "spec": SPEC}
    with pytest.raises(ValueError, match="only a PR lens"):
        addenda.submit({**credential(review), "lens": area}, "agent:w")
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**credential(review), "lens": lens(NEXT_SHA)}, "agent:w")
    receipt = addenda.submit({**credential(review), "lens": lens(spec=SPEC)}, "agent:w")
    assert receipt == {"executionId": record["executionId"], "kind": "pr", "headSha": SHA, "recorded": True}
    db = review["service"].db_for(scope["project"])
    assert review_lens.for_node(db, scope["project"], scope["workspace"], "card")["lens"]["spec"] == SPEC
    with review["jobs"].executions.transaction(scope["project"], scope["workspace"]) as repo:
        ExecutionPullRequests(repo.db, *repo.scope).update(record["executionId"], state="closed")
    with pytest.raises(ValueError, match="no open linked pull request"):
        addenda.submit({**credential(review), "lens": lens(spec=SPEC)}, "agent:w")
