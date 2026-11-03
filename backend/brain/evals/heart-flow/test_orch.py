"""Čisté pomocníky scénářů O (orch.py): podobnost titulků, součet usage ze stream-json, příkazy srdce."""
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[1] / "opora-vs-bare" / "multi"),
                str(Path(__file__).resolve().parents[1] / "opora-vs-bare")]
import orch  # noqa: E402


def test_jaccard_and_near_duplicates():
    assert orch.jaccard("Přidání a smazání úkolů", "přidání a smazání úkolů") == 1.0
    assert orch.jaccard("", "x") == 0.0
    pairs = orch.near_duplicates(["MVP: přidání a smazání úkolů", "MVP přidání smazání úkolů", "Filtr úkolů"])
    assert [(a, b) for a, b, _ in pairs] == [(0, 1)]


def test_stream_usage_dedupes_message_ids():
    msg = {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 10, "cache_read_input_tokens": 100,
                                                                    "output_tokens": 5}}}
    other = {"type": "assistant", "message": {"id": "m2", "usage": {"input_tokens": 1, "output_tokens": 1}}}
    got = orch.stream_usage([json.dumps(msg), json.dumps(msg), json.dumps(other), "nejson"])
    assert got["messages"] == 2 and got["input_tokens"] == 11 and got["peakContextTokens"] == 110
    assert round(orch.usage_cost({"input_tokens": 1_000_000}), 2) == 3.0


def test_heart_commands_counts_plan_and_task():
    batch = {"transcript": {"bash": ["python opora_heart.py plan --file dilna/out/a.json --dry-run",
                                     "python opora_heart.py plan --file dilna/out/a.json",
                                     "python opora_heart.py task --title T --do D", "python opora_heart.py plan --help", "python opora_heart.py done --summary S"]}}
    assert orch.heart_commands(batch) == {"planReal": 1, "planDry": 1, "task": 1, "answer": 0, "escalate": 0}


def test_listing_and_first():
    assert orch.listing({"executions": [1]}, "items", "executions") == [1]
    assert orch.listing([2], "x") == [2] and orch.listing(None, "x") == []
    assert orch.first({"a": "", "b": 3}, "a", "b") == 3
