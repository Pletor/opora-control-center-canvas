"""Kola karty: uzavřená v1 → čistá v2 podle nového zadání (`docs/navrh-schranka-zadani.md`, „Kola karty“).

Stav uzlu `round = {number, openedAt, by, reason}` nese číslo aktuálního kola (chybí = kolo 1).
Mění ho jen `open_round` (cesta `POST /api/desktop-v3/card-round`, jen člověk); obecný zápis
stavu ho nemění (`guard_state_write`).

Otevření kola N+1 zamrazí kolo N do append-only tabulky `card_rounds` (schéma `opora.card-round/1`):
zadání kola (cíl, text karty, doslovné revize fragmentů schránky), pipeline s předávkami, bloky,
důkazy, commity, nálezy kritiků, chyby, Podněty, předávky na vazbách, prostor agenta a odkazy na
výsledky agentů. Záznam se nikdy nepřepisuje: obnova verze plátna smí jen přidat novou revizi
(i prázdnou), stará zůstává. Karta v kole N+1 začíná načisto: pipeline k nasměrování, bloky
otevřené, fáze na začátku (`discover`), důkazy pending, uzavření zrušené, jen otevřené Podněty, prázdný prostor agenta a odkazy
na fragmenty v aktuální revizi. Rozhodnutí kola se nepřebírají (rozhodnutí 2026-10-09: „nové zadání
potřebuje nové postupy a možnosti“): porty bloků bez volby `status`/`reason` a kritéria nezaškrtnutá;
v1 je drží v zamrazeném záznamu a `previousRounds` je ukazuje jako kontext. Rozhodnutí karty
(`state.decisions`) zůstávají; node-brief je odvozeně označí `fromRound` (bez změny modelu); jejich doslovný text se zamrazí do záznamu (`nextBrief`), takže
se agentovi zadání kola nezmění, ani když se schránka dál vyvíjí.
"""

import copy
import json

from backend.canvas.activity_log import require_human
from backend.canvas.canvas_service import now
from backend.canvas.graph import encode, valid_id
from backend.editor.agent_memory.desktop_v3_state import PHASES

SCHEMA = "opora.card-round/1"
ROUND_KEYS = {"number", "openedAt", "by", "reason"}
OPEN_KEYS = {"project", "workspace", "nodeId", "expectedRevision", "reason"}
MAX_REASON = 2000
MAX_ROUNDS = 200
NOTE_PREVIEW = 600
NOTE_SHORT = 280


def _fail(message):
    raise ValueError("Neplatné kolo karty: " + message)


def validate_round(value, node_id=""):
    """Tvar `nodes[].round`; kolo 1 se neukládá (chybějící klíč)."""
    if not isinstance(value, dict) or set(value) != ROUND_KEYS:
        _fail(f"round[{node_id}] má pole number, openedAt, by, reason.")
    if type(value["number"]) is not int or not 2 <= value["number"] <= MAX_ROUNDS:
        _fail(f"číslo kola musí být celé číslo 2 až {MAX_ROUNDS}.")
    for key, limit in (("openedAt", 40), ("by", 120), ("reason", MAX_REASON)):
        if not isinstance(value[key], str) or "\0" in value[key] or len(value[key]) > limit:
            _fail(f"{key} kola musí být text do {limit} znaků.")
    return value


def round_number(node_state):
    return (node_state or {}).get("round", {}).get("number", 1)


def guard_state_write(actor, previous_state, state):
    """Číslo kola mění jen operace otevření kola (server, `actor == "system"`)."""
    if actor == "system":
        return
    before = previous_state.get("nodes", {})
    for node_id, node in state.get("nodes", {}).items():
        if node.get("round") == before.get(node_id, {}).get("round"):
            continue
        message = "Nové kolo karty otevírá jen člověk tlačítkem „Otevřít v2 podle nového zadání“ (POST /api/desktop-v3/card-round)."
        require_human(actor, message)
        raise ValueError(message)


# ---- čtení ----------------------------------------------------------------------------------


def _rows(db, project, workspace, node_id):
    """Poslední revize každého kola karty, {kolo: (revize, záznam)}; prázdný záznam = skryté obnovou."""
    latest = {}
    for row in db.execute("SELECT round,revision,record FROM card_rounds WHERE project_id=? AND workspace_id=?"
                          " AND node_id=? ORDER BY round,revision", (project, workspace, node_id)):
        latest[row["round"]] = (row["revision"], json.loads(row["record"]))
    return latest


