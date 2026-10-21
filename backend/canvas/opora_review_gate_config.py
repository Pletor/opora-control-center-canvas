"""Config of the additional merge gate rules (docs/oporahub-review-jobs.md, "Pravidla brány").

Parsed from the same TOML as review jobs. A missing section switches its rule off so older
config files keep their meaning; the shipped file switches every rule on. Invalid values fail."""
import re

CHECK_NAME = re.compile(r"[A-Za-z0-9_.:/ ()-]{1,100}")
TIERS = ("low", "medium", "high")  # Same order as opora_review_risk.TIERS.
SELF_CHECK_NAME = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}")


def _strings(value, pattern, name, limit=50):
    if not isinstance(value, list) or len(value) > limit or not all(
            isinstance(item, str) and pattern.fullmatch(item) for item in value) or len(set(value)) != len(value):
        raise ValueError(f"Invalid review gate setting {name}.")
    return list(value)


def _seconds(value, name):
    if type(value) is not int or not 1 <= value <= 7 * 24 * 3600:
        raise ValueError(f"Invalid review gate setting {name}.")
    return value


def parse(raw):
    """`{security, selfChecks, mergeQueue, template}` from the raw TOML document."""
    security, checks = raw.get("security"), raw.get("self_checks") or {}
    queue, template = raw.get("merge_queue"), raw.get("template") or {}
    security_on = isinstance(security, dict) and security.get("enabled", True) is True
    tier = (security or {}).get("min_tier", "medium")
    if tier not in TIERS:
        raise ValueError("Invalid review gate setting security.min_tier.")
    paths = (security or {}).get("paths", [])
    if not isinstance(paths, list) or not all(isinstance(item, str) and 0 < len(item) <= 200 for item in paths):
        raise ValueError("Invalid review gate setting security.paths.")
    queue_on = isinstance(queue, dict) and queue.get("enabled", True) is True
    return {"security": {"enabled": security_on, "minTier": tier, "paths": list(paths)},
            "selfChecks": {"required": _strings(checks.get("required", []), SELF_CHECK_NAME, "self_checks.required")},
            "mergeQueue": {"enabled": queue_on,
                           "requiredChecks": _strings((queue or {}).get("required_checks", []), CHECK_NAME,
                                                      "merge_queue.required_checks"),
                           "maxAgeSeconds": _seconds((queue or {}).get("base_max_age_seconds", 900),
                                                     "merge_queue.base_max_age_seconds"),
                           "observeIntervalSeconds": _seconds((queue or {}).get("observe_interval_seconds", 60),
                                                              "merge_queue.observe_interval_seconds")},
            "template": {"sections": _strings(template.get("sections", []), re.compile(r"[^\n#]{1,80}"),
                                              "template.sections", 10)}}


DISABLED = parse({})


def rules(config):
    """The gate rule config of a parsed review job config (older hand-built dicts: everything off)."""
    return {key: config.get(key, DISABLED[key]) for key in DISABLED}
