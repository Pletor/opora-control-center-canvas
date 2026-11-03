"""Typy uzlů srdce: obal dnešní logiky `backend/brain_opora/` (kontrakt docs/navrhy/2026-11-03-novy-zaklad.md §3.2).

Dávka teče `trigger.heart_event` / `trigger.human_message` → `decision.jev` → `context.snapshot` → `agent.claude`.
Data mezi uzly: `{project, workspace, items}` od spouštěče, pak `inputs` (po `resolve` a Jevu) a `snapshot`.
Všechny kroky dávky jsou `detached` (čtou projekt pod jeho zámkem, Jev jde po síti, `claude -p` běží minuty),
proto běží mimo zámek registru. Importy srdce jsou uvnitř funkcí: registr se načítá i tam, kde srdce neběží.
"""

import time
from collections import deque

from backend.flow.catalogs.heart.runtime import current, detached
from backend.flow.node_spec import NodeType, Port

AGENT_DEFAULTS = {"per_hour": 6, "per_project": 1, "rate_sleep_seconds": 15 * 60}
MODEL_DEFAULTS = {"model": "haiku", "advisor": "opus"}
SCHEDULE_DEFAULT_SECONDS = 600


def params(node, defaults):
    return {**defaults, **(node.get("params") or {})}


def _resolve(ctx, runtime):
    """Spouštěč: vstupy s aktuálními daty (`heart/inputs.resolve`). Vypnutá brána nebo nic k řešení = port `empty`."""
    from backend.brain_opora.determinism import gate_setting
    from backend.brain_opora.heart.inputs import resolve

    data = ctx["input"]
    if not gate_setting.is_on(runtime.service, data["project"]):
        runtime.heart.errors[data["project"]] = "Brána projektu je vypnutá."
        return "empty", {**data, "inputs": []}, None
    inputs = resolve(runtime.service, data["project"], data["items"])
    return ("main" if inputs else "empty"), {**data, "inputs": inputs}, None


def _jev(ctx, runtime):
    """Zařazení vstupů brány `pending` přes Jev (`decision/intake.classify_pending`); chyba Jevu vstupy nemění."""
    from backend.brain_opora.decision import intake

    data = ctx["input"]
    inputs = intake.classify_pending(runtime.service, data["project"], data["workspace"], data["inputs"],
                                     jev=runtime.heart.jev, now=runtime.heart.clock())
    return "main", {**data, "inputs": inputs}, None


def _snapshot(ctx, runtime):
    """Posun prostoru za `main` a snímek `collect` + `render` (`determinism/snapshot.snapshot`)."""
    from backend.brain_opora.determinism import snapshot

    data = ctx["input"]
    runtime.heart._advance_before_batch(data["project"], data["workspace"])
    limit = int(params(ctx["node"], {"limit": snapshot.LIMIT})["limit"])
    return "main", {**data, "snapshot": snapshot.snapshot(runtime.service, data["project"], data["workspace"],
                                                          limit)}, None


# Registrované nástroje srdce s pevným podpříkazem `opora_heart.py` (§3.2 „Ticket“); druhy brány ticket.issue/answer.
TOOL_SUBCOMMANDS = {"tool.ticket_issue": ("ticket-issue",), "tool.ticket_answer": ("ticket-answer",)}


def _subcommands(tools):
    """Povolené podpříkazy z nástrojových uzlů: `tool.opora_heart` bez výčtu = celý nástroj (None), registrovaný
    nástroj (`TOOL_SUBCOMMANDS`) přidá svůj podpříkaz, bez nástroje = žádný."""
    names = []
    for tool in tools:
        allowed = TOOL_SUBCOMMANDS.get(tool.get("type")) or tool["params"].get("subcommands")
        if allowed is None:
            return None
        names += [name for name in allowed if name not in names]
    return tuple(names)


def _agent(ctx, runtime):
    """Dávka `claude -p` stávajícím exekutorem (`heart/batch.run`); stav dávky drží supervisor jako dnes."""
    from backend.brain_opora.heart import batch
    from backend.brain_opora.heart.supervisor import _iso_utc

    data, heart = ctx["input"], runtime.heart
    project, workspace, inputs = data["project"], data["workspace"], data["inputs"]
    claude = heart.find()
    if claude is None:
        heart.errors[project] = "Claude Code nenalezen."
        return "main", {"status": "skipped", "error": heart.errors[project]}, None
    models = ctx["config"].get("model") or [{"params": {}}]
    model = params(models[0], MODEL_DEFAULTS)
    if not any(item.get("type") == "message" for item in inputs):
        with heart.lock:  # do stropu za hodinu se počítá dávka, která opravdu běží (jako supervisor)
            heart.starts.setdefault(project, deque()).append(heart.clock())
    with heart.lock:
        heart.current[project] = {"startedAt": _iso_utc(heart.clock()), "inputs": inputs}
    spec = batch.BatchSpec(brain=heart.brain(project), claude=claude, base_url=heart.base_url,
                           token=heart._token(project, workspace), project=project, workspace=workspace,
                           snapshot=data["snapshot"], inputs=inputs, source_root=heart._source(project, workspace),
                           model=model["model"], advisor_model=model["advisor"],
                           subcommands=_subcommands(ctx["config"].get("tool") or []))
    entry = batch.run(spec, heart.runner, heart.clock)
    heart.errors.pop(project, None)
    if entry["status"] == "rate_limited":
        heart.sleeping_until = heart.clock() + float(params(ctx["node"], AGENT_DEFAULTS)["rate_sleep_seconds"])
        for item in data["items"]:
            heart._add(project, workspace, item, heart.sleeping_until)
    output = {key: entry.get(key) for key in ("at", "status", "sessionId", "costUsd", "numTurns", "summary", "error")}
    return "main", output, {"provider": "anthropic", "model": model["model"], "cost_usd": entry.get("costUsd")}


def _schedule(ctx):
    """Rozvrh (místo 10min pojistky karet supervisoru): příští čtení outboxu projde karty všech prostorů."""
    heart = current().heart
    heart.card_at.clear()
    heart.polled_at = float("-inf")
    heart.wakeup.set()
    return {"port": "main", "output": {"rescan": True, "at": time.time()}}


def _sub_node(ctx):
    raise RuntimeError("Uzel sub-portu se nevykonává, je to konfigurace agenta.")


_TRIGGER_OUT = (Port("main", "out"), Port("empty", "out"))
_STEP = (Port("main", "in"), Port("main", "out"))

HEART_TYPES = (
    NodeType("trigger.heart_event", 1, _TRIGGER_OUT, detached(_resolve), trigger=True, detached=True),
    NodeType("trigger.human_message", 1, _TRIGGER_OUT, detached(_resolve), trigger=True, detached=True),
    NodeType("trigger.schedule", 1, (Port("main", "out"),), _schedule, trigger=True),
    NodeType("decision.jev", 1, _STEP, detached(_jev), detached=True),
    NodeType("context.snapshot", 1, _STEP, detached(_snapshot), detached=True),
    NodeType("agent.claude", 1,
             (*_STEP, Port("model", "in", "model", "one"), Port("tool", "in", "tool"),
              Port("memory", "in", "memory", "one")),
             detached(_agent), detached=True),
    NodeType("model.claude", 1, (Port("model", "out", "model"),), _sub_node),
    NodeType("tool.opora_heart", 1, (Port("tool", "out", "tool"),), _sub_node),
    *(NodeType(name, 1, (Port("tool", "out", "tool"),), _sub_node) for name in TOOL_SUBCOMMANDS),
)