def frozen_rounds(db, project, workspace, node_id, current):
    """Zamrazené záznamy kol 1 … current-1 (jen neprázdné), seřazené."""
    rows = _rows(db, project, workspace, node_id)
    return [rows[number][1] for number in sorted(rows) if number < current and rows[number][1]]


def frozen_fragments(db, project, workspace, refs):
    """Doslovný text fragmentů v revizi odkazu; revize schránky se nepřepisují, takže je to kopie kola."""
    items = []
    for ref in refs or []:
        row = db.execute("SELECT title,kind,text FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=?"
                         " AND fragment_id=? AND revision=?", (project, workspace, ref["fragmentId"], ref["revision"])).fetchone()
        items.append({"fragmentId": ref["fragmentId"], "revision": ref["revision"], "available": row is not None,
                      **({"title": row["title"], "kind": row["kind"], "text": row["text"]} if row else {})})
    return items


def _results_since(db, project, workspace, node_id, after):
    return [(row["sequence"], json.loads(row["record"])) for row in db.execute(
        "SELECT sequence,record FROM agent_result_records WHERE project_id=? AND workspace_id=? AND node_id=?"
        " AND sequence>? ORDER BY sequence", (project, workspace, node_id, after))]


def _result_link(record):
    output = record.get("output") or {}
    done = output.get("done") or {}
    return {"id": record["id"], "agent": record.get("agent", ""), "createdAt": record.get("createdAt", ""),
            "contextVersion": record.get("contextVersion"), "doneProposed": bool(done.get("proposed")),
            "note": str(done.get("note", ""))[:NOTE_PREVIEW],
            "stages": [{"id": item.get("id"), "status": item.get("status")} for item in output.get("stages") or []],
            "touched": list(output.get("touched") or [])}


# ---- zamrazení a čistá karta ----------------------------------------------------------------


def freeze(canvas, db, project, workspace, graph, state, node_id, number, at):
    """Úplný záznam kola `number` z uloženého stavu karty, výsledků agentů a revizí schránky."""
    node = state["nodes"][node_id]
    graph_node = next(item for item in graph["nodes"] if item["id"] == node_id)
    previous = frozen_rounds(db, project, workspace, node_id, number)
    after = previous[-1].get("resultsUntil", 0) if previous else 0
    results = _results_since(db, project, workspace, node_id, after)
    stages = (node.get("stages") or {}).get("items", [])
    evidence = node.get("evidence")
    outgoing = [edge["id"] for edge in graph["edges"] if edge["source"] == node_id]
    handoffs = {edge_id: state.get("edges", {})[edge_id] for edge_id in outgoing if edge_id in state.get("edges", {})}
    from backend.editor.agent_memory.agent_workspace import AgentWorkspace
    space = AgentWorkspace(canvas).current(project, workspace, node_id)["workspace"]
    fields = canvas.specs.read((project, workspace, node_id))["fields"]
    text = canvas.texts.read((project, workspace, node_id))
    opened = node.get("round") or {"openedAt": "", "by": "", "reason": ""}
    touched = sorted({path for _, record in results for path in (record.get("output") or {}).get("touched") or []})
    return {
        "schema": SCHEMA, "nodeId": node_id, "round": number,
        "openedAt": opened["openedAt"], "openedBy": opened["by"], "openReason": opened["reason"],
        "closedAt": node.get("done", {}).get("at", ""), "frozenAt": at, "frozenBy": "human",
        "brief": {"goal": fields, "text": text["text"], "textRevision": text["revision"],
                  "fragments": frozen_fragments(db, project, workspace, node.get("fragmentRefs"))},
        "phase": node.get("phase", PHASES[0]),
        "done": copy.deepcopy(node.get("done")),
        "pipeline": copy.deepcopy(node.get("stages")),
        "blocks": copy.deepcopy(node.get("blocks", [])),
        "criteria": copy.deepcopy(node.get("criteria", [])),
        "evidence": copy.deepcopy(evidence),
        "scenarioRun": copy.deepcopy(node.get("scenarioRun")),
        "ideas": copy.deepcopy(node.get("ideas", [])),
        "fragmentRefs": copy.deepcopy(node.get("fragmentRefs", [])),
        "criticFindings": [{key: item.get(key, "") for key in ("id", "kind", "lens", "title", "status", "note", "doneBy")}
                           for item in stages if item.get("kind") in ("review", "critic")],
        "errors": {
            "failedStages": [{key: item.get(key, "") for key in ("id", "kind", "lens", "title", "note")}
                             for item in stages if item.get("status") == "failed"],
            "agentFailures": space.get("failures", ""), "agentFixes": space.get("fixes", ""),
            "handoffErrors": [{"edgeId": edge_id, "errors": report["errors"]} for edge_id, report in handoffs.items()
                              if report.get("errors", "").strip()],
        },
        "commits": {"realization": copy.deepcopy(graph_node.get("realization")),
                    "merge": copy.deepcopy((evidence or {}).get("merge")),
                    "checksRun": copy.deepcopy((evidence or {}).get("checksRun", [])), "touched": touched},
        "handoffs": copy.deepcopy(handoffs),
        "agentWorkspace": copy.deepcopy(space),
        "decisions": [copy.deepcopy(item) for item in state.get("decisions", []) if item.get("nodeId") == node_id],
        "agentResults": [_result_link(record) for _, record in results],
        "resultsUntil": results[-1][0] if results else after,
    }


