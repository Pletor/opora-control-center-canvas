"""Vývoj zadání u fragmentu: výzkum proveditelnosti, otázka K upřesnění, odkazy na rozhodnutí
a zpětná vazba člověka (docs/navrh-schranka-zadani.md, „Rozšíření“ a „Schránka jako pop-up“).

Podrobnosti fragmentu (`brief_fragment_details`) jsou JSON s vlastní řadou revizí (jen přibývají),
aby doslovný text a jeho revize (`brief_fragment_revisions`) zůstaly beze změny tvaru. Pole:

- `research`: {question, verdict, confidence, approach, evidence[{url, title, quote, accessedAt}], status, round};
  jiný verdikt než `unverified` vyžaduje aspoň jeden důkaz s URL (jinak 409).
- `question`: {askedFor, proposal, answer, answeredBy, answeredAt} u fragmentu druhu `question`.
- `decisions`: [id rozhodnutí plátna]; text rozhodnutí se nekopíruje, čte se ze stavu plátna.
- `duel`: stav duelu u fragmentu druhu `duel`, `vision`: body trajektorie u fragmentu druhu `vision`
  (docs/schranka-duel.md, tvar hlídá `brief_vault_duel_shape`).

Zpětná vazba (`brief_fragment_feedback`) je append-only: souhlas / nesouhlas / komentář, autor a čas.
"""

import json
import uuid
from urllib.parse import urlsplit

from backend.canvas.graph import valid_id
from backend.editor.brief_vault.brief_vault_duel_shape import summary as duel_summary
from backend.editor.brief_vault.brief_vault_duel_shape import validate_duel, validate_vision
from backend.editor.brief_vault.brief_vault_model import fail, text_of

VERDICTS = ("feasible", "dead_end", "unrealistic", "unverified")
CONFIDENCE = ("", "low", "medium", "high")
RESEARCH_STATUSES = ("assigned", "running", "done")
ASKED_FOR = ("human", "agent")
FEEDBACK = ("agree", "disagree", "comment")
RESEARCH_KEYS = {"question", "verdict", "confidence", "approach", "evidence", "status", "round"}
QUESTION_KEYS = {"askedFor", "proposal", "answer", "answeredBy", "answeredAt"}
EVIDENCE_KEYS = {"url", "title", "quote", "accessedAt"}
MAX_EVIDENCE, MAX_DECISIONS, MAX_FEEDBACK_READ = 30, 50, 500
MAX_QUESTION, MAX_APPROACH, MAX_QUOTE, MAX_URL = 1000, 8000, 2000, 2048


def empty_research(question):
    return {"question": question, "verdict": "unverified", "confidence": "", "approach": "", "evidence": [],
            "status": "assigned", "round": 1}


def _url(value):
    text_of(value, MAX_URL, "evidence.url", allow_empty=False)
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or any(ch.isspace() for ch in value):
        fail("evidence.url musí být adresa http(s) bez mezer.")
    return value


def validate_evidence(items):
    if not isinstance(items, list) or len(items) > MAX_EVIDENCE:
        fail(f"evidence musí být pole nejvýše {MAX_EVIDENCE} důkazů.")
    for item in items:
        if not isinstance(item, dict) or set(item) != EVIDENCE_KEYS:
            fail("důkaz je {url, title, quote, accessedAt}.")
        _url(item["url"])
        text_of(item["title"], 300, "evidence.title", allow_empty=False)
        text_of(item["quote"], MAX_QUOTE, "evidence.quote")
        text_of(item["accessedAt"], 40, "evidence.accessedAt", allow_empty=False)
    return items


def validate_research(value):
    if not isinstance(value, dict) or set(value) != RESEARCH_KEYS:
        fail("research má pole " + ", ".join(sorted(RESEARCH_KEYS)) + ".")
    text_of(value["question"], MAX_QUESTION, "question", allow_empty=False)
    text_of(value["approach"], MAX_APPROACH, "approach")
    for key, allowed in (("verdict", VERDICTS), ("confidence", CONFIDENCE), ("status", RESEARCH_STATUSES)):
        if value[key] not in allowed:
            fail(f"{key} musí být jedna z hodnot {', '.join(repr(item) for item in allowed)}.")
    validate_evidence(value["evidence"])
    if type(value["round"]) is not int or not 1 <= value["round"] <= 1000:
        fail("round musí být celé číslo 1 až 1000.")
    if value["verdict"] != "unverified" and not value["evidence"]:
        fail(f"verdikt {value['verdict']} potřebuje aspoň jeden důkaz s URL; bez důkazu zůstává unverified.")
    return value


def validate_question(value):
    if not isinstance(value, dict) or set(value) != QUESTION_KEYS:
        fail("question má pole " + ", ".join(sorted(QUESTION_KEYS)) + ".")
    if value["askedFor"] not in ASKED_FOR:
        fail("askedFor musí být human nebo agent.")
    text_of(value["proposal"], 4000, "proposal")
    text_of(value["answer"], MAX_APPROACH, "answer")
    text_of(value["answeredBy"], 120, "answeredBy")
    text_of(value["answeredAt"], 40, "answeredAt")
    return value


