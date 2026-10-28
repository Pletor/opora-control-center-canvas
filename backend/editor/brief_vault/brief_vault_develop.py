"""Operace vývoje zadání ve schránce: výzkum, otázka K upřesnění, odpověď, zpětná vazba člověka,
odkazy na rozhodnutí a fragment z Podnětu (docs/navrh-schranka-zadani.md, „Rozšíření“).

Každý handler dostane `_Write` z `brief_vault.py` (transakce, autor, čas) a vrací část odpovědi.
Změna podrobností (verdikt, důkazy, odpověď) je nová revize fragmentu s poznámkou a beze změny
textu, takže kartám „zadání se změnilo“ nevyvolá (`text_revisions`).
"""

import copy
import json

from backend.canvas.activity_log import require_authority
from backend.canvas.graph import valid_id
from backend.editor.brief_vault.brief_vault_details import (
    MAX_QUESTION,
    RESEARCH_KEYS,
    add_feedback,
    empty_research,
    validate_decisions,
    validate_question,
    validate_research,
    write_details,
)
from backend.editor.brief_vault.brief_vault_model import (
    MAX_TEXT,
    MAX_TITLE,
    discipline_of,
    fail,
    public,
    text_of,
)

OPS = {
    "research-update": ({"fragmentId", "expectedRevision", "note"}, RESEARCH_KEYS),
    "question": ({"fragmentId", "title"}, {"text", "askedFor", "proposal", "note"}),
    "answer": ({"fragmentId", "expectedRevision", "answer"}, {"note"}),
    "feedback": ({"fragmentId", "verdict"}, {"text"}),
    "link-decisions": ({"fragmentId", "decisionIds"}, {"note"}),
    "from-idea": ({"nodeId", "ideaId"}, {"parentId", "scopeNodeId", "title", "note", "discipline"}),
}
HUMAN_OPS = {"feedback": "Zpětnou vazbu k výzkumu dává člověk; agent ji čte v balíčku research-brief."}


def _details(w, fragment_id):
    return w.details(fragment_id)


def research(w, payload, node_ids):
    """Založí dítě `kind: research` s otázkou a verdiktem `unverified` (stav zadáno)."""
    parent = w.latest(payload["fragmentId"])
    w.check_depth(parent["fragment_id"])
    title = text_of(payload["title"], MAX_TITLE, "title", allow_empty=False)
    question = text_of(payload.get("question", title), MAX_QUESTION, "question", allow_empty=False)
    fields = {"research": validate_research({**empty_research(question), "status": payload.get("status", "assigned")})}
    row = w.new(parent=parent["fragment_id"], scope=None, kind="research", stage="research", title=title,
                text=text_of(payload["text"], MAX_TEXT, "text"), note=payload.get("note") or "Výzkum k fragmentu.")
    write_details(w.db, w.project, w.workspace, row["fragment_id"], fields, w.at)
    return {"fragment": public(row), "details": fields}


def research_update(w, payload, node_ids):
    """Výsledek nebo průběh výzkumu: verdikt, jistota, postup, důkazy, stav, kolo."""
    row = w.checked(payload)
    if row["kind"] != "research":
        fail("research-update mění jen fragment druhu research.")
    fields = _details(w, row["fragment_id"])
    current = fields.get("research") or empty_research(row["title"])
    changes = {key: payload[key] for key in RESEARCH_KEYS if key in payload}
    updated = validate_research({**current, **changes})
    if updated == current:
        fail("research-update nic nemění; pošlete změněný verdikt, důkazy, postup nebo stav.")
    revised = w.revise(row, payload["note"])
    fields = {**fields, "research": updated}
    write_details(w.db, w.project, w.workspace, row["fragment_id"], fields, w.at)
    return {"fragment": public(revised), "details": fields}


def question(w, payload, node_ids):
    """Otázka K upřesnění jako dítě `kind: question`; odpověď je pak revize nebo výzkum."""
    parent = w.latest(payload["fragmentId"])
    w.check_depth(parent["fragment_id"])
    title = text_of(payload["title"], MAX_TITLE, "title", allow_empty=False)
    fields = {"question": validate_question({"askedFor": payload.get("askedFor", "human"), "proposal": payload.get("proposal", ""),
                                             "answer": "", "answeredBy": "", "answeredAt": ""})}
    row = w.new(parent=parent["fragment_id"], scope=None, kind="question", stage="draft", title=title,
                text=text_of(payload.get("text", ""), MAX_TEXT, "text"), note=payload.get("note") or "Otázka k upřesnění.")
    write_details(w.db, w.project, w.workspace, row["fragment_id"], fields, w.at)
    return {"fragment": public(row), "details": fields}


