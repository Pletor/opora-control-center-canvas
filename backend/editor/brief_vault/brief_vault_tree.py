"""Odvozené čtení schránky: strom, stav fragmentu, pokrytí podstromu a odkazy z karet.

Nic se tu nepersistuje. `inserted` = některá karta nese `fragmentRefs` na fragment;
`changedSinceInsert` = otisk názvu a textu v odkazu karty (`contentHash`) se liší od fragmentu; starší odkaz
bez otisku: karta vznikla z revize starší, než je poslední změna TEXTU (`text_revisions`). Zápis brány ani revize
jen s metadaty (propose-mvp, stage) kartě zadání nemění (docs/schranka-neurony.md §9 bod 6).
Pokrytí počítá listy druhu `brief` (research a question jsou poznámky k fragmentu, ne kus zadání).
Strom se skládá bez rekurze a vnoření končí na `MAX_DEPTH` (hlubší větev = počet `hidden`).
`effectiveDiscipline` = disciplína nejbližšího předka včetně sebe (`effective_disciplines`); filtr
(`tree_of(discipline=…)`) ponechá fragmenty dané disciplíny a jejich cestu ke kořeni, aby strom zůstal souvislý.
`effectiveTrack` je odvozený alias do K5, pak smazat (kreslení → `ux`, jinak `logic`, nezařazené → null).
Brány cyklu (`gates` jen booleany + `predictionError`, `gateStep`, `gatesStale`) skládá `brief_vault_gate_rules`.
"""

from backend.editor.brief_vault.brief_vault_details import details_summary
from backend.editor.brief_vault.brief_vault_disciplines import track_from_discipline
from backend.editor.brief_vault.brief_vault_gate_rules import detail, gate_state, summary
from backend.editor.brief_vault.brief_vault_model import (
    MAX_DEPTH,
    effective_disciplines,
    public,
    ref_changed,
)

STATUSES = ("changed", "inserted", "research", "mvp", "proposed", "saved")


def refs_by_fragment(state):
    result = {}
    for node_id, node in (state or {}).get("nodes", {}).items():
        for ref in node.get("fragmentRefs", []):
            item = {"nodeId": node_id, "revision": ref["revision"]}
            if ref.get("contentHash"):
                item["contentHash"] = ref["contentHash"]
            result.setdefault(ref["fragmentId"], []).append(item)
    return result


def ideas_by_fragment(state):
    result = {}
    for node_id, node in (state or {}).get("nodes", {}).items():
        for idea in node.get("ideas", []):
            if idea.get("fragmentId"):
                result.setdefault(idea["fragmentId"], []).append(
                    {"nodeId": node_id, "ideaId": idea["id"], "text": idea["text"], "status": idea["status"]})
    return result


def _children(rows):
    result = {}
    for row in rows.values():
        if not row["deleted"] and row["parent_id"] is not None:
            result.setdefault(row["parent_id"], []).append(row)
    for items in result.values():
        items.sort(key=lambda row: (row["ord"], row["fragment_id"]))
    return result


def _research_open(child, details):
    research = details.get(child["fragment_id"], {}).get("research")
    return child["kind"] == "research" and child["stage"] != "ready" and not (research and research["status"] == "done")


def legacy_pairs(state):
    """(fragmentId, revize) starších odkazů karet bez `contentHash` (pro `legacy_hashes`)."""
    return {(ref["fragmentId"], ref["revision"]) for node in (state or {}).get("nodes", {}).values()
            for ref in node.get("fragmentRefs", []) if not ref.get("contentHash")}


def status_of(row, children, refs, text_revision=None, details=None, legacy=None):
    cards = refs.get(row["fragment_id"], [])
    latest_text = text_revision if text_revision is not None else row["revision"]
    if cards and any(ref_changed(ref, row, latest_text, legacy) for ref in cards):
        return "changed"
    if cards:
        return "inserted"
    if row["stage"] == "research" or any(_research_open(child, details or {}) for child in children.get(row["fragment_id"], [])):
        return "research"
    return {"yes": "mvp", "proposed": "proposed"}.get(row["mvp"], "saved")


def effective_fields(disciplines, fragment_id):
    """`effectiveDiscipline` a dočasný `effectiveTrack` (alias do K5, pak smazat) jednoho fragmentu."""
    discipline = disciplines.get(fragment_id)
    return {"effectiveDiscipline": discipline, "effectiveTrack": track_from_discipline(discipline)}


def live_ids(rows):
    """Živé fragmenty: nesmazané a se všemi předky nesmazanými (bez rekurze, cyklus = neživý)."""
    result = {}
    for start in rows:
        chain, cursor, seen, alive = [], start, set(), True
        while cursor is not None:
            if cursor in result:
                alive = result[cursor]
                break
            if cursor not in rows or cursor in seen or rows[cursor]["deleted"]:
                alive = False
                break
            seen.add(cursor)
            chain.append(cursor)
            cursor = rows[cursor]["parent_id"]
        for fragment_id in chain:
            result[fragment_id] = alive
    return {fragment_id for fragment_id, alive in result.items() if alive}


def discipline_counts(rows):
    """Počet živých fragmentů druhu `brief` podle platné disciplíny: ({id: počet}, nezařazené)."""
    disciplines, counts, unassigned = effective_disciplines(rows), {}, 0
    for fragment_id in live_ids(rows):
        if rows[fragment_id]["kind"] != "brief":
            continue
        found = disciplines.get(fragment_id)
        if found is None:
            unassigned += 1
        else:
            counts[found] = counts.get(found, 0) + 1
    return counts, unassigned


