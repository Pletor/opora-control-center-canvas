"""Persistent, bounded telemetry. CLI cumulative snapshots are replaced, never added.

No prompt/tool contents are stored. Counts describe observed results, not task quality.
"""
from __future__ import annotations

import math

TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
MODEL_FIELDS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "costUSD", "contextWindow")


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def numbers(value, fields):
    if not isinstance(value, dict):
        return {}
    return {key: number(value[key]) for key in fields if number(value.get(key)) is not None}


def observe(previous, item):
    """Return a new snapshot, or the original when this line has no measurements."""
    if not isinstance(item, dict):
        return previous
    data = dict(previous or {})
    kind = item.get("type")
    if kind == "system" and item.get("subtype") == "init":
        sid = item.get("session_id")
        if isinstance(sid, str) and sid != data.get("cliSessionId"):
            # /clear starts a new accounting epoch. Never mix old and new CLI totals.
            for key in ("models", "costUsd", "contextTokens", "lastUsage"):
                data.pop(key, None)
            data["cliSessionId"] = sid
        if isinstance(item.get("model"), str):
            data["model"] = item["model"][:160]
    elif kind == "system" and item.get("subtype") == "compact_boundary":
        data["compactions"] = data.get("compactions", 0) + 1
        data.pop("contextTokens", None)
    elif kind == "assistant" and not item.get("parent_tool_use_id"):
        message = item.get("message") or {}
        if not isinstance(message, dict):
            return previous
        usage = numbers(message.get("usage"), TOKEN_FIELDS)
        if "input_tokens" in usage:
            data["contextTokens"] = sum(usage.get(k, 0) for k in TOKEN_FIELDS if k != "output_tokens")
        if isinstance(message.get("model"), str):
            data["model"] = message["model"][:160]
    elif kind == "result":
        result_id = item.get("uuid")
        if result_id and result_id == data.get("lastResultId"):
            return previous
        data["lastResultId"] = result_id if isinstance(result_id, str) else None
        data["completed"] = data.get("completed", 0) + 1
        data["errors"] = data.get("errors", 0) + int(bool(item.get("is_error")))
        data["durationMs"] = data.get("durationMs", 0) + (number(item.get("duration_ms")) or 0)
        data["lastDurationMs"] = number(item.get("duration_ms"))
        data["lastError"] = bool(item.get("is_error"))
        data["lastUsage"] = numbers(item.get("usage"), TOKEN_FIELDS)
        data["steps"] = data.get("steps", 0) + (number(item.get("num_turns")) or 0)
        denials = item.get("permission_denials")
        data["denied"] = data.get("denied", 0) + (len(denials) if isinstance(denials, list) else 0)
        # Includes subagents; these are cumulative over CLI session/resume.
        data["costUsd"] = number(item.get("total_cost_usd"))
        models = item.get("modelUsage")
        data["models"] = {name[:160]: numbers(values, MODEL_FIELDS)
                          for name, values in list(models.items())[:32]
                          if isinstance(name, str)} if isinstance(models, dict) else {}
    else:
        return previous
    return data if data != previous else previous
