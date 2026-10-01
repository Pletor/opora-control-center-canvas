"""Registr rolí agenta: verzovaná data v library/agent-roles.json, jen ke čtení."""

import json

import pytest

from backend.memory import roles


def test_shipped_registry_has_the_expected_roles():
    ids = roles.role_ids()
    assert ids == (
        "role-frontend", "role-backend", "role-db", "role-cloud",
        "role-cache", "role-security", "role-tests", "role-architect",
    )
    assert roles.role("role-db")["label"] == "Databáze"
    assert roles.role("role-frontend")["description"]
    assert roles.role("role-nikdo") is None


def test_every_role_is_a_czech_label_with_a_description():
    for item in roles.load():
        assert set(item) == {"id", "label", "description"}
        assert item["label"].strip() and item["description"].strip()


def write(tmp_path, payload):
    path = tmp_path / "agent-roles.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_invalid_id_shape_is_refused(tmp_path):
    path = write(tmp_path, {"roles": [{"id": "frontend", "label": "F", "description": "d"}]})
    with pytest.raises(ValueError, match="role-"):
        roles.load(path)


def test_duplicate_ids_are_refused(tmp_path):
    item = {"id": "role-a", "label": "A", "description": "d"}
    path = write(tmp_path, {"roles": [item, dict(item)]})
    with pytest.raises(ValueError, match="[Dd]uplicitní"):
        roles.load(path)


def test_broken_json_and_unknown_fields_are_refused_not_guessed(tmp_path):
    path = tmp_path / "agent-roles.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        roles.load(path)
    path = write(tmp_path, {"roles": [{"id": "role-a", "label": "A", "description": "d", "extra": 1}]})
    with pytest.raises(ValueError):
        roles.load(path)
    path = write(tmp_path, {"items": []})
    with pytest.raises(ValueError):
        roles.load(path)


def test_empty_registry_is_refused(tmp_path):
    with pytest.raises(ValueError):
        roles.load(write(tmp_path, {"roles": []}))


def test_reload_picks_up_a_changed_file(tmp_path):
    path = write(tmp_path, {"roles": [{"id": "role-a", "label": "A", "description": "d"}]})
    assert [item["id"] for item in roles.load(path)] == ["role-a"]
    write(tmp_path, {"roles": [{"id": "role-b", "label": "B", "description": "d"}]})
    assert [item["id"] for item in roles.load(path)] == ["role-b"]
