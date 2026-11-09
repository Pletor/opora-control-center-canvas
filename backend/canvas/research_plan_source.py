"""Translate research validation into native canvas HTTP errors."""
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.payload_errors import InvalidPayload, NextStep
from backend.editor.research import planning_source


def _checked(function, *args):
    try:
        return function(*args)
    except GateError as error:
        if error.status == 422:
            raise InvalidPayload(str(error), field="researchSource") from error
        raise NextStep(str(error), code=error.code, hint=error.hint) from error


def shape(source):
    return _checked(planning_source.shape, source)


def validate_source(service, project, workspace, source):
    return _checked(planning_source.validate_source, service, project, workspace, source)
