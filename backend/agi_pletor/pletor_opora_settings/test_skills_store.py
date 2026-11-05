"""Dílna: skilly jako soubory – založení, čtení, zápis a odmítnutí cest mimo skill a cizích přípon."""
import os

import pytest

from backend.agi_pletor.pletor_opora_settings import skills_store, workshop


def test_sample_skill_is_listed():
    sample = next(s for s in skills_store.list_skills() if s["name"] == "restart-opora")
    assert sample["files"] == ["SKILL.md"] and "8740" in sample["description"]


def test_skills_for_pletor_and_heart_are_in_the_repo():
    pletor, heart = skills_store.skills_for("pletor"), skills_store.skills_for("srdce")
    assert "hloubkove-zadani" in pletor and "zadani-na-kanvas" in heart
    assert pletor["hloubkove-zadani"]["body"].startswith("\n# Hloubkové zadání") and "rozhovor" in pletor["hloubkove-zadani"]["description"]
    assert "restart-opora" not in pletor and "restart-opora" not in heart


def test_create_read_write(tmp_path):
    assert skills_store.create_skill(tmp_path, "novy-skill") == {"name": "novy-skill", "files": ["SKILL.md"]}
    with pytest.raises(FileExistsError):
        skills_store.create_skill(tmp_path, "novy-skill")
    text = skills_store.read_file(tmp_path, "novy-skill", "SKILL.md")["content"]
    assert "## Kdy použít" in text and "## Ověření" in text
    assert skills_store.list_skills(tmp_path) == [{"name": "novy-skill", "description": "", "agent": "", "files": ["SKILL.md"]}]
    skills_store.write_file(tmp_path, "novy-skill", "SKILL.md", "---\nname: novy-skill\nagent: srdce\ndescription: D\n---\n# Tělo\n")
    assert skills_store.skills_for("srdce", tmp_path) == {"novy-skill": {"description": "D", "body": "# Tělo\n"}}
    assert skills_store.skills_for("pletor", tmp_path) == {}

    assert skills_store.write_file(tmp_path, "novy-skill", "scripts/a.py", "print('č')\n") == {
        "path": "scripts/a.py", "bytes": 12}
    skills_store.write_file(tmp_path, "novy-skill", "SKILL.md", '---\nname: x\ndescription: "Popis."\n---\n')
    assert skills_store.list_skills(tmp_path)[0] == {
        "name": "novy-skill", "description": "Popis.", "agent": "", "files": ["SKILL.md", "scripts/a.py"]}


@pytest.mark.parametrize("path", ["../venku.md", "a/../../venku.md", "/etc/x.md", "C:/x.md", "a\\b.md", "x.exe",
                                  "scripts/x", ""])
def test_bad_paths_refused(tmp_path, path):
    skills_store.create_skill(tmp_path, "s")
    with pytest.raises(ValueError):
        skills_store.write_file(tmp_path, "s", path, "x")


def test_bad_name_content_unknown_and_symlink(tmp_path):
    with pytest.raises(ValueError):
        skills_store.create_skill(tmp_path, "Spatny_nazev")
    with pytest.raises(LookupError):
        skills_store.read_file(tmp_path, "neni", "SKILL.md")
    skills_store.create_skill(tmp_path, "s")
    with pytest.raises(LookupError):
        skills_store.read_file(tmp_path, "s", "neni.md")
    for content in ["a\0b", "x" * (skills_store.MAX_CONTENT + 1)]:
        with pytest.raises(ValueError):
            skills_store.write_file(tmp_path, "s", "a.md", content)
    try:
        os.symlink(tmp_path, tmp_path / "s" / "odkaz", target_is_directory=True)
    except OSError:
        pytest.skip("Symlink tady nejde vytvořit (Windows bez práv).")
    with pytest.raises(ValueError):
        skills_store.write_file(tmp_path, "s", "odkaz/x.md", "x")


def test_tool_create_read_save(tmp_path):
    assert workshop.create_tool(tmp_path, "nova") == {"name": "nova", "cases": 1}
    with pytest.raises(FileExistsError):
        workshop.create_tool(tmp_path, "nova")
    assert workshop.measure(tmp_path, "nova")["passed"] == 1
    tool = workshop.read_tool(tmp_path, "nova")
    assert "def run(vstup: dict) -> dict:" in tool["code"] and '"priklad"' in tool["cases"]
    code = "def run(vstup):\n    return {'n': vstup['n'] + 1}\n"
    cases = '[{"name": "a", "input": {"n": 1}, "expected": {"n": 2}}, {"name": "b", "input": {"n": 2}, "expected": {"n": 3}}]'
    assert workshop.save_tool(tmp_path, "nova", code, cases) == {"name": "nova", "cases": 2}
    assert workshop.read_tool(tmp_path, "nova") == {"name": "nova", "code": code, "cases": cases}
    for bad in ["{", "{}", '[{"name": "a"}]']:
        with pytest.raises(ValueError, match="Případy"):
            workshop.save_tool(tmp_path, "nova", code, bad)
    with pytest.raises(LookupError):
        workshop.save_tool(tmp_path, "neni", code, cases)
