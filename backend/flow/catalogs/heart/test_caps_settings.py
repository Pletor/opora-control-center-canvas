"""Stropy srdce: výchozí hodnoty, zápis jako nová aktivní verze, hodnota mimo meze se odmítne a verzi nemění."""
import pytest

from backend.flow.catalogs.heart import caps_settings, seed


def test_default_read(db):
    caps = caps_settings.read(db)
    assert (caps["per_hour"], caps["per_project"], caps["rate_sleep_seconds"]) == (6, 1, 900)


def test_write_makes_new_active_version(db):
    _, before = seed.ensure_active(db)
    assert caps_settings.write(db, {"per_hour": 12})["per_hour"] == 12
    _, after = seed.ensure_active(db)
    assert after != before and caps_settings.read(db)["per_project"] == 1


@pytest.mark.parametrize("values", [{"per_hour": 0}, {"per_hour": "12"}, {"per_hour": True}, {"nope": 1}, {}])
def test_invalid_value_keeps_active_version(db, values):
    _, before = seed.ensure_active(db)
    with pytest.raises(ValueError):
        caps_settings.write(db, values)
    assert seed.ensure_active(db)[1] == before
