"""Generované skilly lokálních relací: aktivní verze z Brainu, celý adresář přepsaný, soubory jen ke čtení."""
import os
import threading

from backend.brain import local_skills, registry, seed
from backend.brain.store import Store
from backend.brain.test_seed import db

SOURCE = seed.SEED_DIR / "opora-control-center" / "skills" / "opora-control-center"


def test_active_version_replaces_the_whole_generated_folder_read_only(tmp_path):
    conn, skills = db(), tmp_path / "repo" / ".claude" / "skills"
    seed.ensure(conn, tmp_path / "data", ponytail_cache=tmp_path / "chybi")
    stale = skills / "opora-control-center" / "stary.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("ruční úprava\n", encoding="utf-8")
    os.chmod(stale, 0o444)
    assert local_skills.generate(conn, tmp_path / "data", skills) == ["opora-control-center"]
    target = skills / "opora-control-center"
    assert not stale.exists()  # přepsaný celý adresář
    assert (target / "SKILL.md").read_text(encoding="utf-8") == (SOURCE / "SKILL.md").read_text(encoding="utf-8")
    assert (target / "scripts" / "opora_gate.py").is_file()
    assert not os.access(target / "SKILL.md", os.W_OK)
    newer = Store(tmp_path / "data").write("opora-control-center", {
        "skills/opora-control-center/SKILL.md": "---\nname: opora-control-center\n---\nNová\n"}, "nová verze")
    artifact = "opora:brain:skill:opora-control-center"
    registry.activate(conn, registry.add_version(conn, artifact, newer, "skills/opora-control-center/SKILL.md"))
    local_skills.generate(conn, tmp_path / "data", skills)  # read-only soubory nebrání přepisu
    assert (target / "SKILL.md").read_text(encoding="utf-8").endswith("Nová\n")


def test_start_is_off_in_tests_and_skips_a_skill_without_active_version(tmp_path):
    service = type("Service", (), {"db": db(), "root": tmp_path, "registry_lock": threading.RLock()})()
    assert local_skills.start(service) == []  # backend/conftest.py: OPORA_BRAIN_LOCAL_SKILLS=0
    assert local_skills.generate(service.db, tmp_path, tmp_path / "skills") == []
    assert not (tmp_path / "skills").exists()
