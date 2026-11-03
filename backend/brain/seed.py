"""Idempotentní naplnění Brainu při startu (§3.4): plugin `opora-heart` z repa a `ponytail` z instalace.

`opora-heart` leží v `seed/opora-heart/` (skilly `heart` = systémový prompt srdce, `vyslech` = postup výslechu).
`ponytail` (MIT) se bere z nainstalovaného pluginu Claude Code (nejvyšší verze v cache), do Brainu jdou jeho skilly
a licence; když na stroji není, seed ho přeskočí a zaloguje. Plugin, který už v Brainu je, seed nepřepisuje, a artefakt
s aktivní verzí nechá být: další verze přicházejí přes registr (kandidát → eval → aktivace), ne ze seedu.
"""

import json
import logging
from pathlib import Path

from backend.brain import registry
from backend.brain.store import Store

LOGGER = logging.getLogger(__name__)
SEED_DIR = Path(__file__).resolve().parent / "seed"
PONYTAIL_CACHE = Path.home() / ".claude" / "plugins" / "cache" / "ponytail" / "ponytail"
MESSAGE = "seed: {plugin}"


def _files(folder):
    return {path.relative_to(folder).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(folder.rglob("*")) if path.is_file()}


def _version_key(path):
    return tuple(int(part) if part.isdigit() else 0 for part in path.name.split("."))


def ponytail_files(cache=None):
    """Skilly, licence a zúžený manifest nainstalovaného ponytailu; None, když plugin na stroji není.
    Manifest bez háčků a `userConfig`: Brain nese know-how (skilly), háčky instalace se nepřenášejí."""
    cache = Path(PONYTAIL_CACHE if cache is None else cache)
    versions = sorted((path for path in cache.iterdir() if (path / "skills").is_dir()), key=_version_key) \
        if cache.is_dir() else []
    if not versions:
        return None
    root = versions[-1]
    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    files = {f"skills/{rel}": text for rel, text in _files(root / "skills").items() if "/" in rel}
    files["LICENSE"] = (root / "LICENSE").read_text(encoding="utf-8")
    keep = {key: manifest[key] for key in ("name", "version", "description", "author") if key in manifest}
    files[".claude-plugin/plugin.json"] = json.dumps({**keep, "license": "MIT"}, ensure_ascii=False, indent=2) + "\n"
    return files


def _register(db, store, plugin, files):
    sha = store.version(plugin) or store.write(plugin, files, MESSAGE.format(plugin=plugin))
    for relpath in sorted(files):
        parts = relpath.split("/")
        if len(parts) != 3 or parts[0] != "skills" or parts[2] != "SKILL.md":
            continue
        artifact = registry.ensure_artifact(db, "skill", plugin, parts[1])
        if registry.active(db, artifact) is None:
            registry.activate(db, registry.add_version(db, artifact, sha, relpath))


def ensure(db, data_root, ponytail_cache=None):
    """Plugin `opora-heart` a `ponytail` v Brainu s artefakty skillů a první verzí `active`; podruhé nic nemění."""
    store = Store(data_root)
    _register(db, store, "opora-heart", _files(SEED_DIR / "opora-heart"))
    ponytail = ponytail_files(ponytail_cache)
    if ponytail is None:
        LOGGER.info("Brain: ponytail není nainstalovaný (%s), seed ho přeskočil.", ponytail_cache or PONYTAIL_CACHE)
        return
    _register(db, store, "ponytail", ponytail)
