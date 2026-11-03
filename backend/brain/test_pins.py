"""Piny ticketu: výchozí ponytail a opora-control-center, ID artefaktu → aktivní pin, pin s verzí doslova, po pluginech, neznámé ID."""
import pytest

from backend.brain import pins, registry, seed
from backend.brain.test_seed import db, fake_ponytail


def seeded(tmp_path, ponytail=True):
    conn = db()
    seed.ensure(conn, tmp_path, ponytail_cache=fake_ponytail(tmp_path / "cache") if ponytail else tmp_path / "chybi")
    return conn


def test_default_pins_ponytail_and_control_center_when_they_exist(tmp_path):
    conn = seeded(tmp_path)
    ponytail = registry.active(conn, "opora:brain:skill:ponytail")
    found = pins.for_ticket(conn, [])
    assert found[0] == {"pin": ponytail["pin"], "plugin": "ponytail", "version": ponytail["version"],
                        "zip": f"/api/brain-registry/pins/ponytail@{ponytail['version'][:12]}.zip"}
    assert [item["plugin"] for item in found] == ["ponytail", "opora-control-center"]
    assert [item["plugin"] for item in pins.for_ticket(seeded(tmp_path / "bez", ponytail=False), [])] ==         ["opora-control-center"]  # každý výchozí pin jen, když je v registru


def test_artifact_ids_resolve_to_active_pins_grouped_by_plugin(tmp_path):
    conn = seeded(tmp_path)
    found = pins.for_ticket(conn, ["opora:brain:skill:vyslech", "opora:brain:skill:heart",
                                   "opora:brain:skill:ponytail-review"])
    assert [item["plugin"] for item in found] == ["opora-control-center", "opora-heart", "ponytail"]  # plugin = zip
    assert found[1]["pin"] == registry.active(conn, "opora:brain:skill:vyslech")["pin"]
    heart = registry.active(conn, "opora:brain:skill:heart")
    assert pins.for_ticket(conn, [heart["pin"]])[2]["version"] == heart["version"]  # pin s verzí doslova


def test_unknown_artifact_or_version_is_refused(tmp_path):
    conn = seeded(tmp_path)
    for ref in ("opora:brain:skill:nic", "opora:brain:skill:heart@" + "0" * 12):
        with pytest.raises(LookupError):
            pins.for_ticket(conn, [ref])
