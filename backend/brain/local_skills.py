"""Skilly Brainu pro lokální relace Claude Code v repu OPORA (§3.4: `SKILL.md` se do relace jen generuje).

Při startu aplikace (`start`, po seedu Brainu) se aktivní verze skillu vyexportuje z gitu Brainu do
`.claude/skills/<skill>/` v repu: celý adresář se přepíše a soubory jsou jen ke čtení. Cesta je v `.gitignore`;
zdroj je Brain (seed v `backend/brain/seed/`), úprava v generované kopii se dalším startem ztratí.
"""

import logging
import os
import shutil
import stat
import zipfile
from pathlib import Path

from backend.brain import registry, seed
from backend.brain.store import Store

LOGGER = logging.getLogger(__name__)
REPO_SKILLS = Path(__file__).resolve().parents[2] / ".claude" / "skills"
SKILLS = ("opora-control-center",)
ENV = "OPORA_BRAIN_LOCAL_SKILLS"


def _clear(target):
    if target.exists():
        for path in target.rglob("*"):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | (stat.S_IEXEC if path.is_dir() else 0))
        shutil.rmtree(target)


def generate(db, data_root, skills_dir=REPO_SKILLS, skills=SKILLS):
    """Aktivní verze skillů do `skills_dir/<skill>/` (přepíše celý adresář, soubory read-only). Vrátí zapsané skilly;
    skill bez aktivní verze přeskočí."""
    store, written = Store(data_root), []
    for name in skills:
        active = registry.active(db, f"opora:brain:skill:{name}")
        if active is None:
            LOGGER.info("Brain: skill %s nemá aktivní verzi, do %s se negeneruje.", name, skills_dir)
            continue
        prefix = f"skills/{name}/"
        target = Path(skills_dir) / name
        _clear(target)
        with zipfile.ZipFile(store.export(active["plugin"], active["version"])) as archive:
            for item in archive.infolist():
                if item.is_dir() or not item.filename.startswith(prefix):
                    continue
                path = target / item.filename[len(prefix):]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(item))
                os.chmod(path, stat.S_IREAD)
        written.append(name)
    return written


def start(service):
    """Seed Brainu a generované skilly v repu; v testech vypnuto (`OPORA_BRAIN_LOCAL_SKILLS=0`)."""
    if os.environ.get(ENV) == "0":
        return []
    try:
        with service.registry_lock:
            seed.ensure(service.db, service.root)
            return generate(service.db, service.root)
    except OSError:  # zamčený soubor v repu nesmí shodit start aplikace
        LOGGER.exception("Brain: generování skillů do %s selhalo.", REPO_SKILLS)
        return []
