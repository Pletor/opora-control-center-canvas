"""Řazení oddílů přes falešný Jev; skutečné API se nikdy nevolá (README.md, sekce RLM)."""

import pytest

from backend.brain_opora.decision.sources import rank

CANDIDATES = [{"id": "a", "text": "Přihlášení"}, {"id": "b", "text": "Platby"}, {"id": "c", "text": "Mapa"}]


def jev(answer):
    calls = []

    def evaluate(state, questions):
        calls.append((state, questions))
        return answer

    return evaluate, calls


def test_question_and_state_follow_the_contract():
    evaluate, calls = jev({"rank": {"type": "choice", "choice": "b", "confidence": 0.6,
                                    "probabilities": {"a": 0.1, "b": 0.6, "c": 0.3}}})
    assert rank(" platby ", CANDIDATES, 2, evaluate=evaluate) == {
        "status": "ok", "ranked": [{"id": "b", "p": 0.6}, {"id": "c", "p": 0.3}]}
    state, questions = calls[0]
    assert state == {"query": "platby"}
    assert questions == {"rank": {"type": "choice", "instructions": "Který oddíl nejlépe odpovídá dotazu: platby?",
                                  "criteria": {"a": "Přihlášení", "b": "Platby", "c": "Mapa"}}}


def test_unknown_ids_and_bad_probabilities_drop_out():
    evaluate, _ = jev({"rank": {"type": "choice", "choice": "zz",
                                "probabilities": {"zz": 0.9, "a": 0.2, "b": "x", "c": True}}})
    assert rank("q", CANDIDATES, 10, evaluate=evaluate) == {"status": "ok", "ranked": [{"id": "a", "p": 0.2}]}


def test_choice_without_probabilities_still_counts():
    evaluate, _ = jev({"rank": {"type": "choice", "choice": "c", "confidence": 0.8}})
    assert rank("q", CANDIDATES, 10, evaluate=evaluate)["ranked"] == [{"id": "c", "p": 0.8}]


@pytest.mark.parametrize("answer", [None, {}, {"rank": None}, {"rank": {"probabilities": {"zz": 1.0}}}])
def test_no_usable_answer_is_unavailable(answer):
    evaluate, _ = jev(answer)
    assert rank("q", CANDIDATES, 3, evaluate=evaluate) == {"status": "unavailable"}


def test_failing_client_is_unavailable():
    def broken(state, questions):
        raise RuntimeError("síť")

    assert rank("q", CANDIDATES, 3, evaluate=broken) == {"status": "unavailable"}


def test_long_text_is_cut_to_300():
    evaluate, calls = jev(None)
    rank("q", [{"id": "a", "text": "x" * 1000}], 1, evaluate=evaluate)
    assert calls[0][1]["rank"]["criteria"]["a"] == "x" * 300


@pytest.mark.parametrize("query, candidates, top", [
    ("", CANDIDATES, 1),
    ("x" * 2001, CANDIDATES, 1),
    ("q", [], 1),
    ("q", [{"id": f"n{i}", "text": ""} for i in range(256)], 1),
    ("q", [{"id": "a b", "text": ""}], 1),
    ("q", [{"id": "a" * 129, "text": ""}], 1),
    ("q", [{"id": "a", "text": ""}, {"id": "a", "text": ""}], 1),
    ("q", [{"id": "a", "text": "", "extra": 1}], 1),
    ("q", [{"id": "a", "text": 5}], 1),
    ("q", CANDIDATES, 0),
    ("q", CANDIDATES, 51),
    ("q", CANDIDATES, True),
])
def test_invalid_input_is_refused_before_jev(query, candidates, top):
    evaluate, calls = jev(None)
    with pytest.raises(ValueError):
        rank(query, candidates, top, evaluate=evaluate)
    assert calls == []


def test_limits_are_inclusive():
    evaluate, _ = jev({"rank": {"probabilities": {"n0": 0.5}}})
    many = [{"id": f"n{i}", "text": ""} for i in range(255)]
    assert rank("x" * 2000, many, 50, evaluate=evaluate)["status"] == "ok"
    assert rank("q", [{"id": "a" * 128, "text": ""}], 1, evaluate=jev(None)[0]) == {"status": "unavailable"}
