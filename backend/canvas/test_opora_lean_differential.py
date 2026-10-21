"""Differential test: real implementation functions vs the proved Lean models.

tools/formal/lean/vectors.json is produced by `lake exe vectors` from the same definitions the
theorems are about (CI regenerates it and fails on drift). Here the production code runs on the
identical inputs: opora_review_aggregation.candidates/tally, ChangesetRepository.advance on a
real project schema, and opora_field_merge.merge_fields. Any mismatch is a model/implementation
divergence. Coverage guards keep the vectors from being vacuous.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from backend.canvas.opora_field_merge import merge_fields
from backend.canvas.opora_review_aggregation import candidates, tally
from database.repositories.opora_changesets import ChangesetRepository
from database.schema.project_schema import PROJECT_SCHEMA

VECTORS = json.loads((Path(__file__).resolve().parents[2] / "tools/formal/lean/vectors.json").read_text("utf-8"))


def fingerprint(n):
    return f"fp{n:04d}"  # zero padding: string order == Nat order of the model


def revision(n):
    return None if n is None else f"{n:040x}"


def test_vectors_are_not_vacuous():
    assert VECTORS["schemaVersion"] == 1
    assert sum(bool(case["posted"]) for case in VECTORS["votes"]) >= 10
    assert sum(not case["posted"] for case in VECTORS["votes"]) >= 10
    assert sum(bool(case["conflicts"]) for case in VECTORS["merge"]) >= 10
    assert sum(not all(case["oks"]) for case in VECTORS["cas"]) >= 10
    assert sum(len(case["proposed"]) < sum(map(len, case["submissions"])) for case in VECTORS["dedupe"]) >= 10


@pytest.mark.parametrize("case", VECTORS["votes"])
def test_tally_matches_model(case):
    items = [{"candidateId": f"c{c}", "kind": "finding", "fingerprint": fingerprint(c)} for c in case["candidates"]]
    ballots = [{"votes": [{"candidateId": f"c{c}", "verdict": verdict} for c, verdict in ballot]}
               for ballot in case["ballots"]]
    result = tally(items, ballots, case["required"])
    assert [int(item["candidateId"][1:]) for item in result if item["accepted"]] == case["posted"]


@pytest.mark.parametrize("case", VECTORS["dedupe"])
def test_candidates_dedupe_matches_model(case):
    submissions = [(slot, {"findings": [{"fingerprint": fingerprint(n), "severity": "nit", "path": "a.py", "line": 1,
                                         "title": "t", "rationale": "r"} for n in fps], "fixed": []})
                   for slot, fps in enumerate(case["submissions"], start=1)]
    result = candidates("job", submissions, {fingerprint(n) for n in case["known"]})
    assert [item["fingerprint"] for item in result] == [fingerprint(n) for n in case["proposed"]]
    again = candidates("job", submissions, {fingerprint(n) for n in case["known"] + case["proposed"]})
    assert again == []  # no_repost


@pytest.mark.parametrize("case", VECTORS["cas"])
def test_accepted_head_cas_matches_model(case):
    db = sqlite3.connect(":memory:")
    db.executescript(PROJECT_SCHEMA)
    repo, oks, log = ChangesetRepository(db, "p", "w"), [], []
    for expected, rev in case["ops"]:
        with db:
            db.execute("BEGIN IMMEDIATE")
            try:
                repo.advance(revision(expected), revision(rev))
            except ValueError:
                oks.append(False)
                continue
            oks.append(True)
            log.insert(0, [rev, expected])  # acceptance inserts parentRevision=expected in the same transaction
    assert oks == case["oks"]
    assert repo.head() == revision(case["head"])
    assert log == case["log"]


@pytest.mark.parametrize("case", VECTORS["merge"])
def test_field_merge_matches_model(case):
    def record(values):
        return {f"f{field}": value for field, value in zip(case["fields"], values, strict=True) if value is not None}

    result = merge_fields(record(case["base"]), record(case["ours"]), record(case["theirs"]))
    assert result["conflicts"] == [f"f{field}" for field in case["conflicts"]]
    assert result["merged"] == {f"f{field}": value for field, value in case["merged"] if value is not None}
    swapped = merge_fields(record(case["base"]), record(case["theirs"]), record(case["ours"]))
    assert swapped == result  # merged_comm / conflicts_comm
