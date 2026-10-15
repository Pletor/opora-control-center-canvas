"""Pravidla bran bez databáze (docs/schranka-neurony.md §3, §9 bod 4): payloady, predikční chyba, otisk a platnost."""
import json

import pytest

from backend.editor.brief_vault.brief_vault_gate_rules import (
    GATES,
    MAX_ROUNDS,
    MICROSTEP_TYPES,
    encode_gates,
    gate_state,
    input_hash,
    prediction_error,
    round_fields,
    round_of,
    stored_gates_valid,
    summary,
    validate_payload,
)
from backend.editor.brief_vault.brief_vault_model import BadRequest

SYNTH = {"type": "SCHEMA", "done": "Tabulka existuje.", "prediction": {"tests": "pass", "criticRounds": 1, "risk": "migrace"}}


def test_gate_order_is_the_contract():
    assert GATES == ("scoped", "weighed", "synthesized", "decided", "planned", "placed", "verified", "learned")
    assert len(MICROSTEP_TYPES) == 14 and "ENCRYPTION" in MICROSTEP_TYPES


@pytest.mark.parametrize(("prediction", "actual", "error"), [
    (("pass", 0), ("pass", 0, False), 0.0),
    (("pass", 0), ("fail", 0, False), 0.33),
    (("pass", 1), ("pass", 2, False), 0.17),
    (("pass", 0), ("pass", 2, False), 0.33),
    (("pass", 0), ("pass", 3, False), 0.33),   # r je shora omezené: min(|3 − 0|, 2) / 2 = 1
    (("fail", 2), ("pass", 0, False), 0.67),
    (("pass", 1), ("pass", 1, True), 0.33),
    (("pass", 0), ("fail", 3, True), 1.0),
    (("fail", 2), ("fail", 1, True), 0.5),
])
def test_prediction_error_table(prediction, actual, error):
    assert prediction_error({"tests": prediction[0], "criticRounds": prediction[1], "risk": "r"},
                            {"tests": actual[0], "criticRounds": actual[1], "unexpected": actual[2]}) == error


@pytest.mark.parametrize(("gate", "payload"), [
    ("scoped", {"x": 1}),
    ("weighed", {"benefit": "b" * 281, "risk": "r"}),
    ("weighed", {"benefit": "b", "risk": ""}),
    ("weighed", {"benefit": "b", "risk": "r", "extra": 1}),
    ("synthesized", {**SYNTH, "type": "FOO"}),
    ("synthesized", {**SYNTH, "steps": []}),
    ("synthesized", {**SYNTH, "steps": ["krok"] * 13}),
    ("synthesized", {**SYNTH, "steps": ["k" * 301]}),
    ("synthesized", {**SYNTH, "steps": [" "]}),
    ("synthesized", {**SYNTH, "steps": "1. krok"}),
    ("synthesized", {**SYNTH, "layer": "infra"}),
    ("synthesized", {**SYNTH, "extra": 1}),
    ("synthesized", {"type": "SCHEMA", "done": "d", "steps": ["krok"]}),
    ("synthesized", {**SYNTH, "done": "d" * 501}),
    ("synthesized", {**SYNTH, "prediction": {**SYNTH["prediction"], "criticRounds": 3}}),
    ("synthesized", {**SYNTH, "prediction": {**SYNTH["prediction"], "criticRounds": True}}),
    ("synthesized", {**SYNTH, "prediction": {**SYNTH["prediction"], "tests": "ok"}}),
    ("decided", {"verdict": "maybe", "reason": "r"}),
    ("decided", {"verdict": "yes", "reason": "r" * 501}),
    ("verified", {"actual": {"tests": "pass", "criticRounds": 4, "unexpected": False}}),
    ("verified", {"actual": {"tests": "pass", "criticRounds": 0, "unexpected": "no"}}),
    ("learned", {"lesson": "l" * 501, "kind": "pattern"}),
    ("learned", {"lesson": "l", "kind": "rule"}),
    ("nope", None),
])
def test_invalid_payloads_are_bad_requests(gate, payload):
    with pytest.raises(BadRequest):
        validate_payload(gate, payload)


