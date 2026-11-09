"""Společné kontroly položek dávky plánu: tvar položky, `ref` a pojmenovaná chyba."""

import math
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

REF = re.compile(r"[a-z0-9-]{1,80}")
_identity_sequence = ContextVar("plan_identity_sequence", default=None)


@contextmanager
def stable_identities(seed, identities=None, observed=None):
    """Replay one immutable plan without changing legacy or concurrent UUID allocation."""
    token = _identity_sequence.set((uuid.UUID(seed), iter(range(100000)), identities, observed, set()))
    try:
        yield
    finally:
        _identity_sequence.reset(token)


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


def new_id(label=None):
    sequence = _identity_sequence.get()
    if sequence is not None:
        position = next(sequence[1])
        if (sequence[2] is not None or sequence[3] is not None) and label in sequence[4]:
            raise ValueError("Duplicate native identity allocation label.")
        sequence[4].add(label)
        if sequence[2] is not None:
            if not isinstance(label, str) or not label:
                raise ValueError("Named native identity allocation requires a label.")
            result = sequence[2].setdefault(label, str(uuid.uuid5(sequence[0], label)))
        else:
            result = str(uuid.uuid5(sequence[0], str(position)))
        if sequence[3] is not None and label is not None:
            sequence[3][label] = result
        return result
    return str(uuid.uuid4())


def position_of(value, label):
    """A drop point is optional presentation input, validated before any write."""
    fields(value, {"x", "y"}, {"x", "y"}, label)
    if any(type(value[key]) not in (int, float) or not math.isfinite(value[key])
           or abs(value[key]) > 1_000_000 for key in ("x", "y")):
        fail(label, "position vyžaduje konečné souřadnice x/y v rozsahu ±1000000.")
    # Seznam, ne n-tice: zápis do JSON by n-tici vrátil jako seznam a záznam by se při čtení lišil od zapsaného.
    return [value["x"], value["y"]]
