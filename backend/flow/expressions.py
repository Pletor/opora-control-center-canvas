"""Malý bezpečný jazyk výrazů pro simulaci procesu (`docs/navrhy/2026-11-04-platno-procesu.md` §4).

Výraz je Python výraz zpracovaný přes `ast` s whitelistem uzlů: čísla, řetězce, `$json.pole.pod` (čtení z dat kroku),
aritmetika, porovnání, `and or not`, `a if p else b` a funkce `round min max len abs number text lower upper contains`.
Žádné `eval`/`exec`, žádné atributy mimo čtení polí z dat, žádné volání mimo whitelist. Chyba výrazu (syntax, chybějící
pole, dělení nulou, typ, příliš velká mocnina) je `ExprError` česky; volající ji převede na chybu kroku.
"""

import ast
import operator
import re

MAX_LENGTH = 500
MAX_POWER = 100  # shortcut: exponent nad 100 je chyba; až bude třeba víc, limitovat velikost výsledku
MAX_TEXT = 10_000
ROOT = "_json"
JSON_REF = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\$json\b""")


class ExprError(ValueError):
    """Výraz nejde vyhodnotit (chyba kroku simulace)."""


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExprError(f"Očekáváno číslo, přišlo {value!r}.")
    return value


def _text_of(value, what):
    if not isinstance(value, str):
        raise ExprError(f"{what} bere text.")
    return value


def _power(base, exp):
    if abs(_number(exp)) > MAX_POWER:
        raise ExprError(f"Mocnina je omezena na exponent {MAX_POWER}.")
    return _number(base) ** exp


def _times(a, b):
    if isinstance(a, str) or isinstance(b, str):
        text, count = (a, b) if isinstance(a, str) else (b, a)
        if not isinstance(count, int) or isinstance(count, bool) or len(text) * max(count, 0) > MAX_TEXT:
            raise ExprError("Násobení textu číslem je omezeno délkou výsledku.")
        return text * count
    return _number(a) * _number(b)


def _plus(a, b):
    return a + b if isinstance(a, str) and isinstance(b, str) else _number(a) + _number(b)


def _arith(fn):
    return lambda a, b: fn(_number(a), _number(b))


BINARY = {ast.Add: _plus, ast.Sub: _arith(operator.sub), ast.Mult: _times, ast.Div: _arith(operator.truediv),
          ast.FloorDiv: _arith(operator.floordiv), ast.Mod: _arith(operator.mod), ast.Pow: _power}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
           ast.Gt: operator.gt, ast.GtE: operator.ge}


def _to_number(value):
    if isinstance(value, str):
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            raise ExprError(f"{value!r} není číslo.") from None
    return _number(value)


def _to_text(value):
    if isinstance(value, (dict, list)):
        raise ExprError("text() bere číslo, text nebo pravdu/nepravdu.")
    return "" if value is None else str(value)


def _contains(whole, part):
    if not isinstance(whole, (str, list)):
        raise ExprError("contains() hledá v textu nebo seznamu.")
    return part in whole


def _extreme(fn):
    def run(*args):
        values = args[0] if len(args) == 1 and isinstance(args[0], list) else args
        return fn([_number(v) for v in values])
    return run


def _len(value):
    if not isinstance(value, (str, list)):
        raise ExprError("len() bere text nebo seznam.")
    return len(value)


FUNCTIONS = {"round": lambda x, n=0: round(_number(x), int(_number(n))), "min": _extreme(min), "max": _extreme(max),
             "len": _len, "abs": lambda x: abs(_number(x)), "number": _to_number, "text": _to_text,
             "lower": lambda x: _text_of(x, "lower()").lower(), "upper": lambda x: _text_of(x, "upper()").upper(),
             "contains": _contains}


def parse(source):
    if not isinstance(source, str) or not source.strip():
        raise ExprError("Výraz je prázdný.")
    if len(source) > MAX_LENGTH:
        raise ExprError(f"Výraz je delší než {MAX_LENGTH} znaků.")
    prepared = JSON_REF.sub(lambda m: m.group(1) or ROOT, source.strip())
    try:
        return ast.parse(prepared, mode="eval").body
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        raise ExprError(f"Výraz {source!r} nejde přečíst.") from None


def evaluate(source, data):
    """Hodnota výrazu; `$json` je `data` kroku."""
    try:
        return _eval(parse(source), data)
    except ExprError:
        raise
    except ZeroDivisionError:
        raise ExprError("Dělení nulou.") from None
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise ExprError(f"Výraz nelze spočítat ({error}).") from None


def _field(node, data):
    """`$json.a.b`: jen čtení klíčů objektů v datech; cokoli jiného je chyba."""
    if isinstance(node, ast.Name) and node.id == ROOT:
        return data, "$json"
    if isinstance(node, ast.Attribute):
        base, path = _field(node.value, data)
        if not isinstance(base, dict) or node.attr not in base:
            raise ExprError(f"Pole {path}.{node.attr} v datech chybí.")
        return base[node.attr], f"{path}.{node.attr}"
    raise ExprError("Atribut jde číst jen z $json.")


def _eval(node, data):
    match node:
        case ast.Constant(value=value) if value is None or isinstance(value, (bool, int, float, str)):
            return value
        case ast.Name(id=name) if name == ROOT:
            return data
        case ast.Attribute():
            return _field(node, data)[0]
        case ast.List(elts=items):
            return [_eval(i, data) for i in items]
        case ast.BinOp(left=left, op=op, right=right) if type(op) in BINARY:
            result = BINARY[type(op)](_eval(left, data), _eval(right, data))
            if isinstance(result, str) and len(result) > MAX_TEXT:
                raise ExprError("Výsledný text je příliš dlouhý.")
            return result
        case ast.UnaryOp(op=ast.Not(), operand=operand):
            return not _eval(operand, data)
        case ast.UnaryOp(op=ast.USub() | ast.UAdd() as op, operand=operand):
            value = _number(_eval(operand, data))
            return -value if isinstance(op, ast.USub) else value
        case ast.BoolOp(op=op, values=values):
            result = None
            for value in values:
                result = _eval(value, data)
                if bool(result) == isinstance(op, ast.Or):
                    break
            return result
        case ast.Compare(left=left, ops=ops, comparators=rights) if all(type(o) in COMPARE for o in ops):
            current = _eval(left, data)
            for op, right in zip(ops, rights):
                following = _eval(right, data)
                if not COMPARE[type(op)](current, following):
                    return False
                current = following
            return True
        case ast.IfExp(test=test, body=body, orelse=orelse):
            return _eval(body if _eval(test, data) else orelse, data)
        case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if name in FUNCTIONS \
                and not any(isinstance(a, ast.Starred) for a in args):
            return FUNCTIONS[name](*[_eval(a, data) for a in args])
    raise ExprError(f"Ve výrazu je nepovolená část ({type(node).__name__}).")
