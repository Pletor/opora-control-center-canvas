"""Plan steps: the versioned `spec.steps` field of an accepted card specification.

Contract: docs/oporahub-plan-steps.md (night contract §1). Steps live inside the node spec
`fields` next to goal/non_goals/acceptance, so they change only through spec changesets
(propose → accept, manual rebase, server auto-rebase) and are pinned in the immutable
execution assignment. Everything here is pure and deterministic; runtime progress is not
part of the spec (see opora_step_results.py).
"""
import re

from backend.canvas.opora_field_merge import merge_field

KINDS = ("code", "test", "docs", "design", "research")
REQUIRED = {"id", "order", "title", "acceptance", "dependsOn"}
OPTIONAL = {"kind", "files"}
MAX_STEPS, MAX_ACCEPTANCE, MAX_FILES = 50, 20, 50
STEP_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
_ABSENT = object()


def _text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise ValueError(f"Krok plánu: {label} musí být neprázdný text do {limit} znaků.")


def _step(item):
    if not isinstance(item, dict) or not REQUIRED <= set(item) <= REQUIRED | OPTIONAL:
        raise ValueError("Krok plánu vyžaduje id, order, title, acceptance a dependsOn (volitelně kind, files).")
    if not isinstance(item["id"], str) or not STEP_ID.fullmatch(item["id"]):
        raise ValueError("ID kroku plánu má 1 až 40 znaků A-Z, a-z, 0-9, _ nebo -.")
    if type(item["order"]) is not int or not 1 <= item["order"] <= 10_000:
        raise ValueError("Pořadí kroku plánu je celé číslo 1 až 10000.")
    _text(item["title"], 200, "title")
    acceptance = item["acceptance"]
    if not isinstance(acceptance, list) or not 1 <= len(acceptance) <= MAX_ACCEPTANCE:
        raise ValueError(f"Krok plánu má 1 až {MAX_ACCEPTANCE} podmínek přijetí.")
    for text in acceptance:
        _text(text, 1000, "podmínka přijetí")
    depends = item["dependsOn"]
    if not isinstance(depends, list) or len(depends) > MAX_STEPS or len(set(map(str, depends))) != len(depends):
        raise ValueError("dependsOn kroku plánu je pole různých ID kroků.")
    if "kind" in item and item["kind"] not in KINDS:
        raise ValueError("Druh kroku plánu je code, test, docs, design nebo research.")
    if "files" in item:
        files = item["files"]
        if not isinstance(files, list) or len(files) > MAX_FILES or len(set(map(str, files))) != len(files):
            raise ValueError(f"files kroku plánu je pole nejvýše {MAX_FILES} různých globů.")
        for pattern in files:
            _text(pattern, 300, "glob souboru")


def validate_steps(steps):
    """Schema, unique ids, existing dependsOn, acyclic DAG and `order` consistent with it."""
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        raise ValueError(f"Kroky plánu jsou pole nejvýše {MAX_STEPS} kroků.")
    for item in steps:
        _step(item)
    ids = [item["id"] for item in steps]
    if len(set(ids)) != len(ids):
        raise ValueError("ID kroků plánu musí být jedinečná.")
    orders = [item["order"] for item in steps]
    if len(set(orders)) != len(orders):
        raise ValueError("Pořadí kroků plánu musí být jedinečné.")
    known = set(ids)
    for item in steps:
        missing = [value for value in item["dependsOn"] if value not in known]
        if missing or item["id"] in item["dependsOn"]:
            raise ValueError(f"Krok {item['id']} závisí na neexistujícím nebo sám na sobě.")
    if topological(steps) is None:
        raise ValueError("Závislosti kroků plánu tvoří cyklus.")
    order = {item["id"]: item["order"] for item in steps}
    for item in steps:
        if any(order[value] >= item["order"] for value in item["dependsOn"]):
            raise ValueError(f"Pořadí kroku {item['id']} musí být větší než pořadí všech jeho závislostí.")
    return steps


def topological(steps):
    """Step ids in a deterministic topological order (ties by order, id); None on a cycle."""
    pending = {item["id"]: set(item["dependsOn"]) for item in steps}
    rank = {item["id"]: (item["order"], item["id"]) for item in steps}
    result = []
    while pending:
        ready = sorted((key for key, deps in pending.items() if not deps), key=lambda key: rank[key])
        if not ready:
            return None
        result.append(ready[0])
        del pending[ready[0]]
        for deps in pending.values():
            deps.discard(ready[0])
    return result


def steps_of(fields):
    """Steps of a spec `fields` mapping; a missing field reads as no steps (legacy specs)."""
    value = (fields or {}).get("steps", [])
    return value if isinstance(value, list) else []


def ordered(steps):
    return sorted(steps, key=lambda item: (item["order"], item["id"]))


def merge_steps(key, base, ours, theirs):
    """Per-step-id three-way merge with the Lean-proved `merge_field`.

    Returns (outcomes, merged): one outcome per step this side changed — `clean`,
    `redundant` or a conflict dict — and the merged list (None when anything conflicts or
    the combined plan is no longer a valid DAG)."""
    sides = [{item["id"]: item for item in (value if isinstance(value, list) else [])}
             for value in (base, ours, theirs)]
    outcomes, merged = [], dict(sides[2])
    for step in sorted(set().union(*sides)):
        b, o, t = (side.get(step, _ABSENT) for side in sides)
        if o == b:
            continue
        ok, value = merge_field(b, o, t)
        if not ok:
            outcomes.append({"key": f"{key}:{step}", "base": _plain(b), "ours": _plain(o), "theirs": _plain(t)})
            continue
        outcomes.append("clean" if t == b else "redundant")
        if value is _ABSENT:
            merged.pop(step, None)
        else:
            merged[step] = value
    if any(isinstance(item, dict) for item in outcomes):
        return outcomes, None
    result = ordered(merged.values())
    try:
        validate_steps(result)
    except ValueError as error:
        return [{"key": key, "base": base, "ours": ours, "theirs": theirs, "reason": "steps_invalid_after_merge",
                 "detail": str(error)}], None
    return outcomes, result


def _plain(value):
    return None if value is _ABSENT else value
