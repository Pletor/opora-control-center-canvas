"""Independent scoped broker authentication; worker identities confer no authority."""
import hashlib
import hmac
import json
import os
import re
import time

from backend.editor.node.drawings import _json_safe

BODY_LIMIT = 128 * 1024
PROVIDER = "anthropic-managed-agents"


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field.")
            result[key] = value
        return result
    try:
        if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > BODY_LIMIT:
            raise ValueError("Observer body exceeds its limit.")
        value = json.loads(raw, object_pairs_hook=pairs)
        if not isinstance(value, dict):
            raise ValueError("Observer body must be an object.")  # noqa: TRY004 -- HTTP domain rejection.
        _json_safe(value)
        return value
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("Invalid observer JSON.") from error


def money(value, *, positive=False):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,17}", value):
        raise ValueError("Invalid USD list cost cents.")
    if positive and value == "0":
        raise ValueError("A positive provider list budget is required.")
    return value


def observers():
    try:
        raw = os.environ.get("OPORA_EXECUTION_OBSERVERS", "{}")
        if len(raw.encode("utf-8")) > 32768:
            raise ValueError()
        values = strict_json(raw)
        if len(values) > 32:
            raise ValueError()
        for name, value in values.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
                raise ValueError()
            if not isinstance(value, dict) or set(value) != {
                "secret", "project", "workspace", "provider", "maxListCostCents"
            }:
                raise ValueError()
            secret = value["secret"]
            if not isinstance(secret, str) or not 32 <= len(secret.encode("utf-8")) <= 512:
                raise ValueError()
            from backend.canvas.opora_change_validation import scope
            scope(value)
            if value["provider"] != PROVIDER:
                raise ValueError()
            money(value["maxListCostCents"], positive=True)
        return values
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError("Observer configuration is unavailable.") from None


def authenticate(headers, raw, *, clock=None):
    config = observers()
    name = headers.get("x-opora-observer-id", "")
    stamp = headers.get("x-opora-observer-time", "")
    signature = headers.get("x-opora-observer-signature", "")
    observer = config.get(name)
    if (not observer or not re.fullmatch(r"0|[1-9][0-9]{0,11}", stamp)
            or not re.fullmatch(r"[a-f0-9]{64}", signature)
            or abs((time.time() if clock is None else clock) - int(stamp)) > 300):
        raise PermissionError("Observer authentication failed.")
    message = stamp + "\n" + hashlib.sha256(raw).hexdigest()
    expected = hmac.new(observer["secret"].encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise PermissionError("Observer authentication failed.")
    payload = strict_json(raw)
    if any(payload.get(key) != observer[key] for key in ("project", "workspace")):
        raise PermissionError("Observer scope is not authorized.")
    return name, observer, payload
