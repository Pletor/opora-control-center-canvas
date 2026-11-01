"""Risk tier rules: from the change only, sensitive paths need a human, unobserved fails closed."""
import pytest

from backend.canvas.opora_review_risk import DEFAULT_PATH, classify, load, matches, parse

CONFIG = parse({"enabled": True, "risk": {"sensitive": [".github/workflows/**", "**/auth/**", "**/migrations/**"]}})


def change(*files, complete=True):
    return {"complete": complete, "baseSha": "b" * 40,
            "files": [{"path": path, "additions": added, "deletions": removed} for path, added, removed in files]}


def test_size_rules_map_to_tiers_and_required_approvals():
    assert classify(change(("src/a.py", 10, 5)), CONFIG) | {} == {
        "tier": "low", "requiredApprovals": 0, "sensitive": False, "reasons": ["small_change"],
        "changedFiles": 1, "changedLines": 15}
    medium = classify(change(("src/a.py", 150, 50)), CONFIG)
    assert (medium["tier"], medium["requiredApprovals"], medium["reasons"]) == ("medium", 1, ["medium_change"])
    files = [(f"src/f{index}.py", 1, 0) for index in range(40)]
    large = classify(change(*files), CONFIG)
    assert (large["tier"], large["requiredApprovals"], large["reasons"]) == ("high", 1, ["large_change"])
    assert classify(change(("src/a.py", 999, 1)), CONFIG)["tier"] == "high"


def test_sensitive_paths_always_need_a_human():
    result = classify(change((".github/workflows/ci.yml", 1, 0)), CONFIG)
    assert result["tier"] == "medium" and result["requiredApprovals"] == 1 and result["sensitive"] is True
    assert result["reasons"] == ["sensitive_path:.github/workflows/**"]
    strict = parse({"approvals": {"medium": 0, "sensitive_minimum": 2}, "risk": {"sensitive": ["**/auth/**"]}})
    assert classify(change(("auth/login.py", 1, 0)), strict)["requiredApprovals"] == 2
    big = classify(change(("db/migrations/001.sql", 2000, 0)), CONFIG)
    assert big["tier"] == "high" and big["reasons"] == ["large_change", "sensitive_path:**/migrations/**"]


def test_unobserved_or_incomplete_change_fails_closed():
    for value in (None, change(("src/a.py", 1, 0), complete=False)):
        result = classify(value, CONFIG)
        assert result["tier"] == "high" and result["requiredApprovals"] == 1 and result["reasons"] == ["change_unobserved"]


def test_high_tier_approvals_can_be_raised_back():
    team = parse({"approvals": {"high": 2}})
    assert classify(change(("src/a.py", 999, 1)), team)["requiredApprovals"] == 2
    assert classify(None, team)["requiredApprovals"] == 2
    with pytest.raises(ValueError, match="sensitive_minimum"):
        parse({"approvals": {"sensitive_minimum": 0}})


def test_glob_semantics():
    assert matches("**/auth/**", "auth/x.py") and matches("**/auth/**", "src/auth/deep/y.py")
    assert not matches("**/auth/**", "src/author.py")
    assert matches(".github/workflows/**", ".github/workflows/sub/ci.yml")
    assert matches("**/*auth*.*", "backend/oauth_client.py") and not matches("*.pem", "keys/a.pem")
    assert matches("package.json", "package.json") and not matches("package.json", "web/package.json")


def test_config_is_validated_and_shipped_default_is_disabled(monkeypatch):
    with pytest.raises(ValueError, match="required_votes"):
        parse({"jobs": {"voters": 1, "required_votes": 2}})
    with pytest.raises(ValueError, match="agent_account_ids"):
        parse({"approvals": {"agent_account_ids": ["bot"]}})
    with pytest.raises(ValueError, match="finders"):
        parse({"jobs": {"finders": True}})
    monkeypatch.delenv("OPORA_REVIEW_JOBS", raising=False)
    monkeypatch.delenv("OPORA_REVIEW_JOBS_CONFIG", raising=False)
    shipped = load()
    assert shipped["enabled"] is False and shipped["finders"] == 3 and shipped["maxRounds"] == 3
    # Owner decision 2026-11-01 (GATE-001, full autonomy): no human approval by tier; sensitive paths still need one.
    assert shipped["approvals"] == {"low": 0, "medium": 0, "high": 0} and DEFAULT_PATH.exists()
    assert shipped["sensitiveMinimum"] >= 1
    monkeypatch.setenv("OPORA_REVIEW_JOBS", "1")
    assert load()["enabled"] is True
