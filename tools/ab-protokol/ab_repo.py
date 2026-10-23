"""Dočasné složky a malý git repozitář, do kterého skriptovaný agent opravdu commituje."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class Repo:
    """Malý git repozitář, do kterého skriptovaný agent opravdu commituje (úroveň „kód existuje“)."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        git(self.path, "init", "-q", "-b", "main")
        git(self.path, "config", "user.name", "sim")
        git(self.path, "config", "user.email", "sim@example.invalid")
        git(self.path, "config", "commit.gpgsign", "false")
        (self.path / "README.md").write_text("ample sim\n", encoding="utf-8")
        git(self.path, "add", ".")
        git(self.path, "commit", "-q", "-m", "initial")

    def commit(self, card_index, step_id, title):
        name = self.path / "src" / f"card{card_index}_{step_id}.py"
        name.parent.mkdir(exist_ok=True)
        name.write_text(f"# {title}\nVALUE = {card_index * 100 + len(step_id)}\n", encoding="utf-8")
        git(self.path, "add", ".")
        git(self.path, "commit", "-q", "-m", f"step {step_id}: {title}")
        return git(self.path, "rev-parse", "HEAD")

    def exists(self, commit):
        try:
            git(self.path, "cat-file", "-e", commit + "^{commit}")
            return True
        except subprocess.CalledProcessError:
            return False


def tmpdir(prefix):
    """Dočasná složka; `AB_PROTOKOL_TMP` ji může přesměrovat (např. na disk s volným místem)."""
    return Path(tempfile.mkdtemp(prefix=prefix, dir=os.environ.get("AB_PROTOKOL_TMP") or None))


def sweep_previous():
    """Smaže zbytky dřívějších běhů (SQLite drží soubory do konce procesu, takže úklid dojede až příště)."""
    import shutil

    base = Path(os.environ.get("AB_PROTOKOL_TMP") or tempfile.gettempdir())
    for path in list(base.glob("ab-legacy-*")) + list(base.glob("ab-hub-*")):
        shutil.rmtree(path, ignore_errors=True)


def cleanup(path):
    """Smaže dočasnou instanci včetně souborů gitu jen ke čtení (Windows)."""
    import shutil
    import stat

    def writable(func, target, _info):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            LEFTOVERS.add(Path(path))  # SQLite drží soubor do úklidu procesu; smaže se na konci běhu
    shutil.rmtree(path, onerror=writable)


LEFTOVERS: set = set()


def final_cleanup():
    import gc
    import shutil

    gc.collect()
    for path in list(LEFTOVERS):
        shutil.rmtree(path, ignore_errors=True)
        LEFTOVERS.discard(path)
