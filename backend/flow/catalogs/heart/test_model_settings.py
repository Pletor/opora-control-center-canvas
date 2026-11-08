"""Model srdce: výchozí hodnoty, zápis jako nová aktivní verze beze změny ostatních uzlů, neplatný alias."""
import pytest

from backend.flow import workflows
from backend.flow.catalogs.heart import model_settings, seed


def test_default_read(db):
    assert model_settings.read(db)["model"] == "haiku" and model_settings.read(db)["advisor"] == "opus"


def test_write_makes_new_active_version(db):
    workflow_id, before = seed.ensure_active(db)
    old = workflows.get_version(db, before)["graph"]
    result = model_settings.write(db, "sonnet", "fable")
    assert (result["model"], result["advisor"]) == ("sonnet", "fable")
    _, after = seed.ensure_active(db)
    assert after != before and workflows.get_version(db, before)["status"] == "retired"
    new = workflows.get_version(db, after)
    assert new["parent_version_id"] == before
    assert [n for n in new["graph"]["nodes"] if n["type"] != "model.claude"] == [n for n in old["nodes"] if n["type"] != "model.claude"]


def test_invalid_alias_keeps_active_version(db):
    _, before = seed.ensure_active(db)
    with pytest.raises(ValueError):
        model_settings.write(db, "gpt", "opus")
    assert seed.ensure_active(db)[1] == before


def test_effort_roundtrip_and_validation(db):
    assert model_settings.read(db)["effort"] is None and "max" in model_settings.read(db)["efforts"]
    assert model_settings.write(db, "haiku", "opus", "high")["effort"] == "high"
    assert model_settings.write(db, "haiku", "opus", "")["effort"] is None
    _, before = seed.ensure_active(db)
    with pytest.raises(ValueError):
        model_settings.write(db, "haiku", "opus", "extreme")
    assert seed.ensure_active(db)[1] == before
