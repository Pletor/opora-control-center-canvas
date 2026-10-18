"""Spustitelná buňka bez databáze (docs/schranka-bunka.md §3 body 1, 3 a 4): checks, run, druh poučení, kontroly
napříč koly a společná syntaxe příkazu se CLI ověřovatele (CHECK_VECTORS)."""
import json

import pytest

from backend.editor.brief_vault.brief_vault_cell import (
    check_run,
    command_error,
    earlier_checks,
    lesson_kind_rule,
    same_checks,
)
from backend.editor.brief_vault.brief_vault_gate_rules import HINTS, validate_payload
from backend.editor.brief_vault.brief_vault_model import BadRequest

SYNTH = {"type": "SCHEMA", "done": "Tabulka existuje.", "prediction": {"tests": "pass", "criticRounds": 1, "risk": "migrace"}}
CHECKS = [{"id": "unit", "command": "uv run pytest backend/cart -q"}, {"id": "build_1", "command": "npm run build"}]
SHA = "a" * 64

# Společná syntaxe příkazu: server (validate_checks) i CLI ověřovatele (opora_cycle.py run-checks) musí souhlasit.
CHECK_VECTORS = [
    ("python -m pytest -q test_slug.py", True),
    ("python tests/test_a.py", True),
    ("npm test -- --run src/a.test.ts", True),
    ("python tests\\test_a.py", False),
    ('python "C:probe.py"', False),
    ("python C:/x.py", False),
    ("python /x.py", False),
    ("python ../x.py", False),
    ("python --file=/etc/x", False),
    ('python "unterminated', False),
    ("bash x.sh", False),
    ("python a.py | cat", False),
    ('python -c "import sys; sys.exit(0)"', False),
]


def run_of(*codes, executor="builder", verifier="checker"):
    return {"executor": executor, "verifier": verifier, "at": "2026-10-15T08:00:00+02:00",
            "checks": [{"checkId": check["id"], "command": check["command"], "exitCode": code, "durationMs": 120,
                        "outputSha256": SHA} for check, code in zip(CHECKS, codes)]}


def actual_of(tests, run=None):
    return {"tests": tests, "criticRounds": 0, "unexpected": False, **({"run": run} if run is not None else {})}


@pytest.mark.parametrize(("command", "ok"), CHECK_VECTORS)
def test_check_vectors(command, ok):
    assert (command_error(command) is None) is ok
    payload = {**SYNTH, "checks": [{"id": "c", "command": command}]}
    if ok:
        validate_payload("synthesized", payload)
    else:
        with pytest.raises(BadRequest):
            validate_payload("synthesized", payload)


def test_synthesized_checks_shape_and_safe_commands():
    assert validate_payload("synthesized", {**SYNTH, "checks": CHECKS})["checks"] == CHECKS
    for command in ("py -3 x.py", "pytest -q", "npx vitest run src/a.test.ts", "node tools/x.js", "uv run pytest a,b"):
        assert command_error(command) is None, command
    assert "checks" in HINTS["synthesized"] and "run" in HINTS["verified"]


@pytest.mark.parametrize("checks", [
    [],
    [{"id": "c", "command": "pytest"}] * 5,
    [{"id": "c", "command": "pytest"}, {"id": "c", "command": "npm test"}],
    [{"id": "c d", "command": "pytest"}],
    [{"id": "c" * 81, "command": "pytest"}],
    [{"id": "c", "command": "pytest", "extra": 1}],
    [{"id": "c", "command": "pytest " + "x" * 300}],
    [{"id": "c", "command": "   "}],
    [{"id": "c", "command": "python3 x.py"}],
    [{"id": "c", "command": "pytest && rm x"}],
    [{"id": "c", "command": "pytest > out"}],
    [{"id": "c", "command": "pytest < in"}],
    [{"id": "c", "command": "pytest `x`"}],
    [{"id": "c", "command": "pytest $(x)"}],
    [{"id": "c", "command": "pytest a,/etc"}],
    [{"id": "c", "command": "node a/../../b.js"}],
    "pytest",
])
def test_synthesized_checks_rejected(checks):
    with pytest.raises(BadRequest):
        validate_payload("synthesized", {**SYNTH, "checks": checks})


def test_verified_run_shape():
    assert validate_payload("verified", {"actual": actual_of("pass", run_of(0, 0))})["actual"]["run"]["executor"] == "builder"
    for at in ("2026-10-15T08:00:00Z", "2026-10-15T06:00:00.123+00:00"):
        validate_payload("verified", {"actual": actual_of("pass", {**run_of(0, 0), "at": at})})


