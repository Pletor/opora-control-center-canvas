"""Chyby, které agentovi i člověku řeknou, co přesně opravit, místo obecného „neplatný formát“.

`InvalidPayload` = neplatné tělo požadavku (HTTP 422): které pole, jaký tvar a krátký platný příklad.
`NextStep` = platný požadavek, který stav zatím nedovolí (HTTP 409): `code` a `hint` s dalším krokem.
Obě dědí `ValueError`, takže starší `except ValueError` (přebalení popisku v dávce plánu) je dál chytá;
handler aplikace (`backend/app/factory.py`) je pozná dřív než obecné `ValueError` → 409.
"""

import difflib
import json


class InvalidPayload(ValueError):
    """Neplatné tělo: HTTP 422 s `field`, `expected` a volitelně `example`."""

    status = 422

    def __init__(self, message, *, field=None, expected=None, example=None):
        super().__init__(message)
        self.field, self.expected, self.example = field, expected, example

    def body(self):
        out = {"error": str(self), "code": "invalid_payload"}
        for key in ("field", "expected", "example"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        return out


class NextStep(ValueError):
    """Stav požadavek zatím nedovolí, ale další krok je známý: HTTP 409 s `code` a `hint`."""

    status = 409

    def __init__(self, message, *, code, hint):
        super().__init__(message)
        self.code, self.hint = code, hint

    def body(self):
        return {"error": str(self), "code": self.code, "hint": self.hint}


def invalid(label, field, problem, expected, example=None):
    """`InvalidPayload` se zprávou „<label>: <problem> Očekávám <field>: <expected>. Příklad: …“."""
    text = (f"{label}: " if label else "") + f"{problem} Očekávám {field}: {expected}."
    if example is not None:
        text += " Příklad: " + json.dumps(example, ensure_ascii=False)
    return InvalidPayload(text, field=field, expected=expected, example=example)


def keys_problem(value, required, optional=frozenset()):
    """Lidsky čitelný rozdíl klíčů objektu proti tvaru, nebo None, když tvar sedí.

    Neznámé pole s blízkým povoleným jménem dostane nápovědu (`environment` → `environments`)."""
    if not isinstance(value, dict):
        return f"má být objekt, ne {type(value).__name__}."
    allowed = set(required) | set(optional)
    missing = sorted(set(required) - set(value))
    unknown = sorted(set(value) - allowed)
    if not missing and not unknown:
        return None
    parts = []
    if missing:
        parts.append("chybí " + ", ".join(missing))
    for key in unknown:
        close = difflib.get_close_matches(key, sorted(allowed), n=1)
        parts.append(f"neznámé pole {key}" + (f" (myslíte {close[0]}?)" if close else ""))
    return "; ".join(parts) + "."


def relabel(error, prefix):
    """Stejný druh chyby s popiskem `prefix: ` na začátku (dávka plánu doplňuje ref uzlu)."""
    text = f"{prefix}: {error}"
    if isinstance(error, InvalidPayload):
        return InvalidPayload(text, field=error.field, expected=error.expected, example=error.example)
    if isinstance(error, NextStep):
        return NextStep(text, code=error.code, hint=error.hint)
    return ValueError(text)


def exact_fields(payload, fields, what, example):
    """Tělo s přesně těmito poli, jinak 422 s tím, co chybí a co je navíc, a s platným příkladem."""
    problem = keys_problem(payload, fields)
    if problem:
        raise invalid("", "body", f"{what}: {problem}",
                      "přesně " + ", ".join(sorted(fields)) + " (hodnoty z preconditions akce v agent-state)", example)