def answer(w, payload, node_ids):
    """Odpověď na otázku; otázku pro člověka zodpoví jen člověk (403 / 428)."""
    row = w.checked(payload)
    if row["kind"] != "question":
        fail("answer odpovídá jen na fragment druhu question.")
    fields = _details(w, row["fragment_id"])
    asked = fields.get("question") or {"askedFor": "human", "proposal": "", "answer": "", "answeredBy": "", "answeredAt": ""}
    if asked["askedFor"] == "human":
        require_authority(w.actor, "Otázku pro člověka zodpoví jen člověk.")
    text = text_of(payload["answer"], 8000, "answer", allow_empty=False)
    fields = {**fields, "question": validate_question({**asked, "answer": text, "answeredBy": w.by, "answeredAt": w.at})}
    revised = w.revise(row, payload.get("note") or "Zodpovězeno.", stage="ready")
    write_details(w.db, w.project, w.workspace, row["fragment_id"], fields, w.at)
    return {"fragment": public(revised), "details": fields}


def feedback(w, payload, node_ids):
    """Souhlas / nesouhlas / komentář člověka k fragmentu (append-only); vstup dalšího kola výzkumu."""
    row = w.latest(payload["fragmentId"])
    item = add_feedback(w.db, w.project, w.workspace, row, payload["verdict"], payload.get("text", ""), w.by, w.actor, w.at)
    return {"feedback": item}


def link_decisions(w, payload, node_ids):
    """Fragment odkazuje na rozhodnutí plátna (id); text rozhodnutí zůstává na kartě."""
    row = w.latest(payload["fragmentId"])
    ids = validate_decisions(payload["decisionIds"])
    known = {item["id"] for item in w.state()["state"]["decisions"]}
    missing = [item for item in ids if item not in known]
    if missing:
        fail("rozhodnutí " + ", ".join(missing) + " na plátně neexistuje.")
    fields = _details(w, row["fragment_id"])
    if fields.get("decisions", []) == ids:
        fail("odkazy na rozhodnutí se nemění.")
    fields = {**{key: value for key, value in fields.items() if key != "decisions"}, **({"decisions": ids} if ids else {})}
    write_details(w.db, w.project, w.workspace, row["fragment_id"], fields, w.at)
    return {"fragment": public(row), "details": fields}


def from_idea(w, payload, node_ids):
    """Z Podnětu karty vznikne fragment a Podnět dostane `fragmentId` (obojí v jedné transakci)."""
    node_id, idea_id = payload["nodeId"], payload["ideaId"]
    if not isinstance(node_id, str) or not valid_id(node_id) or not isinstance(idea_id, str) or not valid_id(idea_id):
        fail("nodeId a ideaId musí být platné identifikátory.")
    current = w.state()
    state = copy.deepcopy(current["state"])
    idea = next((item for item in state["nodes"].get(node_id, {}).get("ideas", []) if item["id"] == idea_id), None)
    if idea is None:
        fail(f"karta {node_id} nemá Podnět {idea_id}.")
    if idea.get("fragmentId"):
        fail(f"Podnět už je navázaný na fragment {idea['fragmentId']}.")
    if "parentId" in payload and "scopeNodeId" in payload:
        fail("from-idea očekává nejvýš jedno z parentId a scopeNodeId.")
    parent, scope = None, payload.get("scopeNodeId", node_id)
    if "parentId" in payload:
        parent, scope = w.latest(payload["parentId"])["fragment_id"], None
        w.check_depth(parent)
    elif scope != "" and scope not in node_ids:
        fail("scopeNodeId musí být \"\" (plátno) nebo id existující karty či sektoru.")
    title = text_of(payload.get("title") or idea["text"].strip().split("\n")[0][:MAX_TITLE], MAX_TITLE, "title", allow_empty=False)
    # Nový kořen nese disciplínu vždy (jako create); dítě ji smí vynechat a dědí.
    discipline = discipline_of(payload.get("discipline"), allow_null=parent is not None)
    row = w.new(parent=parent, scope=scope, title=title, text=idea["text"],
                note=payload.get("note") or f"Z Podnětu karty {node_id}.", discipline=discipline)
    idea["fragmentId"] = row["fragment_id"]
    from backend.editor.agent_memory.desktop_v3_state import validate_state
    validate_state(state)
    from backend.canvas.opora_execution_guard import state_write
    graph = w.state_store.canvas.view(w.project, w.workspace)["graph"]
    state_write(w.db, w.project, w.workspace, current["state"], state, graph, w.actor)
    w.db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                 (w.project, w.workspace, current["revision"] + 1, json.dumps(state, ensure_ascii=False), w.at))
    return {"fragment": public(row), "idea": {"nodeId": node_id, "ideaId": idea_id, "fragmentId": row["fragment_id"]},
            "stateRevision": current["revision"] + 1}


HANDLERS = {"research-update": research_update, "question": question, "answer": answer, "feedback": feedback,
            "link-decisions": link_decisions, "from-idea": from_idea}
