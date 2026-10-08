"""Reusable gate commands and structured, externally reported run results."""

from datetime import datetime

from backend.canvas.design_metadata import validate_design


def validate_scenario(value):
    if not isinstance(value, dict) or set(value) != {"command"}:
        raise ValueError("scenario musí obsahovat command.")
    command = value["command"]
    if not isinstance(command, str) or not command.strip() or len(command) > 4000 or "\x00" in command:
        raise ValueError("Scénář vyžaduje neprázdný příkaz do 4000 znaků.")


def validate_run(value):
    if not isinstance(value, dict) or set(value) != {"command", "at", "passed", "failed", "logUrl", "firstFailure"}:
        raise ValueError("Běh scénáře vyžaduje command, at, passed, failed, logUrl a firstFailure.")
    validate_scenario({"command": value["command"]})
    for key in ("passed", "failed"):
        if type(value[key]) is not int or not 0 <= value[key] <= 1_000_000:
            raise ValueError("Počty kroků musí být nezáporná celá čísla do milionu.")
    if value["passed"] + value["failed"] == 0:
        raise ValueError("Běh scénáře musí obsahovat alespoň jeden krok.")
    failure = value["firstFailure"]
    if not isinstance(failure, str) or len(failure) > 4000 or "\x00" in failure or bool(failure.strip()) != bool(value["failed"]):
        raise ValueError("Neúspěšný běh potřebuje první nesplněný krok, úspěšný prázdné firstFailure.")
    validate_design({"artifactUrl": value["logUrl"], "version": "run"})
    try:
        if not isinstance(value["at"], str) or len(value["at"]) > 40 or datetime.fromisoformat(value["at"]).tzinfo is None:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Čas běhu vyžaduje ISO časovou zónu.") from None


def run_schema():
    return {"type": "object", "additionalProperties": False,
            "required": ["command", "at", "passed", "failed", "logUrl", "firstFailure"],
            "properties": {"command": {"type": "string", "minLength": 1, "maxLength": 4000},
                           "at": {"type": "string", "maxLength": 40}, "logUrl": {"type": "string", "maxLength": 2048},
                           "firstFailure": {"type": "string", "maxLength": 4000},
                           **{key: {"type": "integer", "minimum": 0, "maximum": 1_000_000} for key in ("passed", "failed")}}}
