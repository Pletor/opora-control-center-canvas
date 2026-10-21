"""Deterministic risk tier of a pull request change (docs/oporahub-review-jobs.md).

The tier comes from the change (changed paths and size), never from the author. Sensitive
path globs always require a human. An unobservable change fails closed to `high`."""
import os
import re
import tomllib
from functools import lru_cache
from pathlib import Path

from backend.canvas import opora_review_gate_config as gate_config

DEFAULT_PATH = Path(__file__).with_name("opora_review_jobs.toml")
TIERS = ("low", "medium", "high")


def _int(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Invalid review job setting {name}.")
    return value


def parse(raw):
    """Validated config; unknown or out-of-range values fail instead of silently weakening review."""
    jobs, risk, approvals = raw.get("jobs", {}), raw.get("risk", {}), raw.get("approvals", {})
    config = {"enabled": raw.get("enabled", False) is True,
              "finders": _int(jobs.get("finders", 3), 1, 9, "finders"),
              "voters": _int(jobs.get("voters", 3), 1, 9, "voters"),
              "requiredVotes": _int(jobs.get("required_votes", 2), 1, 9, "required_votes"),
              "maxRounds": _int(jobs.get("max_rounds", 3), 1, 20, "max_rounds"),
              "mediumLines": _int(risk.get("medium_lines", 200), 0, 10**7, "medium_lines"),
              "highLines": _int(risk.get("high_lines", 1000), 0, 10**7, "high_lines"),
              "mediumFiles": _int(risk.get("medium_files", 10), 0, 10**5, "medium_files"),
              "highFiles": _int(risk.get("high_files", 40), 0, 10**5, "high_files"),
              "sensitive": list(risk.get("sensitive", [])),
              "approvals": {tier: _int(approvals.get(tier, index), 0, 10, tier) for index, tier in enumerate(TIERS)},
              "sensitiveMinimum": _int(approvals.get("sensitive_minimum", 1), 1, 10, "sensitive_minimum"),
              "agentAccountIds": list(approvals.get("agent_account_ids", []))}
    if config["requiredVotes"] > config["voters"]:
        raise ValueError("required_votes cannot exceed voters.")
    if not all(isinstance(item, str) and 0 < len(item) <= 200 for item in config["sensitive"]):
        raise ValueError("Invalid sensitive path glob.")
    if not all(type(item) is int and item > 0 for item in config["agentAccountIds"]):
        raise ValueError("agent_account_ids must be positive GitHub account IDs.")
    config.update(gate_config.parse(raw))  # security, selfChecks, mergeQueue, template
    return config


@lru_cache(maxsize=8)
def _load(path, enabled_env):
    with open(path, "rb") as handle:
        config = parse(tomllib.load(handle))
    if enabled_env is not None:
        config["enabled"] = enabled_env == "1"
    return config


def load():
    """Shipped defaults, optionally replaced by OPORA_REVIEW_JOBS_CONFIG and switched by OPORA_REVIEW_JOBS."""
    path = os.environ.get("OPORA_REVIEW_JOBS_CONFIG") or str(DEFAULT_PATH)
    return dict(_load(path, os.environ.get("OPORA_REVIEW_JOBS")))


@lru_cache(maxsize=256)
def _pattern(glob):
    out, index = "", 0
    while index < len(glob):
        if glob.startswith("**/", index):
            out, index = out + "(?:.*/)?", index + 3
        elif glob.startswith("**", index):
            out, index = out + ".*", index + 2
        elif glob[index] == "*":
            out, index = out + "[^/]*", index + 1
        elif glob[index] == "?":
            out, index = out + "[^/]", index + 1
        else:
            out, index = out + re.escape(glob[index]), index + 1
    return re.compile(out + r"\Z", re.IGNORECASE)


def matches(glob, path):
    return _pattern(glob).match(path.lstrip("/")) is not None


def classify(change, config):
    """`change` is `{files: [{path, additions, deletions}], complete}` or None when unobserved.

    Returns `{tier, requiredApprovals, sensitive, reasons, changedFiles, changedLines}`."""
    if change is None or change.get("complete") is not True:
        return {"tier": "high", "requiredApprovals": config["approvals"]["high"], "sensitive": False,
                "reasons": ["change_unobserved"], "changedFiles": None, "changedLines": None}
    files = change["files"]
    lines = sum(item["additions"] + item["deletions"] for item in files)
    reasons, level = [], 0
    if lines >= config["highLines"] or len(files) >= config["highFiles"]:
        level, reasons = 2, ["large_change"]
    elif lines >= config["mediumLines"] or len(files) >= config["mediumFiles"]:
        level, reasons = 1, ["medium_change"]
    hits = sorted({glob for glob in config["sensitive"] for item in files if matches(glob, item["path"])})
    if hits:
        level = max(level, 1)
        reasons += ["sensitive_path:" + glob for glob in hits]
    tier = TIERS[level]
    required = config["approvals"][tier]
    if hits:
        required = max(required, config["sensitiveMinimum"])
    return {"tier": tier, "requiredApprovals": required, "sensitive": bool(hits), "reasons": reasons or ["small_change"],
            "changedFiles": len(files), "changedLines": lines}