@pytest.mark.parametrize("change", [
    lambda run: run.pop("at"),
    lambda run: run.update(extra=1),
    lambda run: run.update(executor=""),
    lambda run: run.update(verifier="v" * 81),
    lambda run: run.update(checks=[]),
    lambda run: run.update(at="2026-10-15T08:00:00"),
    lambda run: run.update(at="2026-10-15"),
    lambda run: run.update(at="včera"),
    lambda run: run["checks"][0].update(exitCode=True),
    lambda run: run["checks"][0].update(exitCode="0"),
    lambda run: run["checks"][0].update(durationMs=-1),
    lambda run: run["checks"][0].update(durationMs=1.5),
    lambda run: run["checks"][0].update(outputSha256="A" * 64),
    lambda run: run["checks"][0].update(outputSha256="a" * 63),
    lambda run: run["checks"][0].pop("command"),
])
def test_verified_run_shape_rejected(change):
    run = run_of(0, 0)
    change(run)
    with pytest.raises(BadRequest):
        validate_payload("verified", {"actual": actual_of("pass", run)})


def test_check_run_semantics():
    cell = {**SYNTH, "checks": CHECKS}
    check_run(SYNTH, actual_of("pass"))  # bez checks i bez run beze změny
    check_run(cell, actual_of("untested"))  # plán schválen ≠ testy (§13)
    check_run(cell, actual_of("pass", run_of(0, 0)))
    check_run(cell, actual_of("fail", run_of(0, 2)))
    other = run_of(0, 0)
    other["checks"][1]["command"] = "npm run build -- --x"
    broken = [
        (cell, actual_of("pass")),  # pass/fail při checks jen s run
        (cell, actual_of("fail")),
        (SYNTH, actual_of("pass", run_of(0, 0))),  # run bez checks
        (cell, actual_of("pass", run_of(0))),  # chybí kontrola
        (cell, actual_of("pass", {**run_of(0, 0), "checks": list(reversed(run_of(0, 0)["checks"]))})),  # pořadí
        (cell, actual_of("pass", other)),  # jiný příkaz
        (cell, actual_of("pass", run_of(0, 1))),  # pass s nenulovým kódem
        (cell, actual_of("fail", run_of(0, 0))),  # fail se samými nulami
        (cell, actual_of("untested", run_of(0, 0))),
        (cell, actual_of("pass", run_of(0, 0, executor="same", verifier="same"))),
    ]
    for synthesized, actual in broken:
        with pytest.raises(BadRequest):
            check_run(synthesized, actual)


def test_lesson_kind_follows_verified_outcome():
    lesson_kind_rule(actual_of("fail"), "antipattern")
    lesson_kind_rule({**actual_of("untested"), "planApproved": False}, "antipattern")
    lesson_kind_rule(actual_of("pass"), "pattern")
    for kind in ("pattern", "antipattern"):
        lesson_kind_rule({**actual_of("untested"), "planApproved": True}, kind)  # úspěch bez testů druh neurčuje
    for actual, kind in ((actual_of("fail"), "pattern"), ({**actual_of("pass"), "planApproved": False}, "pattern"),
                         (actual_of("pass"), "antipattern")):
        with pytest.raises(BadRequest):
            lesson_kind_rule(actual, kind)


def test_checks_are_the_yardstick_across_rounds():
    def gates(value, payload):
        return json.dumps({"synthesized": {"value": value, "payload": payload}})
    assert earlier_checks([None, gates(False, None)]) is None  # synthesized nikdy zapnutá: nic neváže
    assert earlier_checks([gates(True, SYNTH)]) == []  # zapnutá bez kontrol = „žádné“
    history = [gates(True, {**SYNTH, "checks": CHECKS}), gates(False, None)]
    assert earlier_checks(history) == CHECKS
    same_checks(None, {**SYNTH, "checks": CHECKS})
    same_checks([], SYNTH)
    same_checks(CHECKS, {**SYNTH, "checks": [dict(item) for item in CHECKS]})
    with pytest.raises(BadRequest, match="napříč koly"):
        same_checks([], {**SYNTH, "checks": CHECKS})  # přidání checks v dalším kole
    for changed in (SYNTH, {**SYNTH, "checks": CHECKS[:1]}, {**SYNTH, "checks": list(reversed(CHECKS))},
                    {**SYNTH, "checks": [CHECKS[0], {**CHECKS[1], "command": "npm test"}]}):
        with pytest.raises(BadRequest, match="napříč koly"):
            same_checks(CHECKS, changed)
