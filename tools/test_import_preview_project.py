import importlib.util
import sqlite3
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "import-preview-project.py"


def load():
    spec = importlib.util.spec_from_file_location("import_preview_project", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # skript bez __main__ nic nespustí
    return module


def test_registry_backup_uses_backup_api_and_keeps_wal_only_rows(tmp_path):
    """Karta P3: registr je ve WAL (P2); záloha před importem nesmí minout potvrzené řádky z -wal."""
    module = load()
    registry = tmp_path / "production" / "registry.sqlite"
    registry.parent.mkdir()
    live = sqlite3.connect(registry)
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("PRAGMA wal_autocheckpoint=0")
    with live:
        live.execute("CREATE TABLE projects(id TEXT)")
        live.execute("INSERT INTO projects VALUES('4b38')")
    backup = module.backup_registry(registry, tmp_path / "backups", "4b38182c5b04", "20261010T000000Z")
    assert backup == tmp_path / "backups" / "registry-pre-import-4b38182c-20261010T000000Z.sqlite"
    copy = sqlite3.connect(backup)
    assert copy.execute("SELECT id FROM projects").fetchall() == [("4b38",)]
    copy.close()
    live.close()
    assert "shutil.copy2(registry" not in SCRIPT.read_text(encoding="utf-8")
