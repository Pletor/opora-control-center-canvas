"""PR Lens evidence: shape validation, per-head storage, the card read, and a gate that never blocks on it."""
import pytest

from backend.canvas import opora_review_lens as review_lens
from backend.canvas.opora_review_lens import LensAddenda, validate_lens
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import config, gate_item, run_round, use
from backend.canvas.test_opora_review_jobs import push
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

URL = f"https://github.com/owner/repo/raw/{'e' * 40}/.pr-lens/overview-light-0123.svg"
SPEC = {"kind": "graph", "title": "Batch sends", "nodes": [{"id": "n", "files": [{"path": "src/a.ts", "startLine": 1, "endLine": 9}]}]}


def lens(head=SHA, number=7, **extra):
    return {"url": URL, "prNumber": number, "headSha": head, "validatedAt": "2026-10-22T11:50:00.000Z", **extra}


def test_valid_lens_is_normalized_with_its_optional_spec():
    value = validate_lens(lens(specUrl=URL.replace("overview-light-0123.svg", "spec.json"), specSha256="a" * 64,
                               specBytes=900, spec=SPEC))
    assert value["spec"] == SPEC and value["specBytes"] == 900
    assert validate_lens(lens()) == lens()
    for url in ("https://github.com/user-attachments/assets/0f1e", "https://raw.githubusercontent.com/o/r/abc/x.svg"):
        assert validate_lens(lens(url=url))["url"] == url


@pytest.mark.parametrize("value", [
    None, {}, lens(extra=1), {k: v for k, v in lens().items() if k != "url"},
    lens(url="http://github.com/o/r/x.svg"), lens(url="https://evil.example/x.svg"),
    lens(url="https://github.com.evil.example/x.svg"), lens(url="https://user@github.com/o/r/x.svg"),
    lens(url="https://github.com:8443/o/r/x.svg"), lens(url="https://github.com/"), lens(url="https://github.com/o r"),
    lens(url="javascript:alert(1)"), lens(head="C" * 40), lens(number=0), lens(number=True),
    lens(validatedAt="yesterday"), lens(specSha256="xyz"), lens(specBytes=0), lens(specBytes=600 * 1024),
    lens(spec={"kind": "patch"}), lens(spec={"kind": "graph", "pad": "x" * 70_000}), lens(specUrl="ftp://github.com/x"),
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
    payload = {**review["scope"], "executionId": review["record"]["executionId"]}
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**payload, "lens": lens(NEXT_SHA)}, "agent:w")
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**payload, "lens": lens(number=8)}, "agent:w")
    receipt = addenda.submit({**payload, "lens": lens(spec=SPEC)}, "agent:w")
    assert receipt == {"executionId": review["record"]["executionId"], "headSha": SHA, "recorded": True}
    assert addenda.submit({**payload, "lens": lens(spec=SPEC)}, "agent:w")["recorded"] is False  # idempotent
    with pytest.raises(ValueError, match="different content"):
        addenda.submit({**payload, "lens": lens(url=URL + "?v=2")}, "agent:w")
    item = gate_item(review)
    assert item["evidence"]["review"]["lens"] == lens(spec=SPEC)
    # Optional and non-blocking: the gate's status and reasons are exactly what they were without it.
    assert item["reviewGate"] == before["reviewGate"] and item["mergeReadiness"] == before["mergeReadiness"]
    db = review["service"].db_for(review["scope"]["project"])
    read = review_lens.for_node(db, review["scope"]["project"], review["scope"]["workspace"], "card")
    assert (read["current"], read["number"], read["lens"]["spec"]) == (True, 7, SPEC)
    assert review_lens.for_node(db, review["scope"]["project"], review["scope"]["workspace"], "other") == \
        {"nodeId": "other", "lens": None}
    # A new head: the gate shows no lens for it, the card read still finds the old one, marked not current.
    push(review, NEXT_SHA, "push")
    assert "evidence" not in gate_item(review)
    assert review_lens.for_node(db, review["scope"]["project"], review["scope"]["workspace"], "card")["current"] is False


def test_lens_needs_an_open_linked_pull_request(review):  # noqa: F811
    addenda = LensAddenda(review["jobs"])
    with pytest.raises(ValueError, match="no open linked"):
        addenda.submit({**review["scope"], "executionId": "missing", "lens": lens()}, "agent:w")
    with pytest.raises(ValueError):
        addenda.submit({**review["scope"], "executionId": "bad id!", "lens": lens()}, "agent:w")
