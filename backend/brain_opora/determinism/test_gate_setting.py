"""Přepínač brány: výchozí vypnuto, poškozená hodnota = vypnuto, zápis vedle agentAutonomy."""
import json
from datetime import UTC, datetime

import pytest

from backend.brain_opora.determinism import gate_setting
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService

NOW = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.db_for("draft")  # založí složku draftu s project.json
    yield canvas
    canvas.close()


def test_off_by_default_and_on_after_write(service):
    assert gate_setting.read(service, "draft") == {"gate": False}
    assert gate_setting.is_on(service, "draft") is False
    saved = gate_setting.write(service, {"project": "draft", "enabled": True}, now=NOW)
    assert saved == {"project": "draft", "enabled": True, "since": "2026-10-28T10:00:00Z", "by": "human"}
    assert gate_setting.is_on(service, "draft") is True
    assert service.folder("draft").read()["settings"]["brain"]["gate"] is True
    assert gate_setting.write(service, {"project": "draft", "enabled": False}) == {"project": "draft", "enabled": False}
    assert gate_setting.is_on(service, "draft") is False


def test_corrupt_or_missing_value_reads_as_off(service):
    folder = service.folder("draft")
    for broken in ("ano", {"gate": "true"}, {"gate": 1}, None):
        folder.update(settings={"brain": broken})
        assert gate_setting.read(service, "draft") == {"gate": False}
    folder.identity_file.write_text("{nejde", encoding="utf-8")
    assert gate_setting.is_on(service, "draft") is False
    assert gate_setting.is_on(service, "") is False and gate_setting.is_on(service, "../x") is False
    assert gate_setting.is_on(service, "neexistuje") is False


def test_write_validates_body_and_project(service):
    for body in ({"project": "draft"}, {"project": "draft", "enabled": "ano"},
                 {"project": "draft", "enabled": True, "x": 1}, []):
        with pytest.raises(GateError) as error:
            gate_setting.write(service, body)
        assert error.value.status == 422 and error.value.hint
    with pytest.raises(GateError) as error:
        gate_setting.write(service, {"project": "neexistuje", "enabled": True})
    assert error.value.status == 404 and error.value.code == "project_not_found"


def test_write_keeps_other_settings(service):
    folder = service.folder("draft")
    folder.update(settings={"agentAutonomy": {"full": True}})
    gate_setting.write(service, {"project": "draft", "enabled": True})
    settings = json.loads(folder.identity_file.read_text(encoding="utf-8"))["settings"]
    assert settings["agentAutonomy"] == {"full": True} and settings["brain"]["gate"] is True
