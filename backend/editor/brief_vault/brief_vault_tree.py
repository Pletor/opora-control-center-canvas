"""Odvozené čtení schránky: strom, stav fragmentu, pokrytí podstromu a odkazy z karet.

Nic se tu nepersistuje. `inserted` = některá karta nese `fragmentRefs` na fragment;
`changedSinceInsert` = karta vznikla ze starší revize, než je poslední. Pokrytí počítá listy
druhu `brief` (research je poznámka k fragmentu, ne kus zadání).
"""

from backend.editor.brief_vault.brief_vault_model import public

STATUSES = ("changed", "inserted", "research", "mvp", "proposed", "saved")


def refs_by_fragment(state):
    result = {}
    for node_id, node in (state or {}).get("nodes", {}).items():
        for ref in node.get("fragmentRefs", []):
            result.setdefault(ref["fragmentId"], []).append({"nodeId": node_id, "revision": ref["revision"]})
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


def status_of(row, children, refs):
    cards = refs.get(row["fragment_id"], [])
    if cards and any(ref["revision"] < row["revision"] for ref in cards):
        return "changed"
    if cards:
        return "inserted"
    if row["stage"] == "research" or any(child["kind"] == "research" and child["stage"] != "ready"
                                         for child in children.get(row["fragment_id"], [])):
        return "research"
    return {"yes": "mvp", "proposed": "proposed"}.get(row["mvp"], "saved")


def tree_of(rows, state, scope=None):
    refs, ideas, children = refs_by_fragment(state), ideas_by_fragment(state), _children(rows)

    def node(row):
        kids = [node(child) for child in children.get(row["fragment_id"], [])]
        cards = refs.get(row["fragment_id"], [])
        status = status_of(row, children, refs)
        briefs = [kid for kid in kids if kid["kind"] == "brief"]
        coverage: dict[str, int] = {key: 0 for key in ("leaves", "mvpInserted", *STATUSES)}
        if row["kind"] == "brief" and not briefs:
            coverage["leaves"], coverage[status] = 1, 1
            coverage["mvpInserted"] = int(row["mvp"] == "yes" and bool(cards))
        for kid in briefs:
            for key, value in kid["coverage"].items():
                coverage[key] += value
        return {**public(row), "status": status, "inserted": bool(cards), "cards": cards,
                "changedSinceInsert": status == "changed",
                "ideas": sum(1 for idea in ideas.get(row["fragment_id"], []) if idea["status"] == "open"),
                "coverage": coverage, "children": kids}

    roots = [row for row in rows.values() if row["parent_id"] is None and not row["deleted"]
             and (scope is None or row["scope_node_id"] == scope)]
    return [node(row) for row in sorted(roots, key=lambda row: (row["scope_node_id"] or "", row["ord"], row["fragment_id"]))]


def path_of(rows, fragment_id):
    path, cursor, seen = [], fragment_id, set()
    while cursor in rows and cursor not in seen:
        seen.add(cursor)
        path.append({"id": cursor, "title": rows[cursor]["title"]})
        cursor = rows[cursor]["parent_id"]
    return list(reversed(path))


def fragment_links(rows, state, fragment_id):
    refs, children = refs_by_fragment(state), _children(rows)
    root = path_of(rows, fragment_id)[0]["id"]
    latest = rows[fragment_id]["revision"]
    return {"path": path_of(rows, fragment_id), "scopeNodeId": rows[root]["scope_node_id"],
            "status": status_of(rows[fragment_id], children, refs),
            "children": [{**public(row), "status": status_of(row, children, refs)} for row in children.get(fragment_id, [])],
            "cards": [{**ref, "changedSinceInsert": ref["revision"] < latest} for ref in refs.get(fragment_id, [])],
            "ideas": ideas_by_fragment(state).get(fragment_id, [])}
