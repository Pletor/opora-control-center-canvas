"""Odkazy karet do schránky: `nodes[].fragmentRefs`, `fragmentRef` v canvas-plan, `ideas[].fragmentId`
a sekce `fragments` v node-brief.

Tvar hlídá `validate_refs` (čistá funkce pro `validate_state`). Existenci fragmentu téhož projektu
a prostoru hlídá `check_new_references` při uložení stavu a `resolve_plan_refs` v dávce plánu.
"""

from backend.canvas.graph import valid_id
from backend.editor.brief_vault.brief_vault_model import (
    effective_disciplines,
    latest_rows,
    text_revisions,
)
from backend.editor.brief_vault.brief_vault_tree import path_of

REF_KEYS = {"fragmentId", "revision"}
PLAN_REF_KEYS = (REF_KEYS, {"fragmentId"})
MAX_REFS = 50


def validate_refs(value, label="fragmentRefs"):
    """`[{fragmentId, revision}]`, nejvýše `MAX_REFS`, každý fragment jednou."""
    if not isinstance(value, list) or len(value) > MAX_REFS:
        raise ValueError(f"Neplatný stav Desktop v3: {label} musí být pole nejvýše {MAX_REFS} odkazů.")
    seen = set()
    for ref in value:
        if (not isinstance(ref, dict) or set(ref) != REF_KEYS or not valid_id(ref["fragmentId"])
                or type(ref["revision"]) is not int or ref["revision"] < 1 or ref["fragmentId"] in seen):
            raise ValueError(f"Neplatný stav Desktop v3: {label} má odkaz {{fragmentId, revision ≥ 1}} bez opakování.")
        seen.add(ref["fragmentId"])
    return value


def _check(rows, fragment_id, revision, label):
    row = rows.get(fragment_id)
    if row is None or row["deleted"]:
        raise ValueError(f"{label}: fragment {fragment_id} ve schránce tohoto prostoru neexistuje.")
    if revision is not None and revision > row["revision"]:
        raise ValueError(f"{label}: fragment {fragment_id} nemá revizi {revision}.")
    return row


def _referenced(state):
    refs = {(node_id, ref["fragmentId"], ref["revision"]) for node_id, node in state.get("nodes", {}).items()
            for ref in node.get("fragmentRefs", [])}
    ideas = {(node_id, idea["fragmentId"], None) for node_id, node in state.get("nodes", {}).items()
             for idea in node.get("ideas", []) if idea.get("fragmentId")}
    return refs | ideas


def check_new_references(db, project, workspace, previous, state):
    """Nově přidaný odkaz karty nebo Podnětu musí mířit na živý fragment téhož projektu a prostoru."""
    added = _referenced(state) - _referenced(previous)
    if not added:
        return
    rows = latest_rows(db, project, workspace, [fragment_id for _, fragment_id, _ in added])
    for node_id, fragment_id, revision in sorted(added, key=str):
        _check(rows, fragment_id, revision, f"karta {node_id}")


def resolve_plan_refs(db, project, workspace, built):
    """`fragmentRef` z dávky (objekt nebo pole) → `fragmentRefs` stavu karty; bez `revision` poslední."""
    if not built.fragment_refs:
        return
    wanted = {}
    for node_id, value in built.fragment_refs.items():
        label = built.labels.get(node_id, node_id)
        items = value if isinstance(value, list) else [value]
        if not items or len(items) > MAX_REFS:
            raise ValueError(f"{label}: fragmentRef musí být objekt nebo pole 1 až {MAX_REFS} odkazů.")
        for ref in items:
            if not isinstance(ref, dict) or set(ref) not in PLAN_REF_KEYS or not valid_id(ref.get("fragmentId")):
                raise ValueError(f"{label}: fragmentRef je {{fragmentId, revision?}}.")
            if "revision" in ref and (type(ref["revision"]) is not int or ref["revision"] < 1):
                raise ValueError(f"{label}: fragmentRef.revision musí být celé číslo ≥ 1.")
        wanted[node_id] = items
    rows = latest_rows(db, project, workspace, [ref["fragmentId"] for items in wanted.values() for ref in items])
    for node_id, items in wanted.items():
        label = built.labels.get(node_id, node_id)
        node = built.state["nodes"][node_id]
        refs = {ref["fragmentId"]: ref for ref in node.get("fragmentRefs", [])}
        for ref in items:
            row = _check(rows, ref["fragmentId"], ref.get("revision"), label)
            refs[ref["fragmentId"]] = {"fragmentId": ref["fragmentId"], "revision": ref.get("revision", row["revision"])}
        node["fragmentRefs"] = list(refs.values())
    built.state_changed = True


def brief_section(db, project, workspace, refs):
    """Doslovný text navázaných fragmentů (poslední revize) pro node-brief; nic se nekopíruje do karty."""
    refs = refs or []
    rows = latest_rows(db, project, workspace) if refs else {}
    texts = text_revisions(db, project, workspace, [ref["fragmentId"] for ref in refs]) if refs else {}
    disciplines = effective_disciplines(rows) if refs else {}
    items = []
    for ref in refs:
        row = rows.get(ref["fragmentId"])
        if row is None:
            items.append({"fragmentId": ref["fragmentId"], "insertedRevision": ref["revision"], "available": False})
            continue
        items.append({"fragmentId": ref["fragmentId"], "title": row["title"], "kind": row["kind"], "stage": row["stage"],
                      "effectiveDiscipline": disciplines.get(ref["fragmentId"]),
                      "path": [item["title"] for item in path_of(rows, ref["fragmentId"])],
                      "insertedRevision": ref["revision"], "revision": row["revision"],
                      "textRevision": texts.get(ref["fragmentId"], row["revision"]),
                      "changedSinceInsert": ref["revision"] < texts.get(ref["fragmentId"], row["revision"]),
                      "deleted": bool(row["deleted"]),
                      "available": True, "text": row["text"]})
    return {"items": items, "changed": sum(1 for item in items if item.get("changedSinceInsert")),
            "policy": "verbatim brief text from the brief vault (latest revision); changedSinceInsert = the TEXT changed "
                      "after the card was planned (metadata-only revisions do not count); read GET /api/brief-vault/fragment "
                      "for history and GET /api/brief-vault/research-brief for research"}
