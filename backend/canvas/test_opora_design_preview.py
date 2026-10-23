"""`evidence.preview`: lease + epocha, vazba na hlavu PR, strop 8 na hlavu, čtení karty, brána bez blokace, potvrzení."""
import pytest

from backend.canvas import opora_design_mode as design_mode
from backend.canvas import opora_design_preview as design_preview
from backend.canvas.opora_design_preview import PreviewAddenda
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_design_preview_validation import PNG, preview, shot
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import config, gate_item, run_round, use
from backend.canvas.test_opora_review_jobs import push
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401


def credential(review):  # noqa: F811
    record = review["record"]
    return {**review["scope"], "executionId": record["executionId"], "token": record["token"], "epoch": record["epoch"]}


def db_of(review):  # noqa: F811
    return review["service"].db_for(review["scope"]["project"])


def card(review, node="card"):  # noqa: F811
    return design_preview.for_node(db_of(review), review["scope"]["project"], review["scope"]["workspace"], node)


def test_preview_is_bound_to_the_current_head_and_never_blocks_the_gate(review):  # noqa: F811
    use(review, config())
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    before = gate_item(review)
    addenda = PreviewAddenda(review["jobs"])
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**credential(review), "preview": preview(headSha=NEXT_SHA)}, "agent:w")
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**credential(review), "preview": preview(prNumber=8)}, "agent:w")
    receipt = addenda.submit({**credential(review), "preview": preview()}, "agent:w")
    assert receipt == {"executionId": review["record"]["executionId"], "headSha": SHA, "mode": "brand",
                       "added": ["mobil světlý"], "screenshots": 1, "recorded": True}
    again = addenda.submit({**credential(review), "preview": preview()}, "agent:w")
    assert again["recorded"] is False and again["added"] == []  # idempotent
    with pytest.raises(ValueError, match="different content"):
        addenda.submit({**credential(review), "preview": preview(shot(data=PNG + b"x"))}, "agent:w")
    with pytest.raises(ValueError, match="different design mode or DESIGN.md"):
        addenda.submit({**credential(review), "preview": preview(designMdSha256="b" * 64)}, "agent:w")
    more = addenda.submit({**credential(review), "preview": preview(shot("desktop tmavý", PNG + b"d"))}, "agent:w")
    assert more["screenshots"] == 2 and more["added"] == ["desktop tmavý"]
    item = gate_item(review)
    assert item["evidence"]["preview"] == {"headSha": SHA, "mode": "brand", "designMdSha256": "a" * 64,
                                           "screenshots": 2, "labels": ["mobil světlý", "desktop tmavý"],
                                           "proposedDesignMd": False, "confirmed": None}
    # Evidence only: the gate's status and reasons are exactly what they were without it.
    assert item["reviewGate"] == before["reviewGate"] and item["mergeReadiness"] == before["mergeReadiness"]
    head = card(review)["heads"][0]
    assert (head["current"], head["prNumber"], head["by"], len(head["screenshots"])) == (True, 7, "agent:w", 2)
    assert head["screenshots"][0]["url"].startswith("/api/oporahub/review-preview/file?")
    scope = review["scope"]
    file_id = head["screenshots"][0]["fileId"]
    assert design_preview.png(db_of(review), scope["project"], scope["workspace"], "card", file_id) == PNG
    assert design_preview.png(db_of(review), scope["project"], scope["workspace"], "other", file_id) is None
    assert card(review, "other") == {"nodeId": "other", "heads": [], "design": design_mode.DEFAULT}
    push(review, NEXT_SHA, "push")  # a new head: the gate shows nothing for it, the card keeps the old one
    assert "preview" not in gate_item(review).get("evidence", {})
    assert card(review)["heads"][0]["current"] is False


