"""Kontrolní pás karty: deset polí ano / ne, co karta pro agenta už má a co chybí.

Jediný výpočet pro plátno (pás pod hlavičkou karty, souhrn oblasti), `frontier` (`missing`)
i `node-brief` (`checklist`). Stav pole: `yes` (je / prošlo), `no` (chybí), `run` (rozpracováno),
`fail` (selhalo nebo čeká na člověka). `hint` říká, co doplnit a kam to zapsat.
Nic se neukládá; pás se počítá z grafu, stavu Desktop v3, zadání (spec) a textu karty.
"""

import json

from backend.canvas.card_checks import checks_passed
from backend.editor.agent_memory import card_pipeline
from backend.editor.agent_memory.completion_evidence import evidence_ready
from backend.editor.node.node_specs import EMPTY_FIELDS

KEYS = ("goal", "done", "text", "blocks", "links", "source", "checks", "pipeline", "evidence", "handoff")
LABELS = {"goal": "cíl", "done": "hotovo", "text": "text", "blocks": "bloky", "links": "vazby", "source": "zdroj",
          "checks": "kontroly", "pipeline": "pipeline", "evidence": "důkazy", "handoff": "předávka"}


def _item(key, state, hint=""):
    return {"key": key, "label": LABELS[key], "state": state, "hint": hint}


class EdgeIndex:
    """Vazby grafu podle uzlu: odchozí `next` / `block` a všechny, které se uzlu dotýkají. Jeden průchod O(E)."""

    def __init__(self, edges):
        self.outgoing, self.touching = {}, {}
        for e in edges:
            source, target = e["source"], e["target"]
            self.touching.setdefault(source, []).append(e)
            if target != source:
                self.touching.setdefault(target, []).append(e)
            if not e.get("relation") and e.get("port", "next") in ("next", "block"):
                self.outgoing.setdefault(source, []).append(e)


def card_items(node, node_state, spec, text, edges, reports):
    """Pás jedné karty; `edges` jsou vazby grafu (seznam nebo hotový `EdgeIndex`), `reports` zprávy na vazbách (`state.edges`)."""
    node_id = node["id"]
    blocks = node_state.get("blocks", [])
    evidence = node_state.get("evidence")
    stages = node_state.get("stages")
    index = edges if isinstance(edges, EdgeIndex) else EdgeIndex(edges)
    outgoing = index.outgoing.get(node_id, [])
    touching = index.touching.get(node_id, [])
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


def _latest(canvas, project, workspace, table, column):
    """Poslední revize sloupce pro každý uzel prostoru jedním dotazem (místo dotazu na kartu).

    Stejný výsledek jako `NodeSpecStore.read` / `NodeTextStore.read` (`ORDER BY revision DESC LIMIT 1`):
    SQLite u `MAX()` s `GROUP BY` vrací ostatní sloupce z řádku s maximem.
    """
    rows = canvas.db_for(project).execute(
        f"SELECT node_id,{column},MAX(revision) FROM {table} WHERE project_id=? AND workspace_id=? GROUP BY node_id",
        (project, workspace)).fetchall()
    return {row[0]: row[1] for row in rows}


def checklists(canvas, project, workspace, graph, state, node_ids=None):
    """Pás pro karty a sektory grafu (volitelně jen `node_ids`); čte zadání a text z úložiště."""
    reports = state.get("edges", {})
    selected = [node for node in graph["nodes"]
                if node.get("kind") in ("node", "sector") and (node_ids is None or node["id"] in node_ids)]
    if not selected:
        return {}
    specs = _latest(canvas, project, workspace, "node_spec_revisions", "fields")
    texts = _latest(canvas, project, workspace, "node_text_revisions", "text")
    index = EdgeIndex(graph["edges"])
    out = {}
    for node in selected:
        raw = specs.get(node["id"])
        spec = json.loads(raw) if raw is not None else dict(EMPTY_FIELDS)
        out[node["id"]] = card_items(node, state.get("nodes", {}).get(node["id"], {}), spec, texts.get(node["id"], ""), index, reports)
    return out


def missing(items):
    return [item["key"] for item in items if item["state"] != "yes"]
