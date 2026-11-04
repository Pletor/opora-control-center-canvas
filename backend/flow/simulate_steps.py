"""Chování jednotlivých kroků v simulaci procesu (`docs/navrhy/2026-11-04-platno-procesu.md` §4).

`run_step(node, data, tables, services)` vrátí `{out, branch, note, rule, error}`: `branch` je jméno výstupního portu
(`None` = všechny výstupy kromě `error`), `error` česky = chyba kroku. Tabulky jsou kopie z případu, nic se nezapisuje
trvale. AI, merge, switch, loop, wait a neznámé typy se nesimulují (průchod nebo `example`).
"""

import operator

from backend.flow.expressions import FUNCTIONS, ExprError, evaluate

PASS = {"fe.click", "fe.form", "fe.state", "fe.navigate", "be.endpoint", "be.middleware", "be.auth",
        "db.transaction"}
OPERATORS = {"==": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le, ">": operator.gt,
             ">=": operator.ge}


def _value(source, data):
    """Hodnota z `params`: text je výraz, cokoli jiného (číslo, pravda/nepravda) platí doslova."""
    return evaluate(source, data) if isinstance(source, str) else source


def _base(data):
    return dict(data) if isinstance(data, dict) else {"value": data}


def _truthy(conditions, combinator, data):
    results = []
    for cond in conditions if isinstance(conditions, list) else []:
        op, left = cond.get("operator", "=="), cond.get("left")
        if op == "exists":
            try:
                results.append(_value(left, data) is not None)
            except ExprError:
                results.append(False)
            continue
        a, b = _value(left, data), _value(cond.get("right"), data)
        if op == "contains":
            results.append(FUNCTIONS["contains"](a, b))
        elif op in OPERATORS:
            try:
                results.append(OPERATORS[op](a, b))
            except TypeError:
                raise ExprError(f"Porovnání {a!r} {op} {b!r} nejde spočítat.") from None
        else:
            raise ExprError(f"Neznámý operátor {op!r}.")
    return (any if combinator == "or" else all)(results)


def _message(source, data):
    """Zpráva notifikace: výraz, a když není výrazem (prostý text bez `$json`), text doslova."""
    if not isinstance(source, str):
        return ""
    try:
        return str(evaluate(source, data))
    except ExprError:
        if "$json" in source:
            raise
        return source


def _function(node, params, data):
    rule = params.get("rule") or params.get("expression")
    if not isinstance(rule, str) or not rule.strip():
        return {"out": data, "note": "bez pravidla"}
    value = evaluate(rule, data)
    result = {"out": {**_base(data), params.get("outputName") or "result": value}, "rule": rule}
    if node["type"] == "custom.step" and params.get("branches") and params.get("branchRule"):
        name = evaluate(params["branchRule"], data)
        if name not in params["branches"]:
            raise ExprError(f"Větev {name!r} krok nemá (má {', '.join(map(str, params['branches']))}).")
        result.update(branch=name, rule=f"{rule}; větev: {params['branchRule']}")
    return result


def _write(params, data, tables):
    table = params.get("table")
    if not isinstance(table, str) or not table:
        raise ExprError("Zápis nemá tabulku (params.table).")
    base, columns = _base(data), params.get("columns") or []
    if columns and (missing := [c for c in columns if c not in base]):
        raise ExprError(f"V datech chybí sloupce {', '.join(missing)}.")
    row = {c: base[c] for c in columns} if columns else dict(base)
    tables.setdefault(table, []).append(row)
    return {"out": {**base, "inserted": row}, "note": f"řádek vložen do {table}"}


def _read(params, data, tables):
    table, where = params.get("table"), params.get("where")
    rows = [r for r in tables.get(table, []) if not (isinstance(where, str) and where.strip())
            or evaluate(where, r)]
    return {"out": {**_base(data), "rows": rows}, "rule": where or None, "note": f"{len(rows)} řádků z {table}"}


def _answer(node, services):
    """Odpověď `env.services[nodeId]`; `{error}` je chyba kroku (u db.* tak jde simulovat výpadek databáze)."""
    answer = services.get(node["id"])
    if isinstance(answer, dict) and "error" in answer:
        raise ExprError(f"Služba selhala: {answer['error']}")
    return answer


def _service(node, data, services):
    if node["id"] not in services:
        return {"out": node.get("example", data), "note": "služba bez odpovědi v env.services"}
    return {"out": _answer(node, services)}


def run_step(node, data, tables, services):
    kind, params = node["type"], node.get("params") if isinstance(node.get("params"), dict) else {}
    try:
        if kind in PASS or kind.startswith("trigger."):
            return {"out": data}
        if kind == "transform.set":
            out = _base(data) if params.get("includeOtherFields", True) else {}
            for item in params.get("assignments") or []:
                out[item["name"]] = _value(item.get("value"), data)
            return {"out": out}
        if kind in ("be.function", "custom.step"):
            return _function(node, params, data)
        if kind in ("be.validate", "flow.if"):
            ok = _truthy(params.get("conditions"), params.get("combinator", "and"), data)
            return {"out": data, "branch": "true" if ok else "false"}
        if kind in ("db.write", "db.read"):
            _answer(node, services)
        if kind == "db.write":
            return _write(params, data, tables)
        if kind == "db.read":
            return _read(params, data, tables)
        if kind.startswith("infra."):
            return _service(node, data, services)
        if kind in ("fe.show", "fe.notify"):
            return {"out": data, "note": _message(params.get("message"), data), "notify": True}
    except (ExprError, KeyError, TypeError) as error:
        return {"out": None, "error": str(error) if isinstance(error, ExprError) else f"Krok je špatně zadaný ({error!r})."}
    return {"out": node.get("example", data), "note": "nesimulováno"}