def pending_evidence():
    proof = {"status": "pending", "url": "", "note": ""}
    return {"tests": dict(proof), "review": dict(proof), "merge": dict(proof), "checksRun": []}


def fresh_node(node, refs, number, reason, at):
    """Karta v kole `number`: stejné zadání a struktura, ale bez stop předchozí práce."""
    fresh = copy.deepcopy(node)
    for key in ("stages", "scenarioRun"):
        fresh.pop(key, None)
    fresh["phase"] = PHASES[0]
    fresh["evidence"] = pending_evidence()
    fresh["done"] = {"confirmed": False, "at": "", "by": "human", "note": f"Kolo {number} otevřeno: {reason}".strip()[:4000]}
    for block in fresh.get("blocks", []):
        block["state"]["status"] = "open"
        block["state"].pop("note", None)
        for port in block.get("ports", []):
            port.pop("status", None)
            port.pop("reason", None)
    for criterion in fresh.get("criteria", []):
        criterion["checked"] = False
    if "ideas" in fresh:
        fresh["ideas"] = [item for item in fresh["ideas"] if item["status"] == "open"]
    if "fragmentRefs" in fresh:
        fresh["fragmentRefs"] = refs
    fresh["round"] = {"number": number, "openedAt": at, "by": "human", "reason": reason}
    return fresh


def _current_refs(db, project, workspace, refs):
    """Odkazy na poslední revizi živého fragmentu; smazaný fragment si drží původní revizi."""
    from backend.editor.brief_vault.brief_vault_model import latest_rows
    rows = latest_rows(db, project, workspace, [ref["fragmentId"] for ref in refs or []]) if refs else {}
    return [{"fragmentId": ref["fragmentId"],
             "revision": rows[ref["fragmentId"]]["revision"]
             if ref["fragmentId"] in rows and not rows[ref["fragmentId"]]["deleted"] else ref["revision"]}
            for ref in refs or []]


def open_round(store, payload, actor):
    """Člověk otevře uzavřenou kartu jako nové kolo; agent 403, neznámý původce 428."""
    require_human(actor, "Nové kolo karty otevírá jen člověk v UI.")
    if not isinstance(payload, dict) or set(payload) != OPEN_KEYS:
        raise ValueError("Otevření kola vyžaduje project, workspace, nodeId, expectedRevision a reason.")
    project, workspace, node_id, reason = (payload[key] for key in ("project", "workspace", "nodeId", "reason"))
    if not valid_id(node_id):
        raise ValueError("Neplatný identifikátor uzlu.")
    if not isinstance(reason, str) or "\0" in reason or len(reason) > MAX_REASON:
        raise ValueError(f"Důvod nového kola musí být text do {MAX_REASON} znaků.")
    reason = reason.strip() or "nové zadání"
    canvas = store.canvas
    with canvas.graph_lock, canvas.lock:
        view = canvas.view(project, workspace)
        if view["readOnly"]:
            raise ValueError("Main je pouze pro čtení; kolo karty se otevírá v pracovním prostoru.")
        if not any(item["id"] == node_id and item["kind"] in ("node", "sector") for item in view["graph"]["nodes"]):
            raise ValueError("Karta v tomto pracovním prostoru neexistuje.")
        stored = store.current(project, workspace)
        if stored["revision"] != payload["expectedRevision"]:
            raise ValueError("Stav se změnil v jiném okně (revize nesouhlasí). Obnovte jej.")
        node = stored["state"]["nodes"].get(node_id)
        if not node or not node.get("done", {}).get("confirmed"):
            raise ValueError("Nové kolo lze otevřít jen u karty, kterou člověk uzavřel.")
        number = round_number(node)
        if number >= MAX_ROUNDS:
            raise ValueError(f"Karta má nejvýše {MAX_ROUNDS} kol.")
        db = canvas.db_for(project)
        if _rows(db, project, workspace, node_id).get(number, (0, {}))[1]:
            raise ValueError(f"Kolo {number} je už zamrazené; historie kola se nepřepisuje.")
        at = now()
        record = freeze(canvas, db, project, workspace, view["graph"], stored["state"], node_id, number, at)
        refs = _current_refs(db, project, workspace, node.get("fragmentRefs"))
        record["nextBrief"] = {"round": number + 1, "fragments": frozen_fragments(db, project, workspace, refs)}
        state = copy.deepcopy(stored["state"])
        state["nodes"][node_id] = fresh_node(node, refs, number + 1, reason, at)

        def after_write(transaction):
            revision = _rows(transaction, project, workspace, node_id).get(number, (0, {}))[0] + 1
            transaction.execute("INSERT INTO card_rounds VALUES(?,?,?,?,?,?,?)",
                                (project, workspace, node_id, number, revision, encode(record), at))
            from backend.editor.agent_memory.agent_workspace import SECTIONS
            space = transaction.execute("SELECT MAX(revision) AS revision FROM agent_workspace_revisions"
                                        " WHERE project_id=? AND workspace_id=? AND node_id=?",
                                        (project, workspace, node_id)).fetchone()
            if space["revision"]:
                transaction.execute("INSERT INTO agent_workspace_revisions VALUES(?,?,?,?,?,?,?)",
                                    (project, workspace, node_id, space["revision"] + 1,
                                     json.dumps(dict.fromkeys(SECTIONS, ""), ensure_ascii=False), "human", at))

        saved = store.save({"project": project, "workspace": workspace, "expectedRevision": payload["expectedRevision"],
                            "state": state}, after_write=after_write, actor="system")
        return {**saved, "round": number + 1, "frozen": number}


