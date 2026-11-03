"""Kanál doručení: projekt bez exekuce karty je `gate`, s exekucí kdekoli v projektu `cards`; snímek srdce ho už neukazuje (práce = ticket)."""
import sqlite3

import pytest

from backend.brain_opora.determinism import delivery, gate, snapshot
from backend.canvas.canvas_service import CanvasService
from database.repositories.opora_executions import Executions
from database.schema.opora_execution_schema import SCHEMA
from database.schema.project_schema import GATE_SCHEMA


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA + GATE_SCHEMA)
    yield connection
    connection.close()


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def _claim(db, project, workspace, node="n1"):
    Executions(db, project, workspace).insert({"executionId": "ex_" + node, "nodeId": node, "state": "running"},
                                              "agent:office", "claim-" + node, "d" * 64)


def test_fresh_project_is_gate(db):
    assert delivery.channel(db, "p1") == {"channel": "gate", "executions": 0, "workers": 0}


def test_any_card_execution_in_the_project_makes_it_cards(db):
    _claim(db, "p1", "ws_other")  # claim v jiném prostoru projektu se počítá, cizí projekt ne
    _claim(db, "p2", "main", "n2")
    assert delivery.channel(db, "p1")["channel"] == "cards"
    assert delivery.channel(db, "p3")["channel"] == "gate"


def test_unreadable_tables_fall_back_to_gate():
    assert delivery.channel(sqlite3.connect(":memory:"), "p1")["channel"] == "gate"


def test_line_names_the_command_for_each_channel():
    assert delivery.line({"channel": "gate", "executions": 0, "workers": 0}) == (
        "DORUČENÍ: gate – žádný orchestrátor karet; práci zadávej jako úkoly fronty (task)")
    assert "(relací pracovníků brány 2)" in delivery.line({"channel": "gate", "executions": 0, "workers": 2})
    assert delivery.line({"channel": "cards", "executions": 3, "workers": 0}) == (
        "DORUČENÍ: cards – orchestrátor bere karty (exekucí 3); práci zadávej kartami (plan)")


def test_snapshot_no_longer_splits_work_by_channel(service):
    # Srdce vydává práci jen jako ticket (docs/navrhy/2026-11-03-novy-zaklad.md §3.3); kanál do snímku nejde.
    gate.open_session(service, {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}})
    with service.lock_for("draft"):
        connection = service.db_for("draft")
        with connection:
            _claim(connection, "draft", "draft")
    assert "DORUČENÍ" not in snapshot.snapshot(service, "draft", "draft")
