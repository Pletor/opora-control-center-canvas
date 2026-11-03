"""Příznaky „potřebuje úsudek“: deterministické, nad běhy stopy práce karty."""
import pytest

from backend.canvas.card_trail_judgment import allowed_path, judgment


def step(step_id="s1", status="done", checks=(), commits=("a" * 40,), files=None, allowed=None):
    value = {"stepId": step_id, "status": status, "checks": [{"name": n, "status": s} for n, s in checks],
             "commits": list(commits)}
    if files is not None:
        value["files"] = files
    if allowed is not None:
        value["allowed"] = allowed
    return value


def run(execution="e1", state="reported", steps=(), summary="Hotovo.", ticket=None, attempts=1, reported=True):
    return {"executionId": execution, "ticketId": ticket, "state": state, "summary": summary, "attempts": attempts,
            "reported": reported, "steps": list(steps)}


def codes(runs):
    return [item["code"] for item in judgment(runs)]


def test_clean_runs_have_no_flags():
    assert judgment([run(steps=[step(checks=[("npm test", "green")])])]) == []


def test_red_twice_counts_red_check_or_failed_step_across_runs():
    first = run("e1", steps=[step(status="failed", checks=[("npm test", "red")])])
    second = run("e2", steps=[step(status="done", checks=[("npm test", "red")])])
    assert codes([first]) == []
    (flag,) = [item for item in judgment([second, first]) if item["code"] == "red_twice"]
    assert flag["stepId"] == "s1" and flag["source"] == "det" and "2" in flag["reason"]


def test_failed_work_ticket_counts_once_like_a_failed_step():
    failed = run(None, state="failed", ticket="tk_1", attempts=0, steps=[step("tk_1", status="failed")])
    assert "red_twice" not in codes([failed])


def test_delivered_without_evidence_looks_at_newest_done_report_only():
    bare = run("e2", steps=[step(commits=())])
    proven = run("e1", steps=[step(checks=[("pytest", "green")])])
    assert codes([bare, proven]) == ["delivered_without_evidence"]
    assert codes([proven, bare]) == []


def test_missing_summary_only_for_finished_reported_runs():
    assert codes([run(summary="  ")]) == ["missing_summary"]
    assert codes([run(state="running", summary="")]) == []
    assert codes([run(state="revoked", summary="", reported=False)]) == []


def test_files_mismatch_needs_both_sides_and_lists_outside_files():
    outside = run(steps=[step(files=["src/a.ts", "README.md"], allowed=["src/*.ts"])])
    (flag,) = judgment([outside])
    assert flag["code"] == "files_mismatch" and flag["outside"] == ["README.md"]
    assert codes([run(steps=[step(files=["README.md"])])]) == []  # bez `files` kroku nic
    assert codes([run(steps=[step(allowed=["src/*.ts"])])]) == []  # bez souborů commitu nic


@pytest.mark.parametrize(("path", "patterns", "expected"), [
    ("src/a.ts", ["src/a.ts"], True),
    ("src/deep/a.ts", ["src/**"], True),
    ("src/deep/a.ts", ["src/"], True),
    ("src/deep/a.ts", ["src/*.ts"], True),  # fnmatch: `*` i přes `/` (raději méně planých poplachů)
    ("docs/a.md", ["src/**", "backend/*"], False),
    ("src\\a.ts", ["src/a.ts"], False),
])
def test_allowed_path(path, patterns, expected):
    assert allowed_path(path, patterns) is expected
