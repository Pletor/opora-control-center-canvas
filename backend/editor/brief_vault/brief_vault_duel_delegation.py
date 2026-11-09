"""Explicit role simulation under one verified Heart principal, never independent review."""
from backend.editor.brief_vault.brief_vault_model import bad_request

ROLES = {"advocate_a": "A", "advocate_b": "B", "judge_1": "judge", "judge_2": "judge"}


def participant(record):
    principal = record.get("by", record.get("judge"))
    return (principal, record["delegateRole"]) if "delegateRole" in record else principal


def authorize(w, payload, duel=None):
    mode = (duel or {}).get("delegation")
    requested = payload.get("delegatedRoles", False)
    if "delegatedRoles" in payload and requested is not True:
        bad_request("delegatedRoles must be true.")
    role = payload.get("delegateRole")
    if not mode and not requested:
        if role is not None:
            bad_request("delegateRole requires an explicitly delegated duel.")
        return {}
    session = getattr(w, "duel_session", None)
    if not session or session.get("role") != "heart" or w.actor != "agent" or session["worker_name"] != w.by:
        bad_request("Delegated duel requires a verified Heart session.")
    owner = {"mode": "single-principal-role-simulation", "principal": w.by, "sessionId": session["id"]}
    if mode and mode != owner:
        bad_request("Delegated duel belongs to another authenticated principal/session.")
    if payload["op"] == "duel-open":
        if requested is not True:
            bad_request("delegatedRoles must be true.")
        return {"delegation": owner}
    if payload["op"] == "duel-decide":
        return {}
    expected = payload.get("side") if payload["op"] == "duel-turn" else "judge"
    if not isinstance(role, str) or role not in ROLES or ROLES[role] != expected:
        bad_request("delegateRole is invalid for this duel operation/side.")
    return {"delegateRole": role, "principalSessionId": session["id"]}
