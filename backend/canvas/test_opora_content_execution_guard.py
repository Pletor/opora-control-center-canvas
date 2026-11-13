"""Pojistka content_manifest: enforce drží kartu s neschváleným obsahem bez zápisu při čtení stavu, warn ji pustí a zapíše do deníku."""
import pytest

from backend.app import error_log, errors, guards
from backend.canvas.test_opora_content_changes import accepted, change, propose
from backend.canvas.test_opora_execution_context import claimed, prepared
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414


@pytest.fixture
def unreviewed(sparse):
    _, authority, refs = sparse
    errors.configure(authority.canvas.root)
    guards.configure(authority.canvas.root)
    accepted(sparse, propose(sparse, [change("text", refs["a"], "text", "A accepted")]))
    canvas = authority.canvas
    with canvas.db_for("draft"):  # živý text karty bez návrhu a přijetí
        canvas.texts.save_in_transaction(("draft", "draft", refs["a"]), 1, "A edited without review")
    yield sparse
    error_log.drain()
    guards.configure(None)
    errors.configure(None)


def journal():
    error_log.drain()
    return [r for r in errors.read() if r["kind"] == "blocked"]


def test_enforce_blocks_claim_without_journal_noise(unreviewed):
    _, authority, refs = unreviewed
    context = authority.context("draft", "draft", refs["a"])
    assert not context["available"] and "accepted manifest" in context["unavailableReason"]
    assert journal() == []  # výpočet stavu nezapisuje; odmítnutý claim zapíše factory.refused


def test_warn_lets_claim_through_and_records_it(unreviewed):
    guards.set_mode("content_manifest", "draft", "warn", ("human", None), "nová karta z plánu")
    execution = claimed(unreviewed, context=prepared(unreviewed))
    assert execution["executionId"]
    rows = journal()
    assert rows and all(r["message"].startswith("pojistka content_manifest ve warn") for r in rows)