def test_a_head_holds_at_most_eight_screenshots(review):  # noqa: F811
    addenda = PreviewAddenda(review["jobs"])
    shots = [shot(f"s{index}", PNG + bytes([index])) for index in range(8)]
    assert addenda.submit({**credential(review), "preview": preview(*shots)}, "agent:w")["screenshots"] == 8
    with pytest.raises(ValueError, match="at most 8"):
        addenda.submit({**credential(review), "preview": preview(shot("s9", PNG + b"9"))}, "agent:w")


def test_preview_needs_the_lease_or_a_reported_result(review):  # noqa: F811
    addenda = PreviewAddenda(review["jobs"])
    with pytest.raises(ValueError):  # identity alone is not enough
        addenda.submit({**review["scope"], "executionId": review["record"]["executionId"], "preview": preview()}, "a")
    with pytest.raises(ValueError, match="credential"):
        addenda.submit({**credential(review), "token": "0" * 64, "preview": preview()}, "agent:w")
    with pytest.raises(ValueError, match="credential"):
        addenda.submit({**credential(review), "epoch": review["record"]["epoch"] + 1, "preview": preview()}, "agent:w")
    with pytest.raises(ValueError):
        addenda.submit({**credential(review), "executionId": "bad id!", "preview": preview()}, "agent:w")
    review["links"].executions.release(review["record"]["executionId"], {
        **review["scope"], "token": review["record"]["token"], "epoch": review["record"]["epoch"]})
    with pytest.raises(ValueError, match="no longer authoritative"):
        addenda.submit({**credential(review), "preview": preview()}, "agent:w")


def test_a_reported_execution_with_an_open_pr_on_the_same_head_may_still_add_screenshots(review):  # noqa: F811
    record = review["record"]
    ExecutionResults(review["service"]).submit(record["executionId"], {
        **review["scope"], "token": record["token"], "epoch": record["epoch"], "requestId": "result",
        "result": {"summary": "Hotovo."}})
    receipt = PreviewAddenda(review["jobs"]).submit({**credential(review), "preview": preview()}, "agent:w")
    assert receipt["recorded"] is True


def test_explore_mode_is_recorded_with_its_proposed_design_md(review):  # noqa: F811
    design_mode.set_mode(review["service"], {**review["scope"], "nodeId": "card", "mode": "explore"}, "human")
    addenda = PreviewAddenda(review["jobs"])
    with pytest.raises(ValueError, match="must not draw from DESIGN.md"):
        addenda.submit({**credential(review), "preview": preview()}, "agent:w")
    explore = preview(designMdSha256=None, proposedDesignMd="# Nový směr\n")
    assert addenda.submit({**credential(review), "preview": explore}, "agent:w")["mode"] == "explore"
    head = card(review)["heads"][0]
    assert (head["mode"], head["designMdSha256"], head["proposedDesignMd"]) == ("explore", None, "# Nový směr\n")
    with pytest.raises(ValueError, match="different proposedDesignMd"):
        addenda.submit({**credential(review), "preview": {**explore, "proposedDesignMd": "# Jiný\n"}}, "agent:w")


def test_human_confirms_the_look_for_one_head(review):  # noqa: F811
    use(review, config())
    service, scope = review["service"], review["scope"]
    payload = {**scope, "nodeId": "card", "headSha": SHA}
    with pytest.raises(ValueError, match="No preview screenshots"):
        design_preview.confirm(service, payload, "human")
    PreviewAddenda(review["jobs"]).submit({**credential(review), "preview": preview()}, "agent:w")
    done = design_preview.confirm(service, payload, "human")
    assert done["recorded"] is True and done["confirmed"]["by"] == "human"
    assert design_preview.confirm(service, payload, "human")["recorded"] is False
    assert card(review)["heads"][0]["confirmed"] == done["confirmed"]
    review["jobs"].sync(**scope)
    assert gate_item(review)["evidence"]["preview"]["confirmed"] == done["confirmed"]
    with pytest.raises(ValueError):
        design_preview.confirm(service, {**payload, "headSha": "C" * 40}, "human")
