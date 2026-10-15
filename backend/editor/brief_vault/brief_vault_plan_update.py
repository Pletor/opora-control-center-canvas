"""Karta, kterou fragment už má: žádné duplicitní karty mezi koly (docs/schranka-neurony.md §4, §11; K11).

Živá karta fragmentu U ve vrstvě plánu = uzel `node` na plátně uvnitř vrstvy (vrstva `None` = celé plátno), jehož
**první** odkaz `fragmentRefs` ve stavu Desktop v3 míří na U (karta vznikla za U z dřívějšího `placed`; další odkazy
jsou podfragmenty). Takovou kartu plán nezakládá znovu: místo položky `nodes` vrátí položku `extend` dávky
`/api/canvas-plan`, tedy existující cestu zápisu specu, bloků a odkazů se stávající validací (`node_specs`,
`validate_state`, `resolve_plan_refs`): `spec` (goal, acceptance z nového `synthesized`) s revizí specu, bloky
přepočítané stejně jako u nové karty (`replaceBlocks`), `fragmentRef` (přepíše se na poslední revizi a otisk obsahu)
a `expectedRevision` = revize stavu; `layer` (je-li) přepíše `card.layer` karty, bez něj vrstva zůstává. Víc takových karet ve vrstvě = 409 (`duplicate-card`); uzavřená karta = 409
(`card-closed`), protože uzavřenou kartu dávka měnit nesmí: nejdřív ji otevřete.

Kontejner plánu (K12): `expectedRevision` je revize **celého** stavu Desktop v3, kterou mění i souběžné smyčky jiných
disciplín. Otisk plánu ji proto nenese (`fingerprint`) a `placed` ji před zápisem nastaví na aktuální revizi
(`with_revisions`). Co plán čte a mění, hlídá `scope_digest`: sha256 uzlů grafu a jejich stavu pro vrstvu plánu,
použitou oblast a sektor a existující kartu fragmentu. Změna mimo tyto uzly `placed` neshodí.
"""

import copy
import hashlib
import json

from backend.editor.brief_vault.brief_vault_model import blocked
from backend.editor.brief_vault.brief_vault_plan_cards import approach_steps


def _inside(by_id, node, layer):
    cursor, seen = node.get("parentId"), set()
    while cursor is not None and cursor not in seen:
        if cursor == layer:
            return True
        seen.add(cursor)
        cursor = (by_id.get(cursor) or {}).get("parentId")
    return False


def live_cards(graph, state, layer):
    """{fragmentId: [id karty]} karet vrstvy podle jejich prvního odkazu do schránky."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    result = {}
    for node in graph["nodes"]:
        refs = (state.get("nodes", {}).get(node["id"]) or {}).get("fragmentRefs") or []
        if node["kind"] != "node" or not refs or (layer is not None and not _inside(by_id, node, layer)):
            continue
        result.setdefault(refs[0]["fragmentId"], []).append(node["id"])
    return result


def existing_card(cards, row, state):
    """Id karty, kterou plán aktualizuje, nebo None; víc karet nebo uzavřená karta = 409 s výčtem."""
    ids = cards.get(row["fragment_id"], [])
    if len(ids) > 1:
        blocked(f"fragment „{row['title']}“ má ve vrstvě víc karet ({', '.join(ids)}); nechte jednu, pak plánujte znovu.",
                [{"id": row["fragment_id"], "title": row["title"], "reason": "duplicate-card"}])
    if not ids:
        return None
    if ((state.get("nodes", {}).get(ids[0]) or {}).get("done") or {}).get("confirmed"):
        blocked(f"karta {ids[0]} fragmentu „{row['title']}“ je uzavřená; nejdřív ji otevřete, pak plánujte znovu.",
                [{"id": row["fragment_id"], "title": row["title"], "reason": "card-closed"}])
    return ids[0]


def research_steps(rows, fragment_id, details):
    """Kroky `approach` posledního hotového výzkumu fragmentu (`research` se `status: done`, poslední podle `ord`)."""
    done = [row for row in rows.values() if row["parent_id"] == fragment_id and row["kind"] == "research"
            and not row["deleted"]
            and ((details.get(row["fragment_id"]) or {}).get("research") or {}).get("status") == "done"]
    if not done:
        return []
    last = max(done, key=lambda row: (row["ord"], row["fragment_id"]))
    return approach_steps(details[last["fragment_id"]]["research"]["approach"])


def update_of(card, node_id, revision, spec_revision, layer=None):
    """Položka `extend` dávky, která existující kartu převede na tvar `card` (spec, bloky, odkazy).

    `layer` = vrstva ze `synthesized`; bez ní se vrstva existující karty nemění."""
    return {"node": "@" + node_id, "expectedRevision": revision,
            "spec": {"expectedRevision": spec_revision, "fields": card["spec"]},
            "fragmentRef": card["fragmentRef"], "blocks": card["blocks"], "replaceBlocks": True,
            **({"layer": layer} if layer else {})}


def fingerprint(plan):
    """Dávka bez revize celého stavu u položek `extend` (vstup otisku plánu); revize specu karty zůstává."""
    found = copy.deepcopy(plan)
    for item in found.get("extend") or []:
        item.pop("expectedRevision", None)
    return found


def with_revisions(plan, current):
    """Uložená dávka s `expectedRevision` položek `extend` z právě sestavené dávky `current` (stejný otisk)."""
    found = copy.deepcopy(plan)
    for item, fresh in zip(found.get("extend") or [], current.get("extend") or [], strict=True):
        item["expectedRevision"] = fresh["expectedRevision"]
    return found


def scope_digest(graph, state, node_ids):
    """sha256 uzlů grafu a jejich stavu Desktop v3, které plán čte nebo mění (chybějící uzel = None)."""
    by_id = {node["id"]: node for node in graph["nodes"]}
    nodes = state.get("nodes") or {}
    items = [[node_id, by_id.get(node_id), nodes.get(node_id)] for node_id in sorted(node_ids)]
    raw = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
