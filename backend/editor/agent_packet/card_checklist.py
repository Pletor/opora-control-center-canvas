"""Kontrolní pás karty: deset polí ano / ne, co karta pro agenta už má a co chybí.

Jediný výpočet pro plátno (pás pod hlavičkou karty, souhrn oblasti), `frontier` (`missing`)
i `node-brief` (`checklist`). Stav pole: `yes` (je / prošlo), `no` (chybí), `run` (rozpracováno),
`fail` (selhalo nebo čeká na člověka). `hint` říká, co doplnit a kam to zapsat.
Nic se neukládá; pás se počítá z grafu, stavu Desktop v3, zadání (spec) a textu karty.
"""

from backend.canvas.card_checks import checks_passed
from backend.editor.agent_memory import card_pipeline
from backend.editor.agent_memory.completion_evidence import evidence_ready

KEYS = ("goal", "done", "text", "blocks", "links", "source", "checks", "pipeline", "evidence", "handoff")
LABELS = {"goal": "cíl", "done": "hotovo", "text": "text", "blocks": "bloky", "links": "vazby", "source": "zdroj",
          "checks": "kontroly", "pipeline": "pipeline", "evidence": "důkazy", "handoff": "předávka"}


def _item(key, state, hint=""):
    return {"key": key, "label": LABELS[key], "state": state, "hint": hint}


def card_items(node, node_state, spec, text, edges, reports):
    """Pás jedné karty; `edges` jsou vazby grafu, `reports` zprávy na vazbách (`state.edges`)."""
    node_id = node["id"]
    blocks = node_state.get("blocks", [])
    evidence = node_state.get("evidence")
    stages = node_state.get("stages")
    outgoing = [e for e in edges if e["source"] == node_id and e.get("port", "next") in ("next", "block")]
    touching = [e for e in edges if node_id in (e["source"], e["target"])]
    items = [
        _item("goal", "yes" if spec.get("goal", "").strip() else "no", "" if spec.get("goal", "").strip() else "cíl práce → /api/node-spec fields.goal"),
        _item("done", "yes" if spec.get("acceptance", "").strip() or any(b["state"]["condition"] for b in blocks) else "no",
              "podmínky dokončení → fields.acceptance nebo podmínka bloku"),
        _item("text", "yes" if text.strip() else "no", "" if text.strip() else "výňatek zadání → /api/node-text"),
    ]
    if not blocks:
        items.append(_item("blocks", "no", "bloky s podmínkou → canvas-plan extend / block add"))
    elif any(b["state"]["status"] == "blocked" for b in blocks):
        items.append(_item("blocks", "fail", "blok čeká na člověka"))
    elif all(b["state"]["status"] == "met" for b in blocks):
        items.append(_item("blocks", "yes"))
    else:
        items.append(_item("blocks", "run", "bloky nejsou splněné → agent-output.blocks"))
    items.append(_item("links", "yes" if touching else "no", "" if touching else "vazba next / block na sousední kartu"))
    source = node.get("sourceRef")
    if not source:
        items.append(_item("source", "no", "kde v kódu → sourceRef"))
    elif source["origin"] == "existing":
        items.append(_item("source", "yes"))
    else:
        items.append(_item("source", "run", "plán; po merge → /api/desktop-v3/realize-source"))
    if not node.get("checks"):
        items.append(_item("checks", "no", "kontroly (příkaz testů) → checks na kartě (člověk)"))
    elif checks_passed(node, evidence):
        items.append(_item("checks", "yes"))
    else:
        items.append(_item("checks", "run", "kontroly bez zeleného běhu → evidence.checksRun"))
    if not stages or not stages.get("items"):
        items.append(_item("pipeline", "no", "proces → router /api/desktop-v3/pipeline"))
    elif card_pipeline.stuck(stages):
        items.append(_item("pipeline", "fail", "smyčka oprav došla, rozhoduje člověk"))
    elif not card_pipeline.open_stages(stages):
        items.append(_item("pipeline", "yes"))
    else:
        current = card_pipeline.current_stage(stages)
        items.append(_item("pipeline", "run", "na řadě: " + (current["title"] if current else "—")))
    if evidence is None:
        items.append(_item("evidence", "no", "důkazy → agent-output.evidence"))
    elif any(evidence[k]["status"] == "failed" for k in ("tests", "review", "merge")):
        items.append(_item("evidence", "fail", "důkaz selhal"))
    elif evidence_ready(evidence, node):
        items.append(_item("evidence", "yes"))
    else:
        items.append(_item("evidence", "run", "důkazy neúplné (tests / review / merge)"))
    sent = [e for e in outgoing if (reports.get(e["id"]) or {}).get("handoff", "").strip()]
    if not outgoing:
        items.append(_item("handoff", "yes", "bez odchozí vazby"))
    elif len(sent) == len(outgoing):
        items.append(_item("handoff", "yes"))
    else:
        items.append(_item("handoff", "run" if sent else "no", "předávka na vazbě → agent-output.reports[].handoff"))
    return items


def checklists(canvas, project, workspace, graph, state, node_ids=None):
    """Pás pro karty a sektory grafu (volitelně jen `node_ids`); čte zadání a text z úložiště."""
    reports = state.get("edges", {})
    out = {}
    for node in graph["nodes"]:
        if node.get("kind") not in ("node", "sector") or (node_ids is not None and node["id"] not in node_ids):
            continue
        scope = (project, workspace, node["id"])
        spec = canvas.specs.read(scope)["fields"]
        text = canvas.texts.read(scope)["text"]
        out[node["id"]] = card_items(node, state.get("nodes", {}).get(node["id"], {}), spec, text, graph["edges"], reports)
    return out


def missing(items):
    return [item["key"] for item in items if item["state"] != "yes"]
