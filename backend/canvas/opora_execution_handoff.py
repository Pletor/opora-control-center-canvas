"""Předávka předchůdců v zadání: `assignment.handoff` (docs/oporahub-executions.md „Předávka v zadání“).

Při claimu se pro každou kartu, ze které vede vazba `next` do claimované karty, vezme poslední
přijatý výsledek (běh se sloučeným PR, jinak nejnovější ohlášený výsledek): souhrn, `stepResults`
s krátkým důkazem, kontroly, rozhodnutí, PR {number, state, mergeSha} a odkaz na review-lens.
Je-li karta v oblasti první (žádný předchůdce `next` ze stejné oblasti), přidají se zprávy toků
`flow`, které do oblasti vedou. Balíček je snímek: je součástí otisku zadání, ale běžící běh se
při změně předchůdce neodvolá (`pinned`). Strop a zkracování řeší `opora_execution_handoff_cap`.
"""
from backend.canvas import opora_execution_handoff_cap as cap
from backend.canvas import opora_review_lens as review_lens
from backend.canvas.areas import area_of
from backend.canvas.graph import digest
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_executions import Executions

ROOT = "/api/oporahub"
STATE = "/api/desktop-v3/state"
CARD_KINDS = ("node", "sector")
HISTORY = 20  # kolik posledních běhů předchůdce se prohlédne při hledání výsledku


