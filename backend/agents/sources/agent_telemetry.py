"""Allowlist veřejné telemetrie; raw zprávy a interní uvažování se nepřenášejí."""

import math
import re

from backend.agents.sources.agent_sources import clip, redact


def read_telemetry(fetch, base_url, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
        return {"runId": run_id, "available": False, "error": "invalid_bridge_id"}
    path = "/api/agent/" + run_id
    status, body = fetch(path)
    if status != 200 or not isinstance(body, dict) or not isinstance(body.get("state"), dict):
        return {"runId": run_id, "available": False, "source": base_url + path, "error": "telemetry_unavailable"}

    def public(fields, value):
        if not isinstance(value, dict):
            return {}
        result = {}
        for key in fields:
            item = value.get(key)
            if item is None or isinstance(item, (str, bool)):
                # Redakce musí proběhnout PŘED ořezem: ořez by mohl tajemství rozdělit
                # na kratší zbytek, který už žádný vzor nechytí, a nechat jeho začátek projít.
                result[key] = clip(redact(item), 1000) if isinstance(item, str) else item
            elif type(item) in (int, float) and math.isfinite(item):
                result[key] = item
        return result

    raw = body.get("raw")
    session = raw.get("worker_session") if isinstance(raw, dict) else None
    session = public(("session_id", "parent_session_id"), session)
    tools = body.get("tools")
    tools = tools if isinstance(tools, list) else []
    return {
        "runId": run_id, "available": True, "source": base_url + path,
        "sessionId": session.get("session_id"), "parentSessionId": session.get("parent_session_id"),
        "state": public(("value", "current_step", "checkpoint_status", "waiting_seconds", "source", "at"), body.get("state")),
        "context": public(("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "context_window", "context_percent", "source", "at"), body.get("context")),
        "costs": public(("actual_usd", "estimated_usd", "source", "at"), body.get("costs")),
        "model": public(("name", "provider", "variant", "source", "at"), body.get("model")),
        "time": public(("start", "end", "duration_seconds"), body.get("time")),
        "tools": [public(("at", "name", "args_preview", "source"), tool) for tool in tools],
        "usageAvailable": body.get("usage_available") is True,
    }
