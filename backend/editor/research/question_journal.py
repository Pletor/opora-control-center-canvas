"""Create-only projection of durable Pletor question events into research.

The JSON question log is the retry source. Reads reconcile missing deterministic cards/edges;
no heart-authored research revision is overwritten. Source events remain full in card content.
"""
import hashlib
import json
from datetime import datetime
from itertools import pairwise

from backend.agi_pletor import questions
from backend.editor.research import model


def identity(question_id, kind, index=0, prefix="rc_"):
    raw = json.dumps([question_id, kind, index], ensure_ascii=False)
    return prefix + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _events(question):
    yield "question", 0, {"text": question["text"], "at": question["askedAt"]}
    for kind, field in (("refinement", "refinements"), ("answer", "answers")):
        for index, event in enumerate(question.get(field, [])):
            yield kind, index, event
    if question.get("status") == "closed":
        yield "close", 0, {"text": question.get("closedNote", ""), "at": question.get("closedAt", "")}


def _card(question, kind, index, event):
    labels = {"question": "Otázka Pletora", "refinement": "Upřesnění otázky",
              "answer": "Odpověď srdce", "close": "Uzavření otázky"}
    label = labels[kind]
    refs = {name: [] for name in model.REFS}
    refs["questionIds"] = [question["id"]]
    refs["fragmentIds"] = list(dict.fromkeys(ref for ref in event.get("refs", [])
                                            if isinstance(ref, str) and ref.startswith("vf_") and model.valid_id(ref)))
    # Exact source payload, including unknown/reason/refs/by, is retained independently of the header.
    content = json.dumps({"questionId": question["id"], "event": kind, "index": index,
                          "sourceWorkspace": question["workspace"], "record": event}, ensure_ascii=False, indent=2)
    if kind == "close":
        content += "\n\nUzavření této otázky samo o sobě nedokládá schválení plánu ani implementace."
    text = event.get("text", "")
    return {"op": "card", "id": identity(question["id"], kind, index), "expectedRevision": 0,
            "kind": "option" if kind == "answer" else "decision" if kind == "close" else "question",
            "title": label, "summary": label + (": " + text[:300] if text else "."),
            "topicPath": ["Nezařazené otázky", question["id"]], "content": content,
            "status": "resolved" if kind == "close" else "open",
            "verification": {"status": "unverified", "method": "Záznam rozhovoru; nejde o ověření faktů.", "at": ""},
            "sources": [{"ref": "opora-question:" + question["id"] + ":" + kind + ":" + str(index),
                         "platform": "opora", "quote": text, "title": label,
                         "accessedAt": event.get("at") or question["askedAt"]}], "refs": refs}


def _edge(question_id, source, target, kind, reason):
    return {"op": "edge", "id": identity(question_id, source, target, "re_"), "expectedRevision": 0,
            "fromId": source, "toId": target, "relation": kind, "reason": reason,
            "resolved": "", "missing": "", "evidenceIds": []}


def _chronology(question):
    """Link recorded events only when all timestamps give an unambiguous total order.

    Equal-second timestamps, missing offsets and legacy arbitrary strings cannot establish
    interleaving across the separate answer/refinement arrays; retain source records only.
    These edges describe time, not inferred causality or approval.
    """
    ordered = []
    try:
        for kind, index, event in _events(question):
            at = datetime.fromisoformat(event["at"])
            if at.utcoffset() is None:
                return []
            ordered.append((at, identity(question["id"], kind, index)))
    except (ValueError, TypeError, KeyError, AttributeError):
        return []
    if len({at for at, _ in ordered}) != len(ordered):
        return []
    ordered.sort()
    return [_edge(question["id"], before, after, "elaborates",
                  "Další zaznamenaná událost této otázky podle časových údajů: "
                  + before_at.isoformat() + " → " + after_at.isoformat()
                  + ". Pořadí samo nedokládá příčinu změny ani schválení plánu.")
            for (before_at, before), (after_at, after) in pairwise(ordered)]


def reconcile(canvas, project, workspace):
    """Retry missing projections; failures surface and leave the durable source for the next read."""
    from backend.editor.research import service

    pending = [q for q in questions.listing(canvas, project)
               if q.get("researchWorkspace", q.get("workspace")) == workspace]
    if not pending:
        return
    with canvas.graph_lock_for(project):
        with canvas.reading(project):
            db = canvas.db_for(project)
            cards = service._latest(db, project, workspace, "card")
            edges = service._latest(db, project, workspace, "edge")
        for question in pending:
            root = identity(question["id"], "question")
            proposed_cards, proposed_edges = [], []
            event_ids = set()
            for kind, index, event in _events(question):
                card = _card(question, kind, index, event)
                event_ids.add(card["id"])
                if card["id"] not in cards:
                    proposed_cards.append(card)
                if kind != "question":
                    reason = {"refinement": "Upřesnění rozvíjí původní otázku; úplné zadání je v kartě.",
                              "answer": "Srdce odpovídá na tuto otázku; podklady a nejistota jsou v plném záznamu.",
                              "close": "Člověk uzavřel tuto otázku s uvedenou poznámkou; nejde o automatické schválení plánu."}[kind]
                    if kind == "close" and event.get("text", "").strip():
                        reason += "\n" + event["text"]
                    # Closing a conversation can defer an unresolved question. Only a research
                    # author can assert resolution with explicit resolved/missing context.
                    proposed_edges.append(_edge(question["id"], card["id"], root, "elaborates", reason))
                for ref in event.get("refs", []):
                    if isinstance(ref, str) and ref in cards and ref != card["id"]:
                        proposed_edges.append(_edge(question["id"], ref, card["id"], "elaborates",
                                                    "Odpověď výslovně odkazuje na tento podklad; odkaz sám nepotvrzuje jeho platnost."))
            proposed_edges.extend(_chronology(question))
            for card in cards.values():
                if card["id"] not in event_ids and question["id"] in card["refs"]["questionIds"]:
                    proposed_edges.append(_edge(question["id"], card["id"], root, "elaborates",
                                                "Podklad je výslovně přiřazen k této otázce pomocí questionIds."))
            # Create only. Archived or edited projections remain untouched, including semantic edges.
            unique_edges = {edge["id"]: edge for edge in proposed_edges if edge["id"] not in edges}
            operations = proposed_cards + list(unique_edges.values())
            for offset in range(0, len(operations), 200):
                chunk = operations[offset:offset + 200]
                digest = hashlib.sha256(service._json(chunk).encode()).hexdigest()
                result = service.apply(canvas, {"project": project, "workspace": workspace,
                                               "key": "question-journal:" + digest, "operations": chunk},
                                       "agent", "question-journal")
                cards.update({card["id"]: card for card in result["cards"]})
                edges.update({edge["id"]: edge for edge in result["edges"]})