def _tables(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _is_next(edge):
    return edge.get("port", "next") == "next"


def _accepted_result(runs, links, node):
    """(záznam, poslední výsledek, PR) nejnovějšího běhu s výsledkem; běh se sloučeným PR má přednost."""
    found = []
    for record in runs.history(node)[:HISTORY]:  # nejnovější první
        receipts = runs.receipts(record["executionId"])
        if receipts:
            found.append((record, receipts[-1], links.read(record["executionId"]) if links else None))
    merged = next((item for item in found if item[2] and item[2]["state"] == "merged"), None)
    return merged or (found[0] if found else None)


def _result(receipt):
    result = receipt.get("result") if isinstance(receipt.get("result"), dict) else {}
    checks = result.get("selfChecks") if isinstance(result.get("selfChecks"), dict) else {}
    return {"summary": result.get("summary"),
            "stepResults": [item for item in result.get("stepResults") or []
                            if isinstance(item, dict) and {"stepId", "status"} <= set(item)],
            "checks": [item for item in checks.get("checks") or [] if isinstance(item, dict)]}


def _decisions(receipt, state, node):
    """Rozhodnutí z výsledku (text nebo objekt s why/alternatives/evidence), pak rozhodnutí karty z plochy."""
    result = (receipt or {}).get("result") or {}
    own = [item for item in result.get("decisions") or [] if isinstance(item, (str, dict))]
    desk = [item for item in state.get("decisions") or [] if isinstance(item, dict) and item.get("nodeId") == node]
    desk.sort(key=lambda item: str(item.get("id", "")))
    desk.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
    return own + [{"text": item.get("text"), **({"agent": item["by"]} if isinstance(item.get("by"), str) else {})}
                  for item in desk]


def _pr(link):
    if not link:
        return None
    pr = {"number": link["number"], "state": link["state"],
          "url": f"https://github.com/{link['repository']}/pull/{link['number']}"}
    if link.get("merge_sha"):
        pr["mergeSha"] = link["merge_sha"]
    return pr


def _lens(db, tables, project, workspace, node):
    lens = {"endpoint": f"{ROOT}/review-lens?nodeId={node}", "stored": False}
    if "opora_review_lens" not in tables:
        return lens
    found = review_lens.for_node(db, project, workspace, node)
    if not found.get("lens"):
        return lens
    spec = found["lens"].get("spec") if isinstance(found["lens"].get("spec"), dict) else {}
    return {**lens, "stored": True, "title": spec.get("title"), "url": found["lens"].get("url"),
            "current": found.get("current")}


def _card(db, tables, scope, runs, links, state, node, edge):
    picked = _accepted_result(runs, links, node["id"]) if runs else None
    record, receipt, link = picked or (None, None, None)
    full = {"executions": f"{ROOT}/executions?nodeId={node['id']}", "lens": f"{ROOT}/review-lens?nodeId={node['id']}"}
    if record:
        full["results"] = f"{ROOT}/executions/{record['executionId']}/results"
        if link:
            full["pullRequest"] = f"{ROOT}/executions/{record['executionId']}/pull-request"
    report = (state.get("edges") or {}).get(edge["id"])
    decisions = _decisions(receipt, state, node["id"])
    if report or any(isinstance(item, dict) and item.get("nodeId") == node["id"] for item in state.get("decisions") or []):
        full["state"] = STATE  # zpráva na vazbě a rozhodnutí karty z plochy
    return {"cardId": node["id"], "title": node.get("name") or node["id"],
            "executionId": record and record["executionId"],
            "resultStatus": ("merged" if link and link["state"] == "merged" else "reported") if receipt else "none",
            "resultAt": receipt and receipt.get("createdAt"),
            "result": _result(receipt) if receipt else None, "decisions": decisions, "pr": _pr(link),
            "lens": _lens(db, tables, *scope, node["id"]), "edgeReport": report if isinstance(report, dict) else None,
            "full": full}


def area_flows(graph, state, by_id, target, predecessors):
    """Zprávy toků do oblasti karty, jen když je karta v oblasti první."""
    area = area_of(target, graph["nodes"])
    if area is None or any((area_of(by_id[item], graph["nodes"]) or {}).get("id") == area["id"] for item in predecessors):
        return []
    flows = []
    for edge in sorted((e for e in graph["edges"] if e.get("port") == "flow" and e["target"] == area["id"]),
                       key=lambda e: e["id"]):
        report = (state.get("edges") or {}).get(edge["id"])
        report = report if isinstance(report, dict) else {}
        source = by_id.get(edge["source"], {})
        flows.append({"edgeId": edge["id"], "fromArea": {"id": edge["source"], "title": source.get("name") or edge["source"]},
                      "handoff": report.get("handoff"), "summary": report.get("summary"),
                      "sentAt": report.get("sentAt") or report.get("updatedAt"), "full": {"state": STATE}})
    flows.sort(key=lambda item: str(item["sentAt"] or ""), reverse=True)  # stabilní: shoda zůstane podle id
    return flows


def handoff_for(canvas, db, project, workspace, node_id):
    """Deterministický balíček předávky pro claim karty `node_id` (nejvýš `cap.CAP_BYTES`)."""
    graph = canvas.view(project, workspace)["graph"]
    state = DesktopV3State(canvas).read(project, workspace)["state"]
    by_id = {item["id"]: item for item in graph["nodes"]}
    tables = _tables(db)
    runs = Executions(db, project, workspace) if "opora_executions" in tables else None
    links = ExecutionPullRequests(db, project, workspace) if "opora_execution_pull_requests" in tables else None
    edges = sorted((e for e in graph["edges"] if _is_next(e) and e["target"] == node_id
                    and by_id.get(e["source"], {}).get("kind") in CARD_KINDS), key=lambda e: (e["source"], e["id"]))
    seen, cards = set(), []
    for edge in edges:
        if edge["source"] not in seen:
            seen.add(edge["source"])
            cards.append(_card(db, tables, (project, workspace), runs, links, state, by_id[edge["source"]], edge))
    cards.sort(key=lambda item: str(item["resultAt"] or ""), reverse=True)  # nejnovější výsledek první
    flows = area_flows(graph, state, by_id, by_id[node_id], seen) if node_id in by_id else []
    params = {"method": "GET", "params": {"project": project, "workspace": workspace},
              "executions": f"{ROOT}/executions?nodeId={{id}}"}
    return cap.build(redact_deep(cards), redact_deep(flows), params)  # texty agentů bez tajemství


def attach(captured, pin, value):
    """Předávka patří do otisku zadání; u řídkého kontextu (v2) se přepočte i otisk v jeho pinu."""
    captured = {**captured, "handoff": value}
    if pin is not None:
        pin["assignmentDigest"] = digest(captured)
    return captured


def pinned(current, record):
    """Živé zadání se porovná se snímkem předávky z claimu: změna předchůdce běh neodvolá."""
    stored = record.get("assignment") or {}
    return {**current, "handoff": stored["handoff"]} if "handoff" in stored else current
