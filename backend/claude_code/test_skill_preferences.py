import json

import pytest

from backend.claude_code.skill_preferences import SkillPreferences


def test_empty_until_saved_then_sorted_unique(tmp_path):
    prefs = SkillPreferences(tmp_path / "data")
    assert prefs.disabled() == []
    assert prefs.save_disabled(["user:b", "user:a", "user:b"]) == ["user:a", "user:b"]
    assert prefs.disabled() == ["user:a", "user:b"]
    assert json.loads((tmp_path / "data/claude-code-skills.json").read_text(encoding="utf-8")) == {"disabledSkills": ["user:a", "user:b"]}


def test_rejects_invalid_payloads_and_ignores_corrupt_file(tmp_path):
    prefs = SkillPreferences(tmp_path)
    with pytest.raises(ValueError):
        prefs.save_disabled("user:a")
    with pytest.raises(ValueError):
        prefs.save_disabled(["no-scope"])
    prefs.path.write_text("{not json", encoding="utf-8")
    assert prefs.disabled() == []
