"""Odvozená orientace nového agenta z již sestaveného node-briefu.

Funkce je čistá: nečte soubory, nevolá síť ani nemění stav. UI i strojový brief proto
vidí stejný autoritativní stav karty a orientace nepředstírá existenci žádné dokumentace.
"""

SCHEMA = "opora.agent-orientation/1"


def _status(value):
    return "present" if value else "missing"


def _item(identifier, label, instruction, sources):
    return {"id": identifier, "label": label, "status": "missing", "instruction": instruction, "sources": sources}


def orientation_from_brief(brief, project=None, workspace=None):
    """Vrátí krátký zobrazitelný pohled, aniž by zahazoval původní ID nebo pole briefu."""
    node, goal, context, agent_workspace = brief["node"], brief["goal"], brief["context"], brief["agentWorkspace"]
    materials = [{**item, "status": "present" if item.get("url") or item.get("path") else "unavailable"} for item in context["materials"]]
    communication = brief.get("communication", {})
    communication_available = communication.get("status", "present") != "unavailable"
    done = brief.get("loop", {}).get("done", {})
    has_definition = bool(goal["acceptance"] or brief["definitionOfDone"]["criteria"] or brief["definitionOfDone"]["blockConditions"])
    effective_read_only = brief["readOnly"] or done.get("confirmed", False)
    workspace_hidden = brief["readOnly"]
    workspace_reading = {
        "id": "workspace", "label": "Pracovní paměť a předávka", "source": "agentWorkspace",
        "status": "unavailable" if workspace_hidden else _status(agent_workspace.get("frame") or agent_workspace.get("handoff")),
        "nodeId": node["id"],
    }
    if workspace_hidden:
        workspace_reading["reason"] = "Pracovní paměť se v tomto pohledu pouze ke čtení nezobrazuje."
    # Paměť role se do pořadí čtení dostane jen tehdy, když opravdu něco nese. Prázdná,
    # vypnutá ani nedostupná paměť se nepředstírá jako podklad ke čtení.
    role_memory = context.get("roleMemory") or {}
    role_memory_items = role_memory.get("items") or []
    reading = [
        {"id": "card", "label": "Karta a její cíl", "source": "node", "status": _status(goal["goal"]), "nodeId": node["id"]},
        *[{"id": f"material:{item['id']}", "label": item["caption"] or item["path"], "source": "material", "status": item["status"], "sourceNodeId": item["sourceNodeId"], "materialId": item["id"]} for item in materials],
        *([{"id": "role-memory", "label": "Paměť role", "source": "context.roleMemory", "status": "present", "nodeId": node["id"], "role": role_memory.get("role")}] if role_memory_items else []),
        workspace_reading,
        {"id": "messages", "label": "Příchozí a odchozí komunikace", "source": "communication", "status": "present" if communication_available else "unavailable", "nodeId": node["id"]},
    ]
    gaps = []
    if not goal["goal"]:
        gaps.append(_item("goal", "Chybí cíl", "Doplňte cíl karty před samostatným pokračováním.", [{"source": "goal"}]))
    if not has_definition:
        gaps.append(_item("acceptance", "Chybí definice hotovo", "Požádejte o kritéria dokončení nebo je doplňte v kartě.", [{"source": "definitionOfDone"}]))
    if not workspace_hidden and not any(agent_workspace.get(key) for key in ("frame", "log", "failures", "fixes", "handoff")):
        gaps.append(_item("agent-workspace", "Chybí pracovní předávka", "Přečtěte komunikaci a vyžádejte si předávku.", [{"source": "agentWorkspace"}]))
    if not communication_available:
        gaps.append(_item("communication", "Komunikace není dostupná", communication.get("reason", "Služba komunikace není dostupná."), [{"source": "communication"}]))
    optional = []
    if not materials:
        optional.append(_item("materials", "Nejsou připojené podklady", "Podklady doplňte jen pokud je tento úkol potřebuje.", [{"source": "context.materials"}]))
    if not context["knowledgeGraph"]["available"]:
        optional.append(_item("knowledge-graph", "Mapa projektu není dostupná", "Mapa je volitelný kontext; není ověřeno, že existuje.", [{"source": "context.knowledgeGraph"}]))
    if effective_read_only:
        next_action = {"kind": "read-only", "label": "Karta je pouze ke čtení; požádejte vlastníka o znovuotevření, neprovádějte zápis.", "status": "recommendation", "sources": [{"source": "loop.done"}]}
    elif gaps:
        next_action = {"kind": "request-context", "label": gaps[0]["instruction"], "status": "recommendation", "sources": gaps[0]["sources"]}
    else:
        next_action = {"kind": "follow-harness", "label": "Pokračujte prvním nehotovým krokem karty.", "status": "recommendation", "sources": [{"source": "harness.steps"}]}
    return {
        "schema": SCHEMA, "scope": {"project": project, "workspace": workspace, "nodeId": node["id"], "path": [*node["path"], node["name"]], "readOnly": effective_read_only},
        "goal": {**goal, "status": _status(goal["goal"])}, "definitionOfDone": {**brief["definitionOfDone"], "status": "present" if has_definition else "missing"},
        "boundaries": brief["boundaries"], "materials": materials, "readingOrder": reading, "contextGaps": gaps, "optionalContext": optional,
        "nextAction": next_action, "blocks": brief["blocks"], "harness": brief["harness"],
        "safety": {"readOnly": effective_read_only, "automaticModelInvocation": False, "automaticAck": False, "ownershipTransfer": False},
    }
