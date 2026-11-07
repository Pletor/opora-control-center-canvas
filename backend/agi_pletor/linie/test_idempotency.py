"""Idempotence: stejný klíč a obsah = týž záznam, jiný obsah 409; klíč se zapíše až po úspěchu."""
import pytest

from backend.agi_pletor.linie import idempotency
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService


@pytest.fixture
def service(tmp_path):
    service = CanvasService(tmp_path / "data")
    yield service
    service.close()


def test_same_key_same_content_is_existing_other_content_conflicts(service):
    assert idempotency.claim(service.root, "draft", "work", "k1", {"a": 1, "b": 2}) == "new"
    assert idempotency.claim(service.root, "draft", "work", "k1", {"b": 2, "a": 1}) == "existing"
    assert idempotency.claim(service.root, "draft", "attempt", "k1", {"a": 9}) == "new"  # jiný rozsah
    with pytest.raises(GateError) as caught:
        idempotency.claim(service.root, "draft", "work", "k1", {"a": 2})
    assert (caught.value.status, caught.value.code) == (409, "idempotency_conflict")


def test_once_gives_same_id_and_records_only_after_success(service):
    made = []

    def act(ident):
        made.append(ident)
        return ident
    first = idempotency.once(service, "draft", "requests", "k", {"text": "a"}, act)
    assert idempotency.once(service, "draft", "requests", "k", {"text": "a"}, act) == first == made[1]
    with pytest.raises(GateError):
        idempotency.once(service, "draft", "requests", "k", {"text": "b"}, act)
    assert len(made) == 2  # konflikt operaci nespustí

    def broken(ident):
        raise GateError(422, "invalid_payload", "špatně", "")
    with pytest.raises(GateError):
        idempotency.once(service, "draft", "requests", "k2", {"text": "chyba"}, broken)
    assert idempotency.once(service, "draft", "requests", "k2", {"text": "opraveno"}, act)  # neúspěch klíč nezabral
    assert idempotency.once(service, "draft", "requests", None, {"text": "x"}, act) is None
