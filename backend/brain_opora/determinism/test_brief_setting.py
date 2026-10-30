"""Výslech srdce zapnutý a strop rešerše (docs/navrhy/2026-10-30-vyslech-srdce.md §8): výchozí zapnuto a 0,30 USD,
ověření těla, poškozená hodnota = výchozí a soužití s ostatním nastavením `settings.brain`."""
import pytest

from backend.brain_opora.determinism import brief_setting, gate_setting, intake_setting
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.db_for("draft")
    gate_setting.write(canvas, {"project": "draft", "enabled": True})
    yield canvas
    canvas.close()


def test_default_is_on_with_thirty_cents_and_write_keeps_other_brain_settings(service):
    intake_setting.write(service, {"project": "draft", "jev": True, "jevPerDay": 7})
    assert brief_setting.get(service, "draft") == {"project": "draft", "enabled": True, "researchUsd": 0.30}
    assert brief_setting.write(service, {"project": "draft", "enabled": False, "researchUsd": 0.5}) == {
        "project": "draft", "enabled": False, "researchUsd": 0.5}
    assert brief_setting.write(service, {"project": "draft", "enabled": True})["researchUsd"] == 0.5  # strop zůstane
    assert gate_setting.is_on(service, "draft") and intake_setting.read(service, "draft")["jevPerDay"] == 7
    intake_setting.write(service, {"project": "draft", "jev": False})
    assert brief_setting.read(service, "draft") == {"enabled": True, "researchUsd": 0.5}


@pytest.mark.parametrize("payload", [{"project": "draft"}, {"project": "draft", "enabled": "ano"},
                                     {"project": "draft", "enabled": True, "researchUsd": -0.1},
                                     {"project": "draft", "enabled": True, "researchUsd": 99},
                                     {"project": "draft", "enabled": True, "researchUsd": True},
                                     {"project": "draft", "enabled": True, "navic": 1}])
def test_invalid_body_is_422(service, payload):
    with pytest.raises(GateError) as error:
        brief_setting.write(service, payload)
    assert error.value.status == 422


def test_unknown_project_is_404_and_broken_value_is_default(service):
    with pytest.raises(GateError) as error:
        brief_setting.get(service, "nikde")
    assert error.value.status == 404
    service.folder("draft").update(settings={"brain": {"brief": {"enabled": "ne", "researchUsd": "hodně"}}})
    assert brief_setting.read(service, "draft") == {"enabled": True, "researchUsd": 0.30}
    service.folder("draft").update(settings={"brain": {"brief": {"enabled": False}}})
    assert brief_setting.read(service, "draft") == {"enabled": False, "researchUsd": 0.30}
