"""Vazba kuličky na plán (docs/navrhy/2026-11-06-linie-rebrand.md §3, §7 bod 4 L7d): ověřená, ne prohlášená.

`resolve(service, project, ticket)` → `{state, planCardId, directionCardId, cardRevision, issued, text}`:
- `none` – ticket bez `machine.cardId` („bez plánu“, jediný stav, který to smí říct);
- `linked` – karta `kind == node` je v grafu prostoru ticketu; `cardRevision` = revize zadání karty
  (`node_spec_revisions`: cíl, omezení, podmínky dokončení, kroky – kritéria, ne prostý text karty);
- `card_missing` – `cardId` je, karta v grafu není; `source_unavailable` – graf nejde přečíst;
- `ambiguous` – víc kandidátů směru pro jednu kartu (`settle`: kuličky téže karty míří na různé stránky).
`directionCardId` = stránka (plátno 2), jejíž `page_intent` vlastní `machine.intent.workflowVersionId`
(`page_intents.owner_of`, jen týž projekt); bez záměru `None` a stav zůstává `linked`. Nic se neodvozuje z názvu.
"""
from backend.flow.page_intents import owner_of
from backend.flow.workflows import FlowNotFound

TEXT = {"none": "bez plánu", "card_missing": "karta plánu {card} v projektu chybí",
        "source_unavailable": "vazbu na plán teď neověřím, karty nejdou přečíst",
        "ambiguous": "karta plánu {card} má víc kandidátů směru"}


def cards(service, project, workspace):
    """`{id: uzel}` grafu prostoru (všechny druhy), nebo None, když graf nejde přečíst."""
    try:
        return {node["id"]: node for node in service.view(project, workspace)["graph"]["nodes"]}
    except (ValueError, KeyError, LookupError, OSError):
        return None


def revision(service, project, workspace, card_id):
    """Revize zadání karty, nebo None (karta nebo zdroj chybí)."""
    try:
        return service.node_spec(project, workspace, card_id)["revision"]
    except (ValueError, KeyError, LookupError, OSError):
        return None


def direction(service, project, ticket):
    version = (ticket["machine"].get("intent") or {}).get("workflowVersionId")
    if not version:
        return None
    try:
        with service.registry_lock:
            owner = owner_of(service.db, version)
    except (FlowNotFound, TypeError, KeyError):
        return None
    return owner[1] if owner and owner[0] == project else None


def text(link, card):
    """Věta pro Pletora a detail; „bez plánu“ jen u `none`."""
    if link["state"] == "linked":
        return f"plán {card} R{link['cardRevision']}"
    return TEXT[link["state"]].format(card=card)


def resolve(service, project, ticket, graph=None):
    """Stav vazby ticketu; `graph` = `cards()` prostoru ticketu přečtené volajícím jednou (board)."""
    card = ticket["machine"].get("cardId")
    issued = (ticket.get("work") or {}).get("issued")
    found = {"state": "none", "planCardId": None, "directionCardId": None, "cardRevision": None, "issued": issued}
    if card:
        graph = cards(service, project, ticket["workspaceId"]) if graph is None else graph
        if graph is None:
            found["state"] = "source_unavailable"
        elif (graph.get(card) or {}).get("kind") != "node":
            found["state"] = "card_missing"
        else:
            found |= {"state": "linked", "planCardId": card, "directionCardId": direction(service, project, ticket),
                      "cardRevision": revision(service, project, ticket["workspaceId"], card)}
    return {**found, "text": text(found, card)}


def settle(links):
    """Karta s kuličkami mířícími na různé směry → u všech `ambiguous` bez směru (seznam se mění na místě)."""
    seen = {}
    for link in links:
        if link["state"] == "linked" and link["directionCardId"]:
            seen.setdefault(link["planCardId"], set()).add(link["directionCardId"])
    for link in links:
        if link["state"] == "linked" and len(seen.get(link["planCardId"], ())) > 1:
            link |= {"state": "ambiguous", "directionCardId": None}
            link["text"] = text(link, link["planCardId"])
    return links


def issue(service, project, ticket, now):
    """Zmrazená reference při vydání práce: revizi čte server z karty, nikdy `machine.cardVersion` klienta."""
    card = ticket["machine"].get("cardId")
    return {"cardId": card, "cardRevision": revision(service, project, ticket["workspaceId"], card) if card else None,
            "at": now}


def diff(link):
    """Aktuální revize karty ≠ revize při vydání."""
    issued = link.get("issued") or {}
    return link["cardRevision"] is not None and issued.get("cardRevision") is not None \
        and link["cardRevision"] != issued["cardRevision"]
