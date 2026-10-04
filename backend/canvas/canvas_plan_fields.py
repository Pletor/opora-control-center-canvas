"""Společné kontroly položek dávky plánu: tvar položky, `ref` a pojmenovaná chyba."""

import math
import re
import uuid

REF = re.compile(r"[a-z0-9-]{1,80}")


def fail(label, message):
    raise ValueError(f"{label}: {message}")


def fields(item, allowed, required, label):
    if not isinstance(item, dict):
        fail(label, "položka musí být objekt.")
    if set(item) - allowed:
        fail(label, "neznámá pole " + ", ".join(sorted(set(item) - allowed)) + ".")
    if required - set(item):
        fail(label, "chybí " + ", ".join(sorted(required - set(item))) + ".")


def plan_ref(value, label):
    if not isinstance(value, str) or not REF.fullmatch(value):
        fail(label, "ref musí být [a-z0-9-] do 80 znaků.")
    return value


def items_of(value, label, name):
    if not isinstance(value, list):
        fail(label, f"{name} musí být pole.")
    return value


def new_id():
    return str(uuid.uuid4())


def position_of(value, label):
    """A drop point is optional presentation input, validated before any write."""
    fields(value, {"x", "y"}, {"x", "y"}, label)
    if any(type(value[key]) not in (int, float) or not math.isfinite(value[key])
           or abs(value[key]) > 1_000_000 for key in ("x", "y")):
        fail(label, "position vyžaduje konečné souřadnice x/y v rozsahu ±1000000.")
    return value["x"], value["y"]
