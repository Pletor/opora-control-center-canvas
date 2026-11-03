"""Eval gate Brainu: kandidát, zmrazená sada evals/, běh `claude plugin eval` (podvržený) a uložený eval_run."""
import json
import re
import sqlite3
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.brain import evaluate, registry, seed
from backend.flow.node_types import NODE_TYPES
from database.schema.project_schema import REGISTRY_SCHEMA

HEART = "opora:brain:skill:heart"


class FakeEval:
    """Podvržený `claude plugin eval`: skóre z `SKORE=x` ve SKILL.md exportu, JSON do `--json`."""

    def __init__(self, cost=0.1, partial=False, write=True):
        self.cost, self.partial, self.write, self.calls = cost, partial, write, []

    def __call__(self, args, cwd, seconds):
        plugin = Path(args[3])
        self.calls.append({"args": args, "evals": sorted(p.relative_to(plugin / "evals").as_posix()
                                                         for p in (plugin / "evals").rglob("*") if p.is_file())})
        match = re.search(r"SKORE=([0-9.]+)", (plugin / "skills" / "heart" / "SKILL.md").read_text(encoding="utf-8"))
        if self.write:
            Path(args[args.index("--json") + 1]).write_text(json.dumps({
                "costUsd": self.cost, "partial": self.partial,
                "aggregates": {"overallScore": float(match.group(1)) if match else 0.5},
                "cases": [{"name": "ticket-s-kriteriem", "aggregates": {"score": 1}, "promptMarkdown": "dlouhé"}]}),
                encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "chyba evalu")


@pytest.fixture
def brain(tmp_path, monkeypatch):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    seed.ensure(db, tmp_path, ponytail_cache=tmp_path / "chybi")
    monkeypatch.setattr(evaluate, "claude_path", lambda: "claude")
    monkeypatch.delenv("OPORA_BRAIN_EVAL_MAX_USD", raising=False)
    return SimpleNamespace(db=db, root=tmp_path, registry_lock=threading.RLock())


def candidate(brain, text="Nový prompt SKORE=0.8"):
    return evaluate.add_candidate(brain.db, brain.root, HEART, {"skills/heart/SKILL.md": text}, "zkouška")


def test_candidate_commits_and_points_to_active_baseline(brain):
    active = brain.db.execute("SELECT id FROM brain_artifact_versions WHERE status='active' AND artifact_id=?",
                              (HEART,)).fetchone()["id"]
    version = candidate(brain)
    assert version["status"] == "candidate" and version["baseline_version_id"] == active
    assert version["content_ref"] == "skills/heart/SKILL.md" and len(version["version"]) == 40


def test_candidate_cannot_touch_evals_or_be_empty(brain):
    with pytest.raises(evaluate.Refused) as frozen:
        evaluate.add_candidate(brain.db, brain.root, HEART, {"evals/x/prompt.md": "lehčí"}, "podvod")
    assert (frozen.value.status, frozen.value.code) == (422, "evals_frozen")
    for files, code in (({}, "files_invalid"), ({"../venku.md": "x"}, "files_invalid")):
        with pytest.raises(evaluate.Refused) as refused:
            evaluate.add_candidate(brain.db, brain.root, HEART, files, "")
        assert refused.value.code == code
    with pytest.raises(evaluate.Refused) as missing:
        evaluate.add_candidate(brain.db, brain.root, "opora:brain:skill:nic", {"a.md": "x"}, "")
    assert missing.value.status == 404


def test_eval_runs_both_on_the_frozen_suite_and_stores_the_run(brain, monkeypatch):
    monkeypatch.setenv("OPORA_BRAIN_EVAL_MAX_USD", "0.5")
    version = candidate(brain)
    fake = FakeEval(cost=0.2)
    run = evaluate.evaluate(brain, version["id"], runner=fake)
    assert run["status"] == "ok" and run["score"] == 0.8 and run["baseline_score"] == 0.5 and run["passed"]
    assert run["cost_usd"] == pytest.approx(0.4) and run["baseline_version_id"] == version["baseline_version_id"]
    assert run["report"]["candidate"]["cases"] == [{"name": "ticket-s-kriteriem", "aggregates": {"score": 1}}]
    first, second = fake.calls
    assert first["args"][:3] == ["claude", "plugin", "eval"] and "--trust-plugin" in first["args"]
    assert first["args"][first["args"].index("--ablation") + 1] == "with-without"
    assert first["args"][first["args"].index("--max-cost-usd") + 1] == "0.50"
    assert second["args"][second["args"].index("--max-cost-usd") + 1] == "0.30"  # zbytek stropu
    assert first["evals"] == second["evals"] and "ticket-s-kriteriem/prompt.md" in first["evals"]
    links = registry.get_artifact(brain.db, HEART)["versions"][0]["links"]
    assert [(item["target_kind"], item["target_ref"]) for item in links] == [("eval_run", run["id"])]
    assert registry.version(brain.db, version["id"])["status"] == "candidate"
    assert brain.db.execute("SELECT eval_score FROM brain_artifact_versions WHERE id=?",
                            (version["id"],)).fetchone()[0] == 0.8


def test_eval_failure_and_cost_ceiling_do_not_pass(brain, monkeypatch):
    version = candidate(brain, "Horší SKORE=0.9")
    partial = evaluate.evaluate(brain, version["id"], runner=FakeEval(partial=True))
    assert partial["status"] == "error" and not partial["passed"] and "strop" in partial["report"]["error"]
    broken = evaluate.evaluate(brain, version["id"], runner=FakeEval(write=False))
    assert broken["status"] == "error" and "kódem 0" in broken["report"]["error"]
    monkeypatch.setattr(evaluate, "claude_path", lambda: None)
    missing = evaluate.evaluate(brain, version["id"], runner=FakeEval())
    assert "claude není" in missing["report"]["error"] and evaluate.latest(brain.db, version["id"]) == missing


def test_only_candidates_with_baseline_are_evaluated(brain):
    active = registry.active(brain.db, HEART)
    vid = brain.db.execute("SELECT id FROM brain_artifact_versions WHERE version=? AND artifact_id=?",
                           (active["version"], HEART)).fetchone()["id"]
    with pytest.raises(evaluate.Refused) as refused:
        evaluate.start(brain.db, vid)
    assert refused.value.code == "not_candidate"
    with pytest.raises(evaluate.Refused) as missing:
        evaluate.start(brain.db, "nic")
    assert missing.value.status == 404


def test_brain_eval_node_is_detached_and_reports_the_gate(brain, monkeypatch):
    spec = NODE_TYPES["brain_eval"]
    assert spec.detached and spec.port("main", "in").schema["required"] == ["versionId"]
    version = candidate(brain)
    monkeypatch.setattr(evaluate, "_run", FakeEval())
    ctx = {"node": {"params": {}}, "input": {"versionId": version["id"]}}
    port, output, extra = evaluate.work(ctx, SimpleNamespace(service=brain))
    assert (port, output) == ("main", {"score": 0.8, "baselineScore": 0.5, "passed": True})
    assert extra == {"cost_usd": pytest.approx(0.2)}
