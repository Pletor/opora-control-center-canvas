import json
import sqlite3

from backend.canvas.canvas_service import CanvasService
from backend.canvas.migrate_to_project_folders import migrate

LEGACY = """
CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT,repo TEXT,url TEXT,branch TEXT);
CREATE TABLE workspaces(id TEXT PRIMARY KEY,project_id TEXT,directory TEXT,branch TEXT,node_id TEXT,actor TEXT,base_sha TEXT);
CREATE TABLE drafts(id TEXT PRIMARY KEY,graph TEXT);
CREATE TABLE jobs(id TEXT PRIMARY KEY,kind TEXT,status TEXT,message TEXT,project_id TEXT,updated_at TEXT);
CREATE TABLE project_sources(project_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_path TEXT);
CREATE TABLE project_settings(project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, goal TEXT NOT NULL, platform TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, budget_seconds INTEGER NOT NULL);
CREATE TABLE builtin_project_metadata(project_id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE node_text_revisions(project_id TEXT, workspace_id TEXT, node_id TEXT, revision INTEGER, text TEXT NOT NULL, saved_at TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id,node_id,revision));
CREATE TABLE drawing_revisions(project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, layer_id TEXT NOT NULL, revision INTEGER NOT NULL, scene TEXT NOT NULL, saved_at TEXT NOT NULL, PRIMARY KEY(project_id, workspace_id, layer_id, revision));
CREATE TABLE archived_projects(project_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, archived_at TEXT NOT NULL);
INSERT INTO projects VALUES('aaaa','ample','/data/projects/aaaa/main','https://github.com/Pletor/ample','main');
INSERT INTO projects VALUES('bbbb','ample','/data/projects/bbbb/main','https://github.com/Pletor/ample','main');
INSERT INTO projects VALUES('cccc','Local','','','');
INSERT INTO project_sources VALUES('cccc','local','C:/src/local');
INSERT INTO workspaces VALUES('w1','aaaa','/data/projects/aaaa/workspaces/w1','work/w1','n1','me','sha');
INSERT INTO drafts VALUES('draft','{"nodes":[],"edges":[]}');
INSERT INTO drafts VALUES('cccc','{"nodes":[{"id":"x"}],"edges":[]}');
INSERT INTO builtin_project_metadata VALUES('draft','Můj návrh');
INSERT INTO project_settings VALUES('aaaa',2,'Cíl ample','web','','',0);
INSERT INTO node_text_revisions VALUES('draft','draft','n1',1,'text draft','t');
INSERT INTO node_text_revisions VALUES('cccc','draft','n1',1,'text local','t');
INSERT INTO drawing_revisions VALUES('draft','draft','',1,'{"elements":[]}','t');
INSERT INTO jobs VALUES('j1','clone','complete','ok','aaaa','t');
"""


def legacy_root(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    db = sqlite3.connect(root / "canvas.sqlite")
    db.executescript(LEGACY)
    db.commit()
    db.close()
    return root


def test_migration_splits_central_db_into_project_folders(tmp_path):
    root = legacy_root(tmp_path)
    result = migrate(root)
    assert result["migrated"] is True and result["projects"] == 4
    assert result["merged"] == [("aaaa", "bbbb")]
    assert not (root / "canvas.sqlite").exists() and list(root.glob("canvas.sqlite.migrated-*"))

    registry = sqlite3.connect(root / "registry.sqlite")
    assert {r[0] for r in registry.execute("SELECT id FROM projects")} == {"aaaa", "bbbb", "cccc"}
    assert registry.execute("SELECT project_id FROM archived_projects").fetchall() == [("bbbb",)]
    assert registry.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 1
    assert registry.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1

    for pid in ("draft", "aaaa", "bbbb", "cccc"):
        identity = json.loads((root / "projects" / pid / "project.json").read_text(encoding="utf-8"))
        assert identity["id"] == pid
    assert json.loads((root / "projects/draft/project.json").read_text(encoding="utf-8"))["name"] == "Můj návrh"
    assert json.loads((root / "projects/cccc/project.json").read_text(encoding="utf-8"))["source"] == {"kind": "local", "value": "C:/src/local", "branch": ""}
    assert json.loads((root / "projects/aaaa/project.json").read_text(encoding="utf-8"))["source"]["kind"] == "git"

    draft = sqlite3.connect(root / "projects/draft/project.sqlite")
    assert draft.execute("SELECT text FROM node_text_revisions").fetchall() == [("text draft",)]
    assert draft.execute("SELECT COUNT(*) FROM drawing_revisions").fetchone()[0] == 1
    local = sqlite3.connect(root / "projects/cccc/project.sqlite")
    assert local.execute("SELECT text FROM node_text_revisions").fetchall() == [("text local",)]
    assert local.execute("SELECT graph FROM drafts WHERE id='cccc'").fetchone()[0] == '{"nodes":[{"id":"x"}],"edges":[]}'
    ample = sqlite3.connect(root / "projects/aaaa/project.sqlite")
    assert ample.execute("SELECT revision,goal FROM project_settings").fetchall() == [(2, "Cíl ample")]
    assert ample.execute("SELECT COUNT(*) FROM node_text_revisions").fetchone()[0] == 0


def test_migration_runs_once_and_service_reads_migrated_data(tmp_path):
    root = legacy_root(tmp_path)
    service = CanvasService(root)
    try:
        assert migrate(root) == {"migrated": False}
        bootstrap = service.bootstrap()
        assert {p["id"] for p in bootstrap["projects"]} == {"aaaa", "cccc"}
        assert bootstrap["draft"]["name"] == "Můj návrh"
        assert service.view("cccc", "draft")["graph"]["nodes"] == [{"id": "x"}]
        assert service.texts.read(("draft", "draft", "n1"))["text"] == "text draft"
        assert service.project_hub.settings("aaaa")["revision"] == 2
        assert service.folder("cccc").exists()
    finally:
        service.close()


def test_fresh_root_needs_no_migration(tmp_path):
    assert migrate(tmp_path / "empty") == {"migrated": False}
    service = CanvasService(tmp_path / "empty")
    try:
        assert (tmp_path / "empty/registry.sqlite").exists()
        assert service.view("draft", "draft")["graph"] == {"nodes": [], "edges": []}
        assert (tmp_path / "empty/projects/draft/project.sqlite").exists()
    finally:
        service.close()
