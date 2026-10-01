"""Přenese jeden projekt ze starého náhledového canvas.sqlite do produkčního datového kořene.

Použití (z kořene repozitáře):
    uv run python tools/import-preview-project.py --project 4b38182c5b04482bb00e0f3d3ae55656
Volitelně: --preview .data/preview/canvas.sqlite  --production .data/production

Postup: záloha registry.sqlite → migrace KOPIE náhledové databáze do dočasné složky →
kopie složky projektu do production/projects/<id> → zápis řádků projects a project_sources
do registru. Náhledová databáze ani ostatní projekty se nemění. Existující cíl se nepřepisuje.
"""  # noqa: N999 - spouštěcí skript, název se spojovníkem je záměrný

import argparse
import shutil
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.canvas.migrate_to_project_folders import migrate  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True, help="ID projektu v náhledové databázi")
parser.add_argument("--preview", default=".data/preview/canvas.sqlite")
parser.add_argument("--production", default=".data/production")
args = parser.parse_args()

preview = Path(args.preview).resolve()
production = Path(args.production).resolve()
registry = production / "registry.sqlite"
target = production / "projects" / args.project
if not preview.exists():
    sys.exit(f"náhledová databáze {preview} neexistuje")
if not registry.exists():
    sys.exit(f"produkční registr {registry} neexistuje (starý formát dat?)")
if target.exists():
    sys.exit(f"cíl {target} už existuje; nic se nepřepisuje")

stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
backups = production.parent / "backups"
backups.mkdir(exist_ok=True)
backup = backups / f"registry-pre-import-{args.project[:8]}-{stamp}.sqlite"
shutil.copy2(registry, backup)
print("záloha registru:", backup)

with tempfile.TemporaryDirectory() as temp:
    work = Path(temp)
    shutil.copy2(preview, work / "canvas.sqlite")
    result = migrate(work)
    if not result.get("migrated"):
        sys.exit("migrace kopie náhledu se neprovedla")
    source_folder = work / "projects" / args.project
    if not source_folder.exists():
        sys.exit(f"projekt {args.project} v náhledové databázi není")
    temp_registry = sqlite3.connect(work / "registry.sqlite")
    project = temp_registry.execute("SELECT id,name,repo,url,branch FROM projects WHERE id=?", (args.project,)).fetchone()
    source = temp_registry.execute(
        "SELECT project_id,source_kind,source_path FROM project_sources WHERE project_id=?", (args.project,)
    ).fetchone()
    temp_registry.close()
    if project is None:
        sys.exit("projekt nemá řádek v registru náhledu")
    shutil.copytree(source_folder, target)
    print("složka projektu:", target)

db = sqlite3.connect(registry)
with db:
    db.execute("INSERT INTO projects(id,name,repo,url,branch) VALUES(?,?,?,?,?)", project)
    if source is not None:
        db.execute("INSERT INTO project_sources(project_id,source_kind,source_path) VALUES(?,?,?)", source)
db.close()
print("zaregistrováno:", project[1], "|", (source[1] if source else "git"), (source[2] if source else project[3]))
print("Hotovo. Běžící server na 8740 čte registr při každém požadavku; projekt se objeví po obnovení stránky.")