def _discipline_kept(rows, disciplines, wanted):
    """Fragmenty platné disciplíny `wanted` a všichni jejich předci (cesta ke kořeni), nad úplnými řádky bez rekurze."""
    kept = set()
    for fragment_id, row in rows.items():
        if row["deleted"] or disciplines.get(fragment_id) != wanted:
            continue
        cursor = fragment_id
        while cursor in rows and cursor not in kept:
            kept.add(cursor)
            cursor = rows[cursor]["parent_id"]
    return kept


def tree_of(rows, state, scope=None, text_revisions=None, details=None, feedback=None, discipline=None, legacy=None):
    """Stromy kořenů rozsahu; `details` = {id: fields}, `feedback` = {id: počet}.

    `discipline` (id | `none` = nezařazené) ponechá fragmenty dané platné disciplíny a jejich cestu ke kořeni.
    Filtr i pokrytí běží nad úplnými řádky (i pod stropem hloubky); strop ořízne až výstup. Uzel jiné disciplíny,
    který zůstal jen jako cesta, sečte jen ponechané podfragmenty; vlastní list se počítá jen ve své disciplíně.
    """
    refs, ideas, children = refs_by_fragment(state), ideas_by_fragment(state), _children(rows)
    text_revisions, details, feedback = text_revisions or {}, details or {}, feedback or {}
    disciplines = effective_disciplines(rows)
    wanted = None if discipline == "none" else discipline
    kept = _discipline_kept(rows, disciplines, wanted) if discipline is not None else None
    shown = children if kept is None else {
        parent: [kid for kid in kids if kid["fragment_id"] in kept] for parent, kids in children.items() if parent in kept}

    def make(row, kids, depth):
        fragment_id = row["fragment_id"]
        cards = refs.get(fragment_id, [])
        text_revision = text_revisions.get(fragment_id, row["revision"])
        status = status_of(row, children, refs, text_revision, details, legacy)
        coverage: dict[str, int] = {key: 0 for key in ("leaves", "mvpInserted", *STATUSES)}
        briefs = [kid for kid in kids if kid["kind"] == "brief"]
        leaf = not any(kid["kind"] == "brief" for kid in children.get(fragment_id, []))
        if row["kind"] == "brief" and leaf and (kept is None or disciplines.get(fragment_id) == wanted):
            coverage["leaves"], coverage[status] = 1, 1
            coverage["mvpInserted"] = int(row["mvp"] == "yes" and bool(cards))
        for kid in briefs:
            for key, value in kid["coverage"].items():
                coverage[key] += value
        # Pod stropem hloubky už se nevnořuje (JSON i UI zůstanou mělké); počet zůstane vidět.
        hidden = sum(1 + kid["hidden"] for kid in kids) if depth >= MAX_DEPTH else 0
        return {**public(row), **effective_fields(disciplines, fragment_id),
                **summary(gate_state(row, disciplines.get(fragment_id))), "status": status, "inserted": bool(cards),
                "cards": cards, "textRevision": text_revision, "changedSinceInsert": status == "changed",
                "ideas": sum(1 for idea in ideas.get(fragment_id, []) if idea["status"] == "open"),
                "feedback": feedback.get(fragment_id, 0), **details_summary(details.get(fragment_id, {})),
                "coverage": coverage, "hidden": hidden, "children": [] if depth >= MAX_DEPTH else kids}

    roots = [row for row in rows.values() if row["parent_id"] is None and not row["deleted"]
             and (scope is None or row["scope_node_id"] == scope) and (kept is None or row["fragment_id"] in kept)]
    result = []
    for root in sorted(roots, key=lambda row: (row["scope_node_id"] or "", row["ord"], row["fragment_id"])):
        built, seen = {}, set()
        stack = [(root, 1, False)]
        while stack:
            row, depth, ready = stack.pop()
            fragment_id = row["fragment_id"]
            if ready:
                kids = [built.pop(kid["fragment_id"]) for kid in shown.get(fragment_id, []) if kid["fragment_id"] in built]
                built[fragment_id] = make(row, kids, depth)
                continue
            if fragment_id in seen:
                continue
            seen.add(fragment_id)
            stack.append((row, depth, True))
            stack.extend((kid, depth + 1, False) for kid in reversed(shown.get(fragment_id, [])))
        result.append(built[root["fragment_id"]])
    return result


def path_of(rows, fragment_id):
    path, cursor, seen = [], fragment_id, set()
    while cursor in rows and cursor not in seen:
        seen.add(cursor)
        path.append({"id": cursor, "title": rows[cursor]["title"]})
        cursor = rows[cursor]["parent_id"]
    return list(reversed(path))


def fragment_links(rows, state, fragment_id, text_revisions=None, details=None, legacy=None):
    refs, children = refs_by_fragment(state), _children(rows)
    text_revisions, details = text_revisions or {}, details or {}
    disciplines = effective_disciplines(rows)
    root = path_of(rows, fragment_id)[0]["id"]
    latest_text = text_revisions.get(fragment_id, rows[fragment_id]["revision"])
    gates = gate_state(rows[fragment_id], disciplines.get(fragment_id))

    def status(row):
        return status_of(row, children, refs, text_revisions.get(row["fragment_id"]), details, legacy)

    return {"path": path_of(rows, fragment_id), "scopeNodeId": rows[root]["scope_node_id"],
            "status": status(rows[fragment_id]), "textRevision": latest_text,
            **effective_fields(disciplines, fragment_id), **summary(gates), "gateDetail": detail(gates),
            "children": [{**public(row), **effective_fields(disciplines, row["fragment_id"]), "status": status(row), **details_summary(details.get(row["fragment_id"], {}))}
                         for row in children.get(fragment_id, [])],
            "cards": [{**ref, "changedSinceInsert": ref_changed(ref, rows[fragment_id], latest_text, legacy)}
                      for ref in refs.get(fragment_id, [])],
            "ideas": ideas_by_fragment(state).get(fragment_id, [])}
