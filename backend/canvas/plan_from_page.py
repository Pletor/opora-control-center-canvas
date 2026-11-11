"""Srdce staví plátno 3 z plátna 2 (F3, `docs/navrhy/2026-11-11-platno-3-folie.md`), deterministicky, bez modelu.

Ze stránky (nebo všech stránek domény) vznikne přírůstek grafu jako **návrh grafu srdce** (`graph-proposals`, stejná
cesta jako `opora_heart.py plan`; přijímá člověk v UI, nic se nezapíše mimo návrh):
- proces = sektor „Plán práce: <stránka>“ pod doménou s cílem stránky, vazbou „dokládá“ na stránku;
- oblast na milník prvku (`page_plan.MILESTONES` v pořadí) uvnitř procesu, sled oblastí = vazby `flow`;
- karta na prvek logiky v oblasti jeho dnešního milníku: název, účel (`spec.goal`), kritéria z `flow.outputs`
  (`spec.acceptance`), odkaz na prvek vazbou „dokládá“ (`evidences`, čte ji `plan_reality.element_of`);
- vazby mezi kartami: `uses` podle `flow.dataTo` (jméno jiného prvku) a `requires` / `uses` převzaté z vazeb prvků.

Box bez prvku logiky kartu nedostane: práci nese prvek (tok, výstupy, kritéria); prázdný box je jen rozvržení
a jeho vzhled pokrývá proces stránky. Výsledek ho vypíše v `skipped.boxes`.
Idempotence: klíč karty = id prvku (vazba „dokládá“), procesu = id stránky, oblasti = název v procesu. Opakovaná
stavba přidá jen chybějící; karta, jejíž prvek zmizel, se nemaže, jen se vypíše v `orphans`.
"""
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas import plan_reality
from backend.canvas.canvas_plan_layout import AREA_PAD, CARD, GAP
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.project.architecture import page_plan

SUBJECT = "Srdce staví plátno 3"
HEART = {"kind": "agent", "name": "heart"}  # stejný autor jako návrh grafu tokenem srdce
LINKED = ("requires", "uses")  # vazby prvků plátna 2, které karta převezme


def pages_for(graph, node_id):
    """Stránka sama, nebo všechny stránky domény (`site.kind application`); jinak 404."""
    node = next((item for item in graph["nodes"] if item["id"] == node_id), None)
    kind = ((node or {}).get("site") or {}).get("kind")
    if kind == "page":
        return [node]
    if kind == "application":
        return page_plan.domain_pages(graph, node_id)
    raise GateError(404, "page_not_found", f"Uzel {node_id!r} není stránka ani doména v tomto prostoru.",
                    "pageId je id uzlu se site.kind page nebo application (GET /api/view).")


def _domain_of(graph, page):
    by_id = {item["id"]: item for item in graph["nodes"]}
    cursor = by_id.get(page.get("parentId"))
    while cursor is not None and (cursor.get("site") or {}).get("kind") != "application":
        cursor = by_id.get(cursor.get("parentId"))
    return cursor and cursor["id"]


def _area_size(cards):
    """Sloupec na jednu kartu na šířku a na `cards` karet na výšku (rozmístění ho při potřebě zvětší)."""
    return {"w": CARD[0] + 2 * AREA_PAD, "h": max(1, cards) * (CARD[1] + GAP) - GAP + 2 * AREA_PAD}