# ---- podklady pro node-brief a UI -----------------------------------------------------------


def _short(text):
    """Zkrácená poznámka pro `previousRounds`; plný text je v `detail` (GET card-rounds)."""
    text = str(text or "")
    return text if len(text) <= NOTE_SHORT else text[:NOTE_SHORT - 1].rstrip() + "…"


def _summary(record, project, workspace):
    """Kompaktní shrnutí kola: poznámka etapy jen jednou a zkrácená, nálezy a chyby na ni odkazují `stageId`."""
    pipeline = record.get("pipeline") or {}
    evidence = record.get("evidence") or {}
    errors = record.get("errors") or {}
    return {
        "round": record["round"], "openedAt": record["openedAt"], "closedAt": record["closedAt"],
        "openReason": _short(record["openReason"]), "closeNote": _short((record.get("done") or {}).get("note", "")),
        "pipeline": {"profile": pipeline.get("profile"),
                     "stages": [{"id": item.get("id", ""), **{key: item.get(key, "") for key in ("kind", "lens", "title", "status", "doneBy")},
                                 "note": _short(item.get("note", ""))}
                                for item in pipeline.get("items", [])]},
        "blocks": [{"number": item["number"], "title": item["title"], "status": item["state"]["status"],
                    "note": _short(item["state"].get("note", "")),
                    "portDecisions": [{key: port[key] for key in ("label", "status", "reason")}
                                      for port in item.get("ports", []) if "status" in port]}
                   for item in record.get("blocks", [])],
        "criteria": [{key: item[key] for key in ("text", "checked")} for item in record.get("criteria", [])],
        "decisions": [{key: item.get(key, "") for key in ("id", "text", "by", "createdAt")} for item in record.get("decisions", [])],
        "decided": decided_lines(record),
        "evidence": {key: {"status": evidence[key]["status"], "url": evidence[key]["url"]}
                     for key in ("tests", "review", "merge") if key in evidence},
        "criticFindings": [{"stageId": item.get("id", ""), "lens": item.get("lens", ""), "status": item.get("status", "")}
                           for item in record.get("criticFindings", [])],
        "errors": {"failedStageIds": [item.get("id", "") for item in errors.get("failedStages", [])],
                   "agentFailures": _short(errors.get("agentFailures", "")), "agentFixes": _short(errors.get("agentFixes", "")),
                   "handoffErrors": [{"edgeId": item["edgeId"], "errors": _short(item["errors"])}
                                     for item in errors.get("handoffErrors", [])]},
        "commits": record.get("commits", {}),
        "ideas": {"open": [item["text"] for item in record.get("ideas", []) if item["status"] == "open"],
                  "done": [item["text"] for item in record.get("ideas", []) if item["status"] == "done"]},
        "handoff": _short(record.get("agentWorkspace", {}).get("handoff", "")),
        "agentResults": [{key: item[key] for key in ("id", "agent", "createdAt", "doneProposed")}
                         for item in record.get("agentResults", [])],
        "notes": f"poznámky zkráceny na {NOTE_SHORT} znaků a uvedeny jen jednou (pipeline.stages[].note); "
                 "criticFindings a errors.failedStageIds odkazují na pipeline.stages[].id; plné texty v detail",
        "detail": f"/api/desktop-v3/card-rounds?project={project}&workspace={workspace}&nodeId={record['nodeId']}&round={record['round']}",
    }


