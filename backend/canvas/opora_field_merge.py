"""Field-level three-way merge: the proved decision rule for rebasing a stale proposal.

Pure and deterministic; mirrors tools/formal/lean/OporaHub/FieldMerge.lean, whose theorems
prove it commutative and that disjoint field changes merge without conflict while keeping
both sides. `backend/canvas/test_opora_lean_differential.py` compares this function with
the Lean model on the exported vectors. Server-side auto-rebase decides every field with
`merge_field` (opora_auto_rebase_merge.py, docs/oporahub-auto-rebase.md); with it enabled the
agent-state `auto_rebase` gap disappears.
"""

ABSENT = object()


def merge_field(base, ours, theirs):
    """Return (True, value) or (False, None) for a conflict; ABSENT marks a missing field."""
    if ours == base:
        return True, theirs
    if theirs == base:
        return True, ours
    if ours == theirs:
        return True, ours
    return False, None


def merge_fields(base, ours, theirs):
    """`{field: value}` maps -> {"merged": {...}, "conflicts": [field, ...]} (fields sorted)."""
    merged, conflicts = {}, []
    for field in sorted(set(base) | set(ours) | set(theirs)):
        ok, value = merge_field(base.get(field, ABSENT), ours.get(field, ABSENT), theirs.get(field, ABSENT))
        if not ok:
            conflicts.append(field)
        elif value is not ABSENT:
            merged[field] = value
    return {"merged": merged, "conflicts": conflicts}
