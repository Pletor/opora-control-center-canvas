"""Seed Brainu: `opora-heart` z repa, `ponytail` z instalace (nebo přeskočený), idempotentní a bez přepisu."""
import json
import sqlite3

from backend.brain import registry, seed
from backend.brain.store import Store
from database.schema.project_schema import REGISTRY_SCHEMA


def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(REGISTRY_SCHEMA)
    return connection


def fake_ponytail(cache):
    for version, text in (("5.2.0", "stará"), ("5.10.1", "nová")):
        root = cache / version
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(
            {"name": "ponytail", "version": version, "hooks": ["./hooks/x.json"], "userConfig": {}}), encoding="utf-8")
        for name in ("ponytail", "ponytail-review"):
            (root / "skills" / name).mkdir(parents=True)
            (root / "skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n{text}\n", encoding="utf-8")
        (root / "skills" / "plugin.json").write_text("{}", encoding="utf-8")
        (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    return cache


def test_seed_without_ponytail_creates_heart_skills_once(tmp_path):
    conn = db()
    seed.ensure(conn, tmp_path, ponytail_cache=tmp_path / "chybi")
    ids = [artifact["id"] for artifact in registry.list_artifacts(conn)]
    assert ids == ["opora:brain:skill:heart", "opora:brain:skill:vyslech"]
    heart = registry.active(conn, "opora:brain:skill:heart")
    expected = (seed.SEED_DIR / "opora-heart" / "skills" / "heart" / "SKILL.md").read_text(encoding="utf-8")
    assert Store(tmp_path).read("opora-heart", heart["content_ref"], heart["version"]) == expected
    count = conn.execute("SELECT COUNT(*) FROM brain_artifact_versions").fetchone()[0]
    seed.ensure(conn, tmp_path, ponytail_cache=tmp_path / "chybi")
    assert conn.execute("SELECT COUNT(*) FROM brain_artifact_versions").fetchone()[0] == count == 2
    assert registry.active(conn, "opora:brain:skill:heart") == heart


def test_seed_keeps_a_brain_that_already_moved_on(tmp_path):
    conn, store = db(), Store(tmp_path)
    seed.ensure(conn, tmp_path, ponytail_cache=tmp_path / "chybi")
    newer = store.write("opora-heart", {"skills/heart/SKILL.md": "---\nname: heart\n---\nNovější\n"}, "úprava")
    seed.ensure(conn, tmp_path, ponytail_cache=tmp_path / "chybi")
    assert store.version("opora-heart") == newer  # seed obsah v Brainu nepřepíše
    assert registry.active(conn, "opora:brain:skill:heart")["version"] != newer  # nová verze jde přes registr


def test_seed_copies_installed_ponytail_skills_and_license(tmp_path):
    conn = db()
    seed.ensure(conn, tmp_path / "data", ponytail_cache=fake_ponytail(tmp_path / "cache"))
    active = registry.active(conn, "opora:brain:skill:ponytail")
    store = Store(tmp_path / "data")
    assert store.read("ponytail", active["content_ref"], active["version"]).endswith("nová\n")  # nejvyšší verze
    assert registry.active(conn, "opora:brain:skill:ponytail-review")["plugin"] == "ponytail"
    assert store.read("ponytail", "LICENSE", active["version"]) == "MIT License\n"
    manifest = json.loads(store.read("ponytail", ".claude-plugin/plugin.json", active["version"]))
    assert manifest == {"name": "ponytail", "version": "5.10.1", "license": "MIT"}  # bez háčků instalace


def test_seed_fills_missing_evals_without_a_new_artifact_version(tmp_path):
    conn, store = db(), Store(tmp_path)
    files = seed._files(seed.SEED_DIR / "opora-heart")
    old = store.write("opora-heart", {rel: text for rel, text in files.items() if not rel.startswith("evals/")},
                      "živý Brain před PR 7c")  # založený Brain bez sady evalu
    seed.ensure(conn, tmp_path, ponytail_cache=tmp_path / "chybi")
    assert registry.active(conn, "opora:brain:skill:heart")["version"] == old  # sada evalu není obsah skillu
    filled = store.version("opora-heart")
    assert filled != old
    assert store.read("opora-heart", "evals/ticket-s-kriteriem/prompt.md", filled) == \
        files["evals/ticket-s-kriteriem/prompt.md"]
    assert conn.execute("SELECT COUNT(*) FROM brain_artifact_versions").fetchone()[0] == 2
    edited = store.write("opora-heart", {"evals/ticket-s-kriteriem/prompt.md": "jiná sada\n"}, "ruční úprava")
    seed.ensure(conn, tmp_path, ponytail_cache=tmp_path / "chybi")
    assert store.version("opora-heart") == edited  # existující evals/ seed nepřepíše
