"""Spouštěče karet nad skutečným plánem srdce (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): fakta z přijatého
plánu a přijetí srdcem není ruční změna. Přesunuto z `determinism/test_triggers.py` (determinismus nesmí importovat
`heart`, `test_layer_boundaries.py`)."""
from backend.api.brain_opora.test_heart_plan import (  # noqa: F401 - fixture skutečné aplikace
    heart,
    plan,
)
from backend.brain_opora.determinism import triggers
from backend.brain_opora.heart import opora_heart


def test_facts_read_a_real_accepted_plan_and_the_heart_acceptance_is_not_a_human_change(heart):  # noqa: F811
    """Skutečná aplikace: plán srdce přijatý tokenem srdce → první karta `ready` s profilem, druhá blokovaná;
    přijetí srdcem (`by.kind == agent`) spouštěč ruční změny nebudí."""
    client, _, tmp_path = heart
    done = plan(tmp_path, opora_heart.PLAN_EXAMPLE)
    service = client.app.state.service
    with service.reading("draft"):
        assert triggers.spaces(service.db_for("draft"), "draft") == ["draft"]
    cards, finished = triggers.facts(service, "draft", "draft", 0)
    by_id = {item["nodeId"]: item for item in cards}
    model = by_id[done["refs"]["model"]]
    assert model["status"] == "ready" and model["label"] in ("XS", "S", "M", "L", "XL", "?")
    assert model["failures"] == 0 and model["runId"] is None and finished == []
    assert triggers.wakes(service, "draft", None, "t", 0) == []
    db = service.db_for("draft")
    head = db.execute("SELECT accepted_id FROM opora_spec_refs WHERE project_id='draft'").fetchone()[0]
    with db:
        assert triggers.human_change(db, "draft", "draft", head, "t") is None


def test_idle_reads_the_real_agent_state_and_a_ready_card_is_not_an_empty_frontier(heart):  # noqa: F811
    """Skutečná aplikace (OPORA-002): fakta prázdné fronty jdou z dokumentu agent-state; přijatý plán s kartou
    `ready` frontu prázdnou nemá, takže `idle_wakes` nebudí a důvod je None."""
    from backend.brain_opora.determinism import idle
    from backend.brain_opora.heart.inputs import idle_wakes

    client, _, tmp_path = heart
    plan(tmp_path, opora_heart.PLAN_EXAMPLE)
    service = client.app.state.service
    state, questions, since = idle.facts(service, "draft", "draft")
    assert state["heads"]["acceptedHead"] and questions == 0 and since is not None
    assert idle.reason(state, questions) is None
    assert idle_wakes(service, "draft", "t", 10 ** 10) == ([], {"draft": None})
