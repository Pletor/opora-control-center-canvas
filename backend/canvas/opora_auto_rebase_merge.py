"""Pure three-way merge of one stale proposal against the accepted line (base/ours/theirs).

base = accepted value the proposal saw at its parent revision, ours = proposed value,
theirs = value at the current accepted head. Each field or item is decided by the Lean-proved
rule `opora_field_merge.merge_field` (tools/formal/lean/OporaHub/FieldMerge.lean); a merge is
`clean` when theirs is still the base (our value applies), `redundant` when the merged value is
already theirs (same change, or our side left it unchanged), otherwise a conflict. No model is
consulted; the same records always produce the same verdict."""
from copy import deepcopy

from backend.canvas.opora_field_merge import merge_field
from backend.canvas.opora_plan_steps import merge_steps

ABSENT = {"$absent": True}


def _value(mapping, key):
    return deepcopy(mapping[key]) if isinstance(mapping, dict) and key in mapping else ABSENT


def verdict(key, base, ours, theirs):
    """One item: `clean`, `redundant` or a conflict dict with all three sides."""
    merged, _ = merge_field(base, ours, theirs)
    if not merged:
        return {"key": key, "base": base, "ours": ours, "theirs": theirs}
    return "clean" if theirs == base else "redundant"


def summarize(results):
    conflicts = [item for item in results if isinstance(item, dict)]
    if conflicts:
        return "conflict", conflicts
    if results and all(item == "redundant" for item in results):
        return "redundant", []
    return "clean", []


def spec(proposal, accepted_documents):
    """Field-level merge of specification changes; returns (outcome, conflicts, merged changes)."""
    accepted = {item["nodeId"]: item for item in accepted_documents}
    results, merged = [], []
    for change in proposal["changes"]:
        node, base_doc = change["nodeId"], change["acceptedBefore"]
        theirs_doc = accepted.get(node)
        if theirs_doc is None or theirs_doc["ownerWorkspace"] != base_doc["ownerWorkspace"]:
            results.append({"key": f"spec:{node}", "base": base_doc, "ours": change["fields"],
                            "theirs": theirs_doc, "reason": "card_removed_or_moved"})
            continue
        fields, card = deepcopy(theirs_doc["fields"]), []
        for name in sorted(set(change["fields"]) | set(base_doc["fields"]) | set(theirs_doc["fields"])):
            base, ours = _value(base_doc["fields"], name), _value(change["fields"], name)
            theirs = _value(theirs_doc["fields"], name)
            if ours == base:
                continue
            if name == "steps":  # Plan steps merge per step id (docs/oporahub-plan-steps.md).
                outcomes, value = merge_steps(f"spec:{node}:steps", base, ours, theirs)
                card.extend(outcomes)
                if value is not None and (value or "steps" in fields):
                    fields["steps"] = value
                continue
            outcome = verdict(f"spec:{node}:{name}", base, ours, theirs)
            card.append(outcome)
            if outcome == "clean":
                if ours == ABSENT:
                    fields.pop(name, None)
                else:
                    fields[name] = ours
        results.extend(card)
        if card and fields != theirs_doc["fields"]:
            merged.append({"nodeId": node, "fields": fields})
    outcome, conflicts = summarize(results)
    return outcome, conflicts, merged


def content(proposal, accepted_entries):
    """Entry-level merge keyed by (kind, target, field); returns (outcome, conflicts, kept changes)."""
    accepted = {(item["kind"], item["target"], item["field"]): item for item in accepted_entries or []}
    base_content = {(item["kind"], item["target"], item["field"]): item for item in proposal["baseContent"]}
    results, kept = [], []
    for change in proposal["changes"]:
        key = (change["kind"], change["target"], change["field"])
        base_entry = change["acceptedBefore"] if change["acceptedBefore"] is not None else base_content.get(key)
        base = base_entry["value"] if base_entry else ABSENT
        theirs = accepted[key]["value"] if key in accepted else (base if accepted_entries is None else ABSENT)
        outcome = verdict("content:" + ":".join(key), base, change["value"], theirs)
        results.append(outcome)
        if outcome == "clean":
            kept.append({name: deepcopy(change[name]) for name in ("kind", "target", "field", "value")})
    outcome, conflicts = summarize(results)
    return outcome, conflicts, kept


def graph(proposal, accepted_graph):
    """Item/field-level merge of graph additions and v2 edits against the accepted graph."""
    current = {kind: {item["id"]: item for item in accepted_graph[kind]} for kind in ("nodes", "edges")}
    results = []
    if proposal["kind"] == "graph-changes":
        for kind in ("nodes", "edges"):
            for item in proposal["changes"][kind]:
                theirs_item = current[kind].get(item["id"])
                key = f"graph:{kind[:-1]}:{item['id']}"
                if item["operation"] == "add":
                    results.append(verdict(key, None, item["proposedAccepted"], theirs_item))
                elif item["operation"] == "remove":
                    results.append("redundant" if theirs_item is None
                                   else verdict(key, item["acceptedBefore"], None, theirs_item))
                elif theirs_item is None:
                    results.append({"key": key, "base": item["acceptedBefore"], "ours": item["proposedAccepted"],
                                    "theirs": None, "reason": "item_removed"})
                else:
                    for name in item["fields"]:
                        ours = _value(item["proposedAccepted"], name)
                        base = _value(item["acceptedBefore"], name)
                        if ours != base:
                            results.append(verdict(f"{key}:{name}", base, ours, _value(theirs_item, name)))
    else:
        for kind in ("nodes", "edges"):
            for item in proposal["additions"][kind]:
                results.append(verdict(f"graph:{kind[:-1]}:{item['id']}", None, item, current[kind].get(item["id"])))
    if not results:
        return "clean", []
    return summarize(results)
