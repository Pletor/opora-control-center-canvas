"""Úložiště Brainu: git repozitář `<datový kořen>/brain/` ve tvaru lokálního marketplace (§3.4).

Rozvržení: `.claude-plugin/marketplace.json` (name `opora-brain`) a `plugins/<plugin>/…` (`.claude-plugin/plugin.json`,
`skills/<skill>/SKILL.md`, případně `evals/`). Verze pluginu je SHA posledního commitu, který ho měnil. Commity píše
autor „OPORA Brain“. Export verze je zip pluginu v `<datový kořen>/brain-pins/<plugin>@<sha12>.zip` pro `--plugin-dir`.
"""

import json
import re
import threading
from pathlib import Path

from backend.integrations.gitio import git

MARKETPLACE = "opora-brain"
AUTHOR = ("-c", "user.name=OPORA Brain", "-c", "user.email=brain@opora.local")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_LOCK = threading.Lock()


def _plugin(name):
    if not NAME.fullmatch(name or ""):
        raise ValueError(f"Neplatné jméno pluginu {name!r}.")
    return name


def _relpath(relpath):
    parts = Path(relpath).parts
    if not parts or Path(relpath).is_absolute() or ".." in parts:
        raise ValueError(f"Neplatná cesta v pluginu {relpath!r}.")
    return "/".join(parts)


class Store:
    def __init__(self, data_root):
        self.root = Path(data_root) / "brain"
        self.pins = Path(data_root) / "brain-pins"

    def _git(self, *args, **kwargs):
        return git(self.root, *args, timeout=60, **kwargs)

    def _ensure(self):
        if not (self.root / ".git").exists():
            self.root.mkdir(parents=True, exist_ok=True)
            self._git("init", "-q")
            self._git("config", "core.autocrlf", "false")  # obsah 1:1 i v exportu (git archive), bez CRLF

    def _marketplace(self):
        plugins = sorted(path.name for path in (self.root / "plugins").iterdir() if path.is_dir())
        value = {"name": MARKETPLACE, "owner": {"name": "OPORA Brain"},
                 "plugins": [{"name": name, "source": f"./plugins/{name}"} for name in plugins]}
        path = self.root / ".claude-plugin" / "marketplace.json"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def write(self, plugin, files, message):
        """Zapíše soubory pluginu (`{relpath: text}`) a commitne je; beze změny jen vrátí poslední verzi pluginu."""
        plugin = _plugin(plugin)
        with _LOCK:
            self._ensure()
            base = self.root / "plugins" / plugin
            for relpath, text in files.items():
                path = base / _relpath(relpath)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8"))  # bez překladu konců řádků (Windows)
            self._marketplace()
            self._git("add", "-A", "--", f"plugins/{plugin}", ".claude-plugin")
            if self._git("diff", "--cached", "--quiet", optional=True) is None:  # kód 1 = staged změna
                self._git(*AUTHOR, "commit", "-q", "-m", message)
            return self.version(plugin)

    def version(self, plugin):
        """SHA posledního commitu, který plugin měnil; None, když plugin v Brainu není."""
        if not (self.root / ".git").exists():
            return None
        return self._git("log", "-1", "--format=%H", "--", f"plugins/{_plugin(plugin)}", optional=True) or None

    def read(self, plugin, relpath, sha):
        """Text souboru pluginu ve verzi `sha` (`git show sha:path`)."""
        if not re.fullmatch(r"[0-9a-f]{7,40}", sha or ""):
            raise ValueError(f"Neplatná verze {sha!r}.")
        data = self._git("show", f"{sha}:plugins/{_plugin(plugin)}/{_relpath(relpath)}", raw=True)
        return data.decode("utf-8")

    def export(self, plugin, sha):
        """Zip pluginu ve verzi `sha` (kořen zipu = kořen pluginu); existující zip vrátí beze změny."""
        plugin = _plugin(plugin)
        if not re.fullmatch(r"[0-9a-f]{12,40}", sha or ""):
            raise ValueError(f"Neplatná verze {sha!r}.")
        target = self.pins / f"{plugin}@{sha[:12]}.zip"
        with _LOCK:
            if not target.is_file():
                self.pins.mkdir(parents=True, exist_ok=True)
                partial = target.with_suffix(".part")
                self._git("archive", "--format=zip", "-o", str(partial), f"{sha}:plugins/{plugin}")
                partial.replace(target)
        return target
