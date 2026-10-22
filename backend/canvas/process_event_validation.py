"""Tvar události živého procesu `opora.process-event/1` (docs/zivy-proces.md §2).

Čistá funkce bez I/O: z libovolného JSON udělá normalizovanou událost, nebo vyhodí
`ValueError` s českým důvodem. Neznámé klíče se zahazují (i v `refs`, `actor`, `tool`),
dlouhé texty se zkracují na stropy kontraktu, výčty se hlídají přesně.
"""
import re
from datetime import datetime

SCHEMA = "opora.process-event/1"
SOURCES = ("office", "opora", "github")
INGEST_SOURCES = ("office", "github")  # vlastní události Opory vznikají z activity_log, ne POSTem
PHASES = ("intake", "plan", "work", "checks", "review", "merge", "memory")
STATES = ("start", "progress", "ok", "fail", "wait", "blocked", "info")
ACTOR_KINDS = ("worker", "human", "agent", "system")
TOOL_ACTIONS = ("read", "edit", "test", "web", "command", "failing")
TITLE_MAX, DETAIL_MAX, TARGET_MAX = 120, 240, 80
ID_MAX, REF_MAX, NAME_MAX = 200, 200, 80
KIND = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
REF_TEXT = ("project", "workspace", "cardId", "executionId", "workerId", "floor", "branch", "sha", "url")
MAX_BATCH = 50


def clip(text, limit):
    """Zkrátí text na `limit` znaků; zkrácení je vidět jako výpustka."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _text(value, label, limit, *, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{label} musí být neprázdný text.")
    return clip(value, limit)


def _short(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} musí být text do {limit} znaků.")
    return value


def _at(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("at musí být čas ISO 8601.")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("at musí být čas ISO 8601.") from None
    return value


def _refs(value):
    if not isinstance(value, dict):
        raise ValueError("refs musí být objekt.")  # noqa: TRY004 - API to vrací jako 422
    refs = {}
    for key in REF_TEXT:
        if value.get(key) is not None:
            refs[key] = _short(value[key], f"refs.{key}", REF_MAX)
    pr = value.get("pr")
    if pr is not None:
        if type(pr) is not int or pr < 1:
            raise ValueError("refs.pr musí být kladné celé číslo.")
        refs["pr"] = pr
    return refs


def _actor(value):
    if not isinstance(value, dict) or value.get("kind") not in ACTOR_KINDS:
        raise ValueError("actor.kind musí být " + " | ".join(ACTOR_KINDS) + ".")
    actor = {"kind": value["kind"]}
    for key in ("id", "name"):
        if value.get(key) is not None:
            actor[key] = _text(value[key], f"actor.{key}", NAME_MAX)
    return actor


def _tool(value):
    if not isinstance(value, dict):
        raise ValueError("tool musí být objekt.")  # noqa: TRY004 - API to vrací jako 422
    tool = {"name": _text(value.get("name"), "tool.name", NAME_MAX)}
    if value.get("action") is not None:
        if value["action"] not in TOOL_ACTIONS:
            raise ValueError("tool.action musí být " + " | ".join(TOOL_ACTIONS) + ".")
        tool["action"] = value["action"]
    if value.get("target") is not None:
        tool["target"] = _text(value["target"], "tool.target", TARGET_MAX)
    return tool


def normalize(raw, *, sources=SOURCES):
    """Normalizovaná událost (jen známé klíče), nebo ValueError."""
    if not isinstance(raw, dict):
        raise ValueError("Událost musí být objekt.")  # noqa: TRY004 - API to vrací jako 422
    if raw.get("schema") != SCHEMA:
        raise ValueError(f"schema musí být {SCHEMA}.")
    if raw.get("source") not in sources:
        raise ValueError("source musí být " + " | ".join(sources) + ".")
    if raw.get("phase") not in PHASES:
        raise ValueError("phase musí být " + " | ".join(PHASES) + ".")
    if raw.get("state") not in STATES:
        raise ValueError("state musí být " + " | ".join(STATES) + ".")
    if not isinstance(raw.get("kind"), str) or not KIND.match(raw["kind"]):
        raise ValueError("kind musí být krátký identifikátor v tečkové notaci.")
    seq = raw.get("seq")
    if type(seq) is not int or seq < 0:
        raise ValueError("seq musí být nezáporné celé číslo.")
    event = {
        "schema": SCHEMA, "id": _short(raw.get("id"), "id", ID_MAX), "seq": seq, "at": _at(raw.get("at")),
        "source": raw["source"], "kind": raw["kind"], "phase": raw["phase"], "state": raw["state"],
        "title": _text(raw.get("title"), "title", TITLE_MAX),
    }
    detail = _text(raw.get("detail"), "detail", DETAIL_MAX, required=False)
    if detail:
        event["detail"] = detail
    if raw.get("actor") is not None:
        event["actor"] = _actor(raw["actor"])
    event["refs"] = _refs(raw.get("refs"))
    if raw.get("tool") is not None:
        event["tool"] = _tool(raw["tool"])
    return event


def batch(payload):
    """Seznam surových událostí z těla `{events: [...]}`; špatné tělo = ValueError (celé odmítnuté)."""
    if not isinstance(payload, dict) or set(payload) != {"events"}:
        raise ValueError("Tělo je přesně {events: ProcessEvent[]}.")
    events = payload["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_BATCH:
        raise ValueError(f"events musí být pole 1–{MAX_BATCH} událostí.")
    return events
