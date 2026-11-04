"""Idempotentní naplnění Brainu při startu (§3.4): pluginy `opora-heart` a `opora-control-center` z repa a `ponytail`
z instalace.

`opora-heart` leží v `seed/opora-heart/` (skilly `heart` = systémový prompt srdce, `vyslech` = postup výslechu, `proces-na-platne` = stavba plátna procesu),
`opora-control-center` v `seed/opora-control-center/` (skill práce s plátnem přes OporaHub, se skripty a jejich testy).
`ponytail` (MIT) se bere z nainstalovaného pluginu Claude Code (nejvyšší verze v cache), do Brainu jdou jeho skilly
a licence; když na stroji není, seed ho přeskočí a zaloguje. Plugin, který už v Brainu je, seed nepřepisuje, a artefakt
s aktivní verzí nechá být: další verze přicházejí přes registr (kandidát → eval → aktivace), ne ze seedu. Jedinou
výjimkou je chybějící `evals/` (zmrazená sada eval gate, `evaluate.py`): tu seed doplní commitem bez nové verze.
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
REPO_PLUGINS = ("opora-heart", "opora-control-center")
SKIP = {"__pycache__", ".pytest_cache"}  # stopy běhu testů skriptů, ne obsah pluginu


def _files(folder):
    return {path.relative_to(folder).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(folder.rglob("*")) if path.is_file() and not SKIP & set(path.parts)}


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


def _fill_evals(store, plugin, files):
    """Pluginu, který už v Brainu je a nemá `evals/`, doplní zmrazenou sadu ze seedu commitem bez nové verze artefaktu
    (sada evalu není obsah skillu). Existující `evals/` seed nemění."""
    evals = {relpath: text for relpath, text in files.items() if relpath.startswith("evals/")}
    if evals and not (store.root / "plugins" / plugin / "evals").is_dir():
        store.write(plugin, evals, f"seed: evals {plugin}")


def _fill_skills(store, plugin, files):
    """Nový skill repa na existující instalaci: celou jeho složku commitne do Brainu, aby aktivní verze měla co číst.
    Skill, který v Brainu už je, seed nepřepisuje (změny jdou přes registr)."""
    base = store.root / "plugins" / plugin
    new = {rel.split("/")[1] for rel in files
           if rel.count("/") == 2 and rel.startswith("skills/") and rel.endswith("/SKILL.md") and not (base / rel).is_file()}
    added = {rel: text for rel, text in files.items() if rel.startswith("skills/") and rel.split("/")[1] in new}
    if added:
        return store.write(plugin, added, f"seed: skill {', '.join(sorted(new))}")
    return None


def _register(db, store, plugin, files):
    sha = store.version(plugin)
    if sha is None:
        sha = store.write(plugin, files, MESSAGE.format(plugin=plugin))
    else:
        _fill_evals(store, plugin, files)
        sha = _fill_skills(store, plugin, files) or sha  # evals nejsou obsah skillu, verzi skillů nemění
    for relpath in sorted(files):
        parts = relpath.split("/")
        if len(parts) != 3 or parts[0] != "skills" or parts[2] != "SKILL.md":
            continue
        artifact = registry.ensure_artifact(db, "skill", plugin, parts[1])
        if registry.active(db, artifact) is None:
            registry.activate(db, registry.add_version(db, artifact, sha, relpath))


def ensure(db, data_root, ponytail_cache=None):
    """Pluginy z repa a `ponytail` v Brainu s artefakty skillů a první verzí `active`; podruhé nic nemění."""
    store = Store(data_root)
    for plugin in REPO_PLUGINS:
        _register(db, store, plugin, _files(SEED_DIR / plugin))
    ponytail = ponytail_files(ponytail_cache)
    if ponytail is None:
        LOGGER.info("Brain: ponytail není nainstalovaný (%s), seed ho přeskočil.", ponytail_cache or PONYTAIL_CACHE)
        return
    _register(db, store, "ponytail", ponytail)
