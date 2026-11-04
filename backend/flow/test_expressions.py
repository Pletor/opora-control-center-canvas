import pytest

from backend.flow.expressions import ExprError, evaluate

DATA = {"w": 80, "h": 180, "name": "Eva", "sub": {"x": 2}, "list": [1, 2, 3]}


@pytest.mark.parametrize("source, expected", [
    ("round($json.w / (($json.h / 100) ** 2), 1)", 24.7),
    ("$json.sub.x * 3 + 1", 7),
    ("7 // 2 + 7 % 4 - 2 ** 3", -2),
    ("$json.w > 50 and $json.h < 200", True),
    ("not ($json.w == 80) or $json.name == 'Eva'", True),
    ("'velká' if $json.w > 100 else 'malá'", "malá"),
    ("upper($json.name) + lower('ABC') + text(5)", "EVAabc5"),
    ("min(3, 1, 2) + max([4, 9]) + abs(-2) + len($json.list)", 15),
    ("number('2.5') + number('2')", 4.5),
    ("contains($json.name, 'v') and contains($json.list, 2)", True),
    ("1 < 2 < 3", True),
    ("'$json' + 'x'", "$jsonx"),
])
def test_valid_expressions(source, expected):
    assert evaluate(source, DATA) == expected


@pytest.mark.parametrize("source, message", [
    ("$json.neni", "chybí"),
    ("$json.sub.neni", "chybí"),
    ("1 / 0", "Dělení nulou"),
    ("1 // 0", "Dělení nulou"),
    ("'a' + 1", "Očekáváno číslo"),
    ("'a' < 1", "nelze spočítat"),
    ("number('abc')", "není číslo"),
    ("", "prázdný"),
    ("1 +", "nejde přečíst"),
    ("x" * 501, "delší než 500"),
])
def test_step_errors_are_czech_expr_errors(source, message):
    with pytest.raises(ExprError, match=message):
        evaluate(source, DATA)


@pytest.mark.parametrize("source", [
    "__import__('os').system('x')", "().__class__", "$json.__class__", "$json.w.real", "(1).__class__.__mro__",
    "lambda: 1", "(lambda: 1)()", "[x for x in [1]]", "{1: 2}", "open('f')", "eval('1')", "len.__call__([])",
    "round(x=1)", "min(*[1, 2])", "$json['w']", "$json.list[0]", "f'{1}'", "[1][0]", "x := 1", "await x",
    "_json.__class__", "print(1)", "1 + __import__('os')",
])
def test_escape_attempts_are_rejected(source):
    with pytest.raises(ExprError):
        evaluate(source, DATA)


def test_power_and_text_blowups_are_limited():
    for source in ("9 ** 9 ** 9", "2 ** 101", "'a' * 10 ** 9", "'abc' * 100 * 100", "10.0 ** 1000"):
        with pytest.raises(ExprError):
            evaluate(source, DATA)
    assert evaluate("2 ** 100", DATA) == 2 ** 100
    assert len(evaluate("'ab' * 5", DATA)) == 10


def test_deep_nesting_does_not_crash():
    with pytest.raises(ExprError):
        evaluate("(" * 240 + "1" + ")" * 240 + "+" + "-" * 240 + "1", DATA)