def test_valid_payloads_pass_unchanged():
    assert validate_payload("scoped", None) is None
    assert validate_payload("synthesized", SYNTH) == SYNTH
    full = {**SYNTH, "steps": ["Přidej tabulku", "k" * 300] + ["krok"] * 10, "layer": "backend"}
    assert validate_payload("synthesized", full) == full
    assert validate_payload("decided", {"verdict": "no", "reason": "Mimo rozsah."})["verdict"] == "no"
    assert validate_payload("learned", {"lesson": "Menší kroky.", "kind": "antipattern"})["kind"] == "antipattern"


def _entry(value, digest, payload=None, revision=2):
    return {"value": value, "payload": payload, "by": "a", "actor": "agent", "at": "T", "inputHash": digest,
            "revision": revision}


def test_state_is_a_prefix_of_gates_with_the_current_input_hash():
    row = {"title": "T", "text": "t"}
    digest = input_hash("T", "t", "be")
    entries = {"scoped": _entry(True, digest), "weighed": _entry(True, digest), "decided": _entry(True, digest)}
    state = gate_state({**row, "gates": encode_gates(entries)}, "be")
    assert state["on"] == ["scoped", "weighed"] and state["next"] == "synthesized" and state["stale"] is False
    assert summary(state)["gateStep"] == 2 and summary(state)["gates"]["decided"] is False
    moved = gate_state({**row, "gates": encode_gates(entries)}, "ux")  # jiná platná disciplína = jiný otisk
    assert moved["on"] == [] and moved["stale"] is True and moved["next"] == "scoped"
    assert input_hash("T", "t", "be") != input_hash("T", "t2", "be") != input_hash("T2", "t", "be")


def test_stored_gates_shape():
    digest = input_hash("T", "t", "be")
    assert stored_gates_valid(None) and stored_gates_valid(encode_gates({"scoped": _entry(True, digest)}))
    assert encode_gates({}) is None
    assert not stored_gates_valid("[]") and not stored_gates_valid("{")
    assert not stored_gates_valid(json.dumps({"nope": _entry(True, digest)}))
    assert not stored_gates_valid(json.dumps({"scoped": {"value": True}}))
    assert list(json.loads(encode_gates({"weighed": _entry(True, digest), "scoped": _entry(True, digest)}))) == ["scoped", "weighed"]


def _gates(**entries):
    return encode_gates({name: {"value": value, "payload": payload, "by": "t", "actor": "agent", "at": "T",
                                "inputHash": "h", "revision": revision}
                         for name, (value, payload, revision) in entries.items()})


def test_round_counts_new_synthesized_after_failed_verified():
    fail = {"actual": {"tests": "fail", "criticRounds": 1, "unexpected": False}, "predictionError": 0.3}
    passed = {"actual": {"tests": "pass", "criticRounds": 1, "unexpected": False}, "predictionError": 0.0}
    assert round_of([]) == 1 and round_of([None, "poškozené"]) == 1
    verified_fail = _gates(synthesized=(True, {}, 3), verified=(True, fail, 7))
    assert round_of([verified_fail, verified_fail]) == 1  # neúspěch sám kolo nezvedne, převzatý záznam jednou
    reset = _gates(synthesized=(False, None, 8), verified=(False, None, 8))
    assert round_of([verified_fail, reset, reset]) == 2
    other = _gates(synthesized=(False, None, 4), decided=(False, {"verdict": "other"}, 4))
    assert round_of([other]) == 1  # decided: other bez neúspěšného verified nové kolo nepočítá
    verified_pass = _gates(synthesized=(True, {}, 9), verified=(True, passed, 12))
    assert round_of([verified_fail, reset, verified_pass, _gates(synthesized=(False, None, 13))]) == 2
    again = _gates(synthesized=(True, {}, 9), verified=(True, fail, 12))
    assert round_of([verified_fail, reset, again, _gates(synthesized=(False, None, 13))]) == 3
    assert round_fields({"f": 4}, "f") == {"round": 4, "exhausted": True} and MAX_ROUNDS == 3
    assert round_fields({}, "f") == {"round": 1, "exhausted": False}