def validate_decisions(value):
    if not isinstance(value, list) or len(value) > MAX_DECISIONS or len(set(map(str, value))) != len(value):
        fail(f"decisionIds musí být pole nejvýše {MAX_DECISIONS} různých id.")
    if any(not isinstance(item, str) or not valid_id(item) for item in value):
        fail("decisionIds obsahuje neplatný identifikátor.")
    return value


def validate_details(fields):
    """Celé podrobnosti jedné revize; používá zápis i obnova verze plátna."""
    if not isinstance(fields, dict) or not set(fields) <= {"research", "question", "decisions", "duel", "vision"}:
        fail("podrobnosti fragmentu mají jen research, question, decisions, duel a vision.")
    if "research" in fields:
        validate_research(fields["research"])
    if "question" in fields:
        validate_question(fields["question"])
    if "decisions" in fields:
        validate_decisions(fields["decisions"])
    if "duel" in fields:
        validate_duel(fields["duel"])
    if "vision" in fields:
        validate_vision(fields["vision"])
    return fields


def latest_details(db, project, workspace, fragment_ids=None):
    """Poslední podrobnosti fragmentů prostoru, {id: {revision, fields}}."""
    query = ("SELECT fragment_id, revision, fields FROM brief_fragment_details AS t WHERE project_id=? AND workspace_id=?"
             " AND revision=(SELECT MAX(revision) FROM brief_fragment_details WHERE project_id=t.project_id"
             " AND workspace_id=t.workspace_id AND fragment_id=t.fragment_id)")
    params = [project, workspace]
    if fragment_ids is not None:
        ids = sorted(set(fragment_ids))
        if not ids:
            return {}
        query += f" AND fragment_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    return {row["fragment_id"]: {"revision": row["revision"], "fields": json.loads(row["fields"])}
            for row in db.execute(query, params)}


def write_details(db, project, workspace, fragment_id, fields, at):
    validate_details(fields)
    current = latest_details(db, project, workspace, [fragment_id]).get(fragment_id)
    db.execute("INSERT INTO brief_fragment_details(project_id,workspace_id,fragment_id,revision,fields,saved_at) VALUES(?,?,?,?,?,?)",
               (project, workspace, fragment_id, (current["revision"] if current else 0) + 1,
                json.dumps(fields, ensure_ascii=False), at))
    return fields


def details_summary(fields):
    """Malý výtah podrobností do stromu (bez důkazů a dlouhých textů)."""
    summary = {}
    research = fields.get("research")
    if research:
        summary["research"] = {"question": research["question"], "verdict": research["verdict"],
                               "confidence": research["confidence"], "status": research["status"],
                               "round": research["round"], "evidence": len(research["evidence"])}
    question = fields.get("question")
    if question:
        summary["question"] = {"askedFor": question["askedFor"], "answered": bool(question["answer"].strip())}
    if fields.get("decisions"):
        summary["decisions"] = list(fields["decisions"])
    if fields.get("duel"):
        summary["duel"] = duel_summary(fields["duel"])
    vision = fields.get("vision")
    if vision is not None:
        points = vision["points"]
        summary["vision"] = {"points": len(points), "last": points[-1]["score"] if points else None}
    return summary


def add_feedback(db, project, workspace, fragment, verdict, text, by, actor, at):
    if verdict not in FEEDBACK:
        fail("verdict zpětné vazby je agree, disagree nebo comment.")
    text_of(text, 4000, "text", allow_empty=verdict != "comment")
    item = {"id": uuid.uuid4().hex, "fragmentId": fragment["fragment_id"], "fragmentRevision": fragment["revision"],
            "verdict": verdict, "text": text, "by": by, "actor": actor, "at": at}
    db.execute("INSERT INTO brief_fragment_feedback(project_id,workspace_id,id,fragment_id,fragment_revision,verdict,text,by,actor,at)"
               " VALUES(?,?,?,?,?,?,?,?,?,?)",
               (project, workspace, item["id"], item["fragmentId"], item["fragmentRevision"], verdict, text, by, actor, at))
    return item


def feedback_rows(db, project, workspace, fragment_ids=None, limit=MAX_FEEDBACK_READ):
    """Zpětná vazba prostoru (nejnovější první), volitelně jen k vybraným fragmentům."""
    query = "SELECT * FROM brief_fragment_feedback WHERE project_id=? AND workspace_id=?"
    params: list = [project, workspace]
    if fragment_ids is not None:
        ids = sorted(set(fragment_ids))
        if not ids:
            return []
        query += f" AND fragment_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    query += " ORDER BY at DESC, id LIMIT ?"
    params.append(limit)
    return [{"id": row["id"], "fragmentId": row["fragment_id"], "fragmentRevision": row["fragment_revision"],
             "verdict": row["verdict"], "text": row["text"], "by": row["by"], "actor": row["actor"], "at": row["at"]}
            for row in db.execute(query, params)]


def decisions_of(state, ids):
    """Rozhodnutí plátna podle id (živý text ze stavu); chybějící = `available: false`."""
    by_id = {item["id"]: item for item in (state or {}).get("decisions", [])}
    return [{"id": item_id, "available": True, "text": by_id[item_id]["text"], "nodeId": by_id[item_id]["nodeId"],
             "pinned": by_id[item_id]["pinned"]} if item_id in by_id else {"id": item_id, "available": False}
            for item_id in ids]