def decided_lines(record):
    """„rozhodnutí v1: …“ – volby portů, splněná kritéria a rozhodnutí karty kola jako čitelný kontext."""
    prefix = f"rozhodnutí v{record['round']}: "
    lines = [f"{prefix}port „{port['label']}“ bloku {block['number']} = {port['status']} ({port['reason']})"
             for block in record.get("blocks", []) for port in block.get("ports", []) if "status" in port]
    lines += [f"{prefix}kritérium splněno: {item['text']}" for item in record.get("criteria", []) if item.get("checked")]
    lines += [f"{prefix}{item['text']}" for item in record.get("decisions", [])]
    return lines


def mark_decisions(decisions, previous_rounds):
    """Rozhodnutí karty vzniklá v dřívějším kole dostanou `fromRound` (nejstarší kolo, kde jsou zamrazená)."""
    origin = {}
    for summary in previous_rounds:
        for item in summary.get("decisions", []):
            origin.setdefault(item["id"], summary["round"])
    return [{**item, "fromRound": origin[item["id"]]} if item.get("id") in origin else item for item in decisions]


def brief_sections(db, project, workspace, node_id, node_state):
    """`rounds` (aktuální kolo a jeho doslovné zadání) a `previousRounds` (shrnutí každého kola)."""
    current = round_number(node_state)
    records = frozen_rounds(db, project, workspace, node_id, current)
    opened = (node_state or {}).get("round") or {"openedAt": "", "by": "", "reason": ""}
    last = records[-1] if records and records[-1]["round"] == current - 1 else None
    if last and "nextBrief" in last:
        fragments, source = last["nextBrief"]["fragments"], "frozen at round opening"
    else:
        fragments, source = frozen_fragments(db, project, workspace, (node_state or {}).get("fragmentRefs")), \
            "brief vault revisions referenced by the card"
    rounds = {"current": current, "openedAt": opened["openedAt"], "openedBy": opened["by"], "reason": opened["reason"],
              "brief": {"fragments": fragments, "source": source},
              "history": [record["round"] for record in records],
              "policy": "rounds.brief is the verbatim assignment of this round and does not change when the brief vault "
                        "changes later; fragments.items show the latest vault text; a new round is opened only by a human; "
                        "port choices and checked criteria of earlier rounds are not carried over (previousRounds[].decided "
                        "is context only, decide them again); the card phase restarts at discover; context.decisions[].fromRound marks card decisions from an earlier round"}
    return rounds, [_summary(record, project, workspace) for record in records]


def read_rounds(store, project, workspace, node_id, round_=None):
    """Historie kol pro UI a detail z node-brief: úplné zamrazené záznamy jen ke čtení."""
    from backend.editor.agent_packet.desktop_v3_packets import redact_deep
    if not valid_id(node_id) or (round_ is not None and (type(round_) is not int or round_ < 1)):
        raise ValueError("Neplatný dotaz na kola karty.")
    canvas = store.canvas
    with canvas.graph_lock, canvas.lock:
        view = canvas.view(project, workspace)
        if not any(item["id"] == node_id for item in view["graph"]["nodes"]):
            raise ValueError("Karta v tomto pracovním prostoru neexistuje.")
        node_state = {} if view["readOnly"] else store.current(project, workspace)["state"]["nodes"].get(node_id, {})
        current = round_number(node_state)
        records = frozen_rounds(canvas.db_for(project), project, workspace, node_id, current)
    if round_ is not None:
        records = [record for record in records if record["round"] == round_]
        if not records:
            raise ValueError(f"Kolo {round_} karty není zamrazené.")
    return {"nodeId": node_id, "current": current, "round": (node_state or {}).get("round"),
            "rounds": redact_deep(records)}


def validate_record(record, node_id, number):
    """Záznam kola ve verzi plátna: prázdný (skryté kolo) nebo úplný záznam téhož kola karty."""
    if not isinstance(record, dict) or (record and (record.get("schema") != SCHEMA or record.get("nodeId") != node_id or record.get("round") != number)):
        raise ValueError("Neplatné kolo karty v uložené verzi.")
