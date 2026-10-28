"""Podněty k dalšímu vývoji karty: ne-blokující nálezy review, kritiků a lidí.

Stav uzlu `ideas = [{id, text, by, source, stageId?, fragmentId?, at, status}]`; `fragmentId` váže
podnět na fragment schránky zadání (`backend/editor/brief_vault/`). Kritik nebo review, který najde
okrajový případ, jenž nerozbije MVP ani proces, etapu nezastaví (`passed`) a nález pošle jako podnět
v `agent-output.output.ideas = [{text, source}]`; server ho přidá bez duplicit podle textu.
Odškrtnutí (`status: done`) a mazání patří člověku; obecný zápis stavu od agenta podněty nemění.
"""

import re
import uuid

from backend.canvas.graph import valid_id

IDEA_KEYS = {"id", "text", "by", "source", "at", "status"}
IDEA_KEY_SETS = (IDEA_KEYS, IDEA_KEYS | {"stageId"}, IDEA_KEYS | {"fragmentId"}, IDEA_KEYS | {"stageId", "fragmentId"})
OUTPUT_IDEA_KEYS = {"text", "source"}
OUTPUT_IDEA_KEY_SETS = (OUTPUT_IDEA_KEYS, OUTPUT_IDEA_KEYS | {"fragmentId"})
STATUSES = ("open", "done")
# Odkud podnět přišel: human, review, work, test, fix nebo critic:<pohled>.
SOURCE = re.compile(r"(human|agent|review|work|test|fix|critic:(user|sly|hacker))")
MAX_IDEAS = 200
MAX_OUTPUT_IDEAS = 20
MAX_IDEA_TEXT = 1000
MAX_AGENT = 120


def _fail(message):
    raise ValueError("Neplatné podněty karty: " + message)


def _text(value, limit, label):
    if not isinstance(value, str) or "\0" in value or len(value) > limit or not value.strip():
        _fail(f"{label} musí být neprázdný text do {limit} znaků.")


def _source(value):
    if not isinstance(value, str) or not SOURCE.fullmatch(value):
        _fail("source musí být human, agent, review, work, test, fix nebo critic:user|sly|hacker.")


def key_of(text):
    """Klíč pro duplicity: bez rozdílu ve velikosti písmen a bílých znacích."""
    return " ".join(text.split()).casefold()


def validate_ideas(value):
    if not isinstance(value, list) or len(value) > MAX_IDEAS:
        _fail(f"ideas musí být pole nejvýše {MAX_IDEAS} podnětů.")
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) not in IDEA_KEY_SETS:
            _fail("podnět má id, text, by, source, at, status a volitelně stageId a fragmentId.")
        if not isinstance(item["id"], str) or not valid_id(item["id"]) or item["id"] in seen:
            _fail("podnět má neplatné nebo opakované id.")
        seen.add(item["id"])
        _text(item["text"], MAX_IDEA_TEXT, "text podnětu")
        _text(item["by"], MAX_AGENT, "autor podnětu")
        _source(item["source"])
        if not isinstance(item["at"], str) or len(item["at"]) > 40:
            _fail("čas podnětu musí být text do 40 znaků.")
        if item["status"] not in STATUSES:
            _fail("stav podnětu musí být open nebo done.")
        if "stageId" in item and (not isinstance(item["stageId"], str) or not valid_id(item["stageId"])):
            _fail("stageId podnětu má neplatný identifikátor.")
        _fragment(item)
    return value


def _fragment(item):
    if "fragmentId" in item and (not isinstance(item["fragmentId"], str) or not valid_id(item["fragmentId"])):
        _fail("fragmentId podnětu má neplatný identifikátor.")


def validate_output_ideas(value):
    """Tvar `agent-output.output.ideas`; přidání a duplicity řeší `merge_ideas`."""
    if not isinstance(value, list) or len(value) > MAX_OUTPUT_IDEAS:
        raise ValueError(f"Neplatný výstup agenta: ideas musí být pole nejvýše {MAX_OUTPUT_IDEAS} podnětů.")
    for item in value:
        if not isinstance(item, dict) or set(item) not in OUTPUT_IDEA_KEY_SETS:
            raise ValueError("Neplatný výstup agenta: podnět má text, source a volitelně fragmentId.")
        _text(item["text"], MAX_IDEA_TEXT, "text podnětu")
        _source(item["source"])
        _fragment(item)
    return value


def merge_ideas(existing, incoming, agent, stamp, stage_id=""):
    """Nové podněty od agenta za stávající (bez duplicit podle textu); vrací nový seznam."""
    ideas = list(existing or [])
    known = {key_of(item["text"]) for item in ideas}
    for item in incoming:
        key = key_of(item["text"])
        if key in known:
            continue
        known.add(key)
        idea = {"id": uuid.uuid4().hex, "text": item["text"].strip(), "by": agent, "source": item["source"],
                "at": stamp, "status": "open"}
        if stage_id:
            idea["stageId"] = stage_id
        if item.get("fragmentId"):
            idea["fragmentId"] = item["fragmentId"]
        ideas.append(idea)
    if len(ideas) > MAX_IDEAS:
        raise ValueError(f"Karta má nejvýše {MAX_IDEAS} podnětů; odškrtnuté smaže člověk.")
    return ideas


def open_ideas(value):
    return [item for item in value or [] if item["status"] == "open"]


def brief_of(value):
    """Podněty pro node-brief: otevřené celé, hotové jen počtem."""
    ideas = value or []
    opened = open_ideas(ideas)
    return {"open": [{key: item[key] for key in ("id", "text", "source", "by", "at", "stageId", "fragmentId") if key in item}
                     for item in opened],
            "done": len(ideas) - len(opened),
            "policy": "non-blocking findings only; add via agent-output.output.ideas [{text, source}], a human marks them done"}


def guard_state_write(actor, previous, value):
    """Brána obecného zápisu stavu; agent s plnou autonomií projde jako člověk (docs/plna-autonomie-agenta.md)."""
    from backend.canvas.activity_log import HumanRequired
    from backend.canvas.authority import acts_as_human

    try:
        _guard_state_write(actor, previous, value)
    except HumanRequired:
        if not acts_as_human(actor):
            raise


def _guard_state_write(actor, previous, value):
    """Obecný zápis stavu od ne-člověka podněty nemění; agent je přidává přes agent-output."""
    from backend.canvas.activity_log import HumanRequired

    if (previous or []) != (value or []):
        raise HumanRequired(actor, "Podněty karty odškrtává a maže jen člověk; agent je přidává přes agent-output.ideas.")
