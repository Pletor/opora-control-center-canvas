"""Povolení a strop Jevu vstupní brány (docs/navrhy/2026-10-30-vstupni-brana.md §7): výchozí vypnuto a 200,
ověření těla, poškozená hodnota = výchozí a soužití s přepínačem brány v `settings.brain`."""
import pytest

from backend.brain_opora.determinism import gate_setting, intake_setting
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.db_for("draft")
    gate_setting.write(canvas, {"project": "draft", "enabled": True})
    yield canvas
    canvas.close()


def test_default_is_off_with_200_per_day_and_write_keeps_the_gate(service):
    assert intake_setting.get(service, "draft") == {"project": "draft", "jev": False, "jevPerDay": 200}
    assert intake_setting.write(service, {"project": "draft", "jev": True, "jevPerDay": 5}) == {
        "project": "draft", "jev": True, "jevPerDay": 5}
    assert intake_setting.write(service, {"project": "draft", "jev": False})["jevPerDay"] == 5  # strop zůstane
    assert gate_setting.is_on(service, "draft")
    gate_setting.write(service, {"project": "draft", "enabled": False})
    assert intake_setting.read(service, "draft") == {"jev": False, "jevPerDay": 5}  # přepnutí brány nastavení nesmaže


@pytest.mark.parametrize("payload", [{"project": "draft"}, {"project": "draft", "jev": "ano"},
                                     {"project": "draft", "jev": True, "jevPerDay": -1},
                                     {"project": "draft", "jev": True, "jevPerDay": True},
                                     {"project": "draft", "jev": True, "navic": 1}])
def test_invalid_body_is_422(service, payload):
    with pytest.raises(GateError) as error:
        intake_setting.write(service, payload)
    assert error.value.status == 422


def test_unknown_project_is_404_and_broken_value_is_default(service):
    with pytest.raises(GateError) as error:
        intake_setting.get(service, "nikde")
    assert error.value.status == 404
    service.folder("draft").update(settings={"brain": {"gate": True, "intake": {"jev": "yes", "jevPerDay": 10**9}}})
    assert intake_setting.read(service, "draft") == {"jev": False, "jevPerDay": 200}
