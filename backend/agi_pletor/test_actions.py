"""Akce Pletora: jen dva typy, neprázdný text, nejvýš tři; zbytek se nevykoná a nese důvod."""
from backend.agi_pletor import actions


def test_known_actions_pass_and_text_is_trimmed():
    checked = actions.validate([{"type": "heart_message", "text": " Postav web. "}, {"type": "vault_note", "text": "A"}])
    assert checked == [({"type": "heart_message", "text": "Postav web."}, None), ({"type": "vault_note", "text": "A"}, None)]


def test_unknown_type_empty_text_and_garbage_are_refused():
    checked = actions.validate([{"type": "gate", "text": "x"}, {"type": "vault_note", "text": "  "}, "nesmysl"])
    assert [problem is not None for _, problem in checked] == [True, True, True]
    assert checked[0][1] == "Neznámý typ akce." and checked[2][0]["type"] == "None"


def test_over_the_limit_is_refused_and_non_list_means_none():
    checked = actions.validate([{"type": "vault_note", "text": str(i)} for i in range(5)])
    assert [problem for _, problem in checked][3:] == ["Přes limit 3 akcí na odpověď."] * 2
    assert all(problem is None for _, problem in checked[:3])
    assert actions.validate({"type": "vault_note"}) == [] and actions.validate(None) == []
    assert actions.validate([{"type": "vault_note", "text": "x" * (actions.TEXT_LIMIT + 1)}])[0][1]
