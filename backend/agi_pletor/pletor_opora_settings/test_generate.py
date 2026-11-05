"""Dílna D5-lite: vytažení a kontrola odpovědi modelu, bez modelu."""
import json

import pytest

from backend.agi_pletor.pletor_opora_settings.generate import generate_tool

GOOD = {"code": "def run(vstup):\n    return {'n': len(vstup['t'])}", "cases": [{"name": "a", "input": {"t": "ab"}, "expected": {"n": 2}}]}


def test_extracts_json_from_chatty_fenced_reply():
    seen = []
    reply = lambda prompt: seen.append(prompt) or f"Tady máš:\n```json\n{json.dumps(GOOD)}\n```"
    result = generate_tool(reply, "delka", "spočítej znaky")
    assert result["cases"] == GOOD["cases"] and result["code"].endswith("}\n")
    assert "spočítej znaky" in seen[0] and "delka" in seen[0]


@pytest.mark.parametrize("reply", [
    "žádný json", json.dumps({**GOOD, "code": "x = 1"}), json.dumps({**GOOD, "cases": [{"name": "a"}]}),
    json.dumps({"code": GOOD["code"]}),
])
def test_bad_reply_is_value_error(reply):
    with pytest.raises(ValueError):
        generate_tool(lambda _: reply, "delka", "x")


def test_empty_intent():
    with pytest.raises(ValueError):
        generate_tool(lambda _: "", "delka", "  ")
