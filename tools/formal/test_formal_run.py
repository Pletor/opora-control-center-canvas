"""Result parsing of tools/formal/run.py on canned TLC outputs; no Java or TLC is started."""
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("opora_formal_run", HERE / "run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)

POSITIVE = {"name": "positive", "config": "ExecutionAuthority.cfg", "expect": "pass"}
NEGATIVE = {"name": "negative", "config": "NoFence.cfg", "expect": "violation", "invariant": "OneActiveOwner"}
STALE = {"name": "stale-negative", "config": "NoEpochReceipt.cfg", "expect": "violation",
         "invariant": "NoStaleEpochReceipt"}


def canned(name):
    return (HERE / "fixtures" / f"tlc-{name}.log").read_text(encoding="utf-8")


def test_positive_pass_requires_exhausted_queue_and_exit_zero():
    parsed = run.parse_output(canned("positive"), 0)
    assert parsed["result"] == "pass" and parsed["queue"] == 0 and parsed["distinct"] > 1_000_000
    assert run.evaluate(POSITIVE, parsed) == (True, None)
    assert run.parse_output(canned("positive"), 1)["result"] == "error"
    truncated = canned("positive").replace(" 0 states left on queue.", " 12 states left on queue.")
    assert run.parse_output(truncated, 0)["result"] == "incomplete"


def test_negative_must_violate_the_declared_invariant():
    parsed = run.parse_output(canned("negative"), 12)
    assert parsed["result"] == "violation" and parsed["violated"] == "OneActiveOwner"
    assert parsed["trace"] == ["Initial", "Claim", "ForceRelease", "Claim"]
    assert run.evaluate(NEGATIVE, parsed) == (True, None)
    stale = run.parse_output(canned("stale-negative"), 12)
    assert stale["trace"][-1] == "Result" and run.evaluate(STALE, stale) == (True, None)
    assert run.evaluate(STALE, parsed) == (False, "wrong_violation")


def test_counterexample_on_positive_and_vacuous_negative_fail_the_run():
    assert run.evaluate(POSITIVE, run.parse_output(canned("negative"), 12)) == (False, "positive_violation")
    assert run.evaluate(NEGATIVE, run.parse_output(canned("positive"), 0)) == (False, "negative_not_detected")


@pytest.mark.parametrize("text,code", [("", -1), ("TLC2 Version 2.19\n[runner] wall timeout\n", -1),
                                       ("Error: Parsing or semantic analysis failed.\n", 150),
                                       ("Running Random Simulation with seed 1\nNo error\n", 0)])
def test_tool_failures_are_runner_errors_never_passes(text, code):
    parsed = run.parse_output(text, code)
    assert parsed["result"] in {"error", "incomplete"}
    assert run.evaluate(POSITIVE, parsed) == (False, "runner_error")
    assert run.evaluate(NEGATIVE, parsed) == (False, "runner_error")


def test_other_violation_kinds_are_classified():
    assert run.parse_output("Error: Deadlock reached.\n", 11)["violated"] == "deadlock"
    assert run.parse_output("Error: Temporal properties were violated.\n", 13)["violationKind"] == "property"


def test_summary_and_annotation_are_machine_readable():
    parsed = run.parse_output(canned("negative"), 12)
    failed = run.case_result({"model": "m"}, POSITIVE, parsed, 1.0)
    passed = run.case_result({"model": "m"}, NEGATIVE, parsed, 1.0)
    document = run.summary([passed, failed], "a" * 40)
    assert document["ok"] is False and document["check"] == "formal/tlc"
    assert document["evidenceKinds"] == {"tlc": "connected", "lean": "not_connected"}
    json.dumps(document)
    line = run.annotation(failed)
    assert line.startswith("::error title=formal/tlc positive_violation::")
    payload = json.loads(line.split("::", 2)[2])
    assert payload == {"model": "m", "case": "positive", "config": "ExecutionAuthority.cfg", "expect": "pass",
                       "expectedInvariant": None, "kind": "positive_violation", "violated": "OneActiveOwner"}
    assert run.summary([])["ok"] is False


def test_bundled_suites_declare_positive_and_negative_configs():
    suites = run.load_suites()
    assert suites, "tools/formal must declare at least one TLC suite"
    for suite in suites:
        expectations = {case["expect"] for case in suite["cases"]}
        assert expectations == {"pass", "violation"}, suite["model"]
        for case in suite["cases"]:
            assert (suite["dir"] / case["config"]).is_file() and (suite["dir"] / suite["spec"]).is_file()


def test_jar_pin_rejects_wrong_bytes(tmp_path):
    fake = tmp_path / "tla2tools.jar"
    fake.write_bytes(b"not the pinned jar")
    with pytest.raises(run.RunnerError, match="SHA256"):
        run.pinned_jar(fake, cache_dir=tmp_path / "cache")
    with pytest.raises(run.RunnerError, match="--download"):
        run.pinned_jar(None, cache_dir=tmp_path / "cache")


def test_markdown_step_summary_lists_every_case():
    parsed = run.parse_output(canned("negative"), 12)
    text = run.markdown(run.summary([run.case_result({"model": "m"}, NEGATIVE, parsed, 1.0)]))
    assert "formal/tlc: ok" in text and "| m | negative | violation OneActiveOwner | violation OneActiveOwner |" in text