def addition(graph, plans, flows):
    """Čistý přírůstek. `plans` = `[(page, page_plan.read(...))]`, `flows` = `{elementId: graf toku | None}`.
    Vrací `{plan: {nodes, edges}, pages, counts, existing, skipped, unmatched, orphans}`."""
    nodes_by_id = {item["id"]: item for item in graph["nodes"]}
    evidence = [edge for edge in graph["edges"] if edge.get("relation") == "evidences"]
    card_of = {edge["target"]: edge["source"] for edge in evidence
               if "element" in nodes_by_id.get(edge["target"], {}) and "element" not in nodes_by_id[edge["source"]]}
    frame_of = {edge["target"]: edge["source"] for edge in evidence
                if nodes_by_id[edge["source"]]["kind"] == "sector"}
    present = {(edge["source"], edge["target"], edge.get("relation"), edge.get("port", "next")) for edge in graph["edges"]}
    nodes, edges, out_pages, skipped_pages, boxes, orphans = [], [], [], [], [], []
    existing = {"frames": 0, "areas": 0, "cards": 0}
    ref_of = {}  # id prvku → "@karta" nebo ref nové karty

    def link(source, target, relation=None, port=None):
        ids = tuple(value.removeprefix("@") for value in (source, target))
        if (*ids, relation, port or "next") not in present:
            present.add((*ids, relation, port or "next"))
            edges.append({"from": source, "to": target, **({"relation": relation} if relation else {}),
                          **({"port": port} if port else {})})

    for index, (page, plan) in enumerate(plans):
        logic = plan["logic"]
        used = {item["section"] for item in logic}
        boxes += [{"pageId": page["id"], "id": box["id"], "name": box.get("name") or box["id"]}
                  for box in plan["sections"] if box["id"] not in used]
        if not logic:
            skipped_pages.append({"pageId": page["id"], "name": page["name"]})
            continue
        frame_id = frame_of.get(page["id"])
        if frame_id:
            existing["frames"] += 1
            frame = "@" + frame_id
            orphans += [{"nodeId": item["id"], "name": item["name"]} for item in graph["nodes"]
                        if item.get("parentId") == frame_id and item["kind"] == "node"
                        and item["id"] not in card_of.values()]
        else:
            frame = f"p{index}"
            domain = _domain_of(graph, page)
            nodes.append({"ref": frame, "kind": "sector", "name": f"Plán práce: {page['name']}",
                          "purpose": plan["page"].get("goal") or "", "parent": domain and "@" + domain})
            link(frame, "@" + page["id"], "evidences")
        out_pages.append({"pageId": page["id"], "name": page["name"], "frameId": frame_id})
        areas = {item["name"]: "@" + item["id"] for item in graph["nodes"]
                 if frame_id and item["kind"] == "area" and item.get("parentId") == frame_id}
        new_cards = [item for item in logic if item["id"] not in card_of]
        existing["cards"] += len(logic) - len(new_cards)
        previous = None
        for step, label in enumerate(page_plan.MILESTONES):
            if label in areas:
                existing["areas"] += 1
            else:
                areas[label] = f"p{index}-m{step}"
                count = sum(item["milestone"] == label for item in new_cards)
                nodes.append({"ref": areas[label], "kind": "area", "name": label, "parent": frame,
                              "size": _area_size(count)})
            if previous:
                link(previous, areas[label], port="flow")
            previous = areas[label]
        for item in logic:
            if item["id"] in card_of:
                ref_of[item["id"]] = "@" + card_of[item["id"]]
                continue
            ref = ref_of[item["id"]] = f"e{len(ref_of)}"
            outputs = plan_reality.flow_lists(flows.get(item["id"]))["outputs"]
            area = areas[item["milestone"]]
            nodes.append({"ref": ref, "kind": "node", "name": item["name"], "purpose": item["purpose"] or "",
                          "parent": area, "memberOf": area,
                          "spec": {"goal": item["purpose"] or "",
                                   "acceptance": "\n".join(f"- {text}" for text in outputs)}})
            link(ref, "@" + item["id"], "evidences")
    # Vazby mezi kartami: z `dataTo` toku (jméno jiného prvku) a převzaté vazby prvků plátna 2.
    names = {plan_reality._norm(nodes_by_id[element]["name"]): element for element in ref_of}
    unmatched = []
    for element, ref in ref_of.items():
        for text in plan_reality.flow_lists(flows.get(element))["dataTo"]:
            target = names.get(plan_reality._norm(text))
            if target and target != element:
                link(ref, ref_of[target], "uses")
            else:
                unmatched.append({"elementId": element, "name": nodes_by_id[element]["name"], "dataTo": text})
    for edge in graph["edges"]:
        if edge.get("relation") in LINKED and edge["source"] in ref_of and edge["target"] in ref_of:
            link(ref_of[edge["source"]], ref_of[edge["target"]], edge["relation"])
    counts = {"areas": sum(item["kind"] == "area" for item in nodes),
              "cards": sum(item["kind"] == "node" for item in nodes), "edges": len(edges)}
    return {"plan": {"nodes": nodes, "edges": edges}, "pages": out_pages, "counts": counts, "existing": existing,
            "skipped": {"pages": skipped_pages, "boxes": boxes}, "unmatched": unmatched, "orphans": orphans}


def build(service, project, workspace, node_id):
    """Přírůstek ze stránky / domény a z něj návrh grafu srdce (nepřijatý). Bez rozdílu žádný návrh nevznikne;
    stejný nepřijatý návrh nad stejnou hlavou a grafem se vrátí místo nového (dvojí klik)."""
    graph = service.view(project, workspace)["graph"]
    pages = pages_for(graph, node_id)
    plans = [(page, page_plan.read(service, project, workspace, page["id"])) for page in pages]
    by_id = {item["id"]: item for item in graph["nodes"]}
    flows = {item["id"]: plan_reality.flow_of(service, project, by_id[item["id"]])
             for _, plan in plans for item in plan["logic"]}
    result = addition(graph, plans, flows)
    if not result["plan"]["nodes"] and not result["plan"]["edges"]:
        return {**result, "proposal": None}
    proposals = OporaGraphProposals(service)
    subject = f"{SUBJECT}: {by_id[node_id]['name']}"
    try:
        context = proposals.context(project, workspace)
        for item in proposals.list(project, workspace)["items"]:
            # Platný (stejná hlava i graf) nepřijatý návrh stavby: stejný rozsah se vrátí, jiný (stránka vs. doména)
            # by po přijetí jednoho a rebase druhého zdvojil karty, proto 409.
            if (not item["subject"].startswith(SUBJECT) or item["accepted"] or item.get("supersededBy")
                    or item["parentRevision"] != context["acceptedHead"]
                    or proposals.read(project, workspace, item["id"])["graphDigest"] != context["graphDigest"]):
                continue
            if item["subject"] == subject:
                return {**result, "proposal": {"id": item["id"], "reused": True}}
            raise GateError(409, "plan_pending", f"Čeká návrh stavby {item['id']} ({item['subject']}).",
                            f"Přijmi nebo zahoď návrh {item['id']} v OporaHubu, pak stavba vrátí jen rozdíl.")
        created = proposals.create({"project": project, "workspace": workspace,
                                    "parentRevision": context["acceptedHead"],
                                    "expectedGraphDigest": context["graphDigest"], "subject": subject,
                                    "plan": result["plan"]}, HEART)
    except ValueError as error:
        raise GateError(409, "plan_build_refused", str(error),
                        "Stavba plánu jde jen v pracovním prostoru domény (ne main); po změně plátna ji spusťte znovu.")
    return {**result, "proposal": {"id": created["id"], "reused": False}}
