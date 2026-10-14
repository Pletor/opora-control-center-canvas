"""Přesun datové složky aplikace (registry.sqlite, projekty, worktrees) jinam, třeba mimo repozitář.

    uv run python tools/move_data_root.py <stará_složka> <nová_složka> [--dry-run]

Backend musí stát. Nástroj zapíše WAL do databází, složku přesune, přepíše absolutní cesty, které
začínají starou složkou (registr, project.json, archiv odpojených projektů, odkazy Git worktree),
a do opora.local.toml zapíše novou `data`. Próza v kartách a zprávách se nepřepisuje.
Záznam starých a nových hodnot zůstane v `<nová_složka>/move-data-root.log.json`.
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.opora import CONFIG, LOCAL_CONFIG, load_config, port_free, resolve

LOG_NAME = "move-data-root.log.json"
# Sloupce registru, které drží absolutní cestu do datové složky.
REGISTRY_COLUMNS = (("projects", "repo"), ("project_sources", "source_path"), ("workspaces", "directory"))
GIT = ["git", "-c", "core.longpaths=true", "-c", "core.fsmonitor=false"]


def moved(value, old, new):
    """Hodnota s novou složkou, nebo None, když cesta nezačíná starou složkou.
    Na Windows bez ohledu na velikost písmen a druh lomítek."""
    if not isinstance(value, str) or not value:
        return None
    text = os.path.normpath(value)
    base = os.path.normpath(str(old))
    head, tail = os.path.normcase(text), os.path.normcase(base)
    if head == tail:
        return str(new)
    if head.startswith(tail.rstrip(os.sep) + os.sep):
        return str(new) + text[len(base.rstrip(os.sep)):]
    return None


def moved_json(value, old, new):
    """Kopie JSON hodnoty s přepsanými řetězci cest; počet změn vrací zvlášť."""
    if isinstance(value, dict):
        pairs = [(key, moved_json(item, old, new)) for key, item in value.items()]
        return {key: item for key, (item, _) in pairs}, sum(count for _, (_, count) in pairs)
    if isinstance(value, list):
        items = [moved_json(item, old, new) for item in value]
        return [item for item, _ in items], sum(count for _, count in items)
    result = moved(value, old, new)
    return (value, 0) if result is None else (result, 1)


def connect(path, readonly):
    if readonly:
        return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
    return sqlite3.connect(path)


def registry_changes(db, old, new):
    changes = []
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, column in REGISTRY_COLUMNS + (("archived_projects", "snapshot"),):
        if table not in tables or column not in {row[1] for row in db.execute(f"PRAGMA table_info({table})")}:
            continue
        for rowid, value in db.execute(f"SELECT rowid, {column} FROM {table}"):
            if column == "snapshot":
                try:
                    data, count = moved_json(json.loads(value), old, new)
                except (TypeError, ValueError):
                    continue
                after = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if count else None
            else:
                after = moved(value, old, new)
            if after is not None and after != value:
                changes.append({"where": f"registry.sqlite {table}.{column}", "rowid": rowid, "old": value, "new": after})
    return changes


def identity_changes(root, old, new):
    changes = []
    for file in sorted((root / "projects").glob("*/project.json")):
        identity = json.loads(file.read_text(encoding="utf-8"))
        value = (identity.get("source") or {}).get("value")
        after = moved(value, old, new)
        if after is not None and after != value:
            changes.append({"where": str(file.relative_to(root)), "old": value, "new": after})
    return changes


def worktree_links(root, old, new):
    """Odkazy `.git/worktrees/*/gitdir` v repozitářích projektů: (repozitář, stará, nová cesta worktree)."""
    links = []
    for gitdir in sorted((root / "projects").glob("*/main/.git/worktrees/*/gitdir")):
        value = gitdir.read_text(encoding="utf-8").strip()
        worktree = str(Path(value).parent)
        links.append({"where": str(gitdir.relative_to(root)), "repo": str(gitdir.parents[3]),
                      "old": worktree, "new": moved(worktree, old, new) or worktree})
    return links


def set_toml_value(text, section, key, value):
    """Text TOML s `key = "value"` v sekci; zbytek souboru (komentáře, jiné sekce) zůstane."""
    lines = text.splitlines()
    entry = f'{key} = {json.dumps(value)}'
    header = next((i for i, line in enumerate(lines) if line.split("#")[0].strip() == f"[{section}]"), None)
    if header is None:
        lines += ([""] if lines and lines[-1].strip() else []) + [f"[{section}]", entry]
    else:
        end = next((i for i in range(header + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
        found = next((i for i in range(header + 1, end) if lines[i].split("=")[0].strip() == key), None)
        if found is None:
            lines.insert(header + 1, entry)
        else:
            lines[found] = entry
    result = "\n".join(lines) + "\n"
    tomllib.loads(result)
    return result


def config_sections(config, base, old):
    """Sekce opory ([app], [profiles.*]), jejichž `data` ukazuje na starou složku."""
    sections = []
    candidates = [("app", config.get("app", {}))] + [
        (f"profiles.{name}", profile) for name, profile in config.get("profiles", {}).items()]
    for name, values in candidates:
        if "data" in values and os.path.normcase((base / values["data"]).resolve()) == os.path.normcase(old):
            sections.append(name)
    return sections


def refuse(old, new, config):
    settings = resolve(config)
    if not port_free(settings["host"], settings["port"]):
        return f"Port {settings['port']} je obsazený: nejdřív zastavte backend (uv run opora)."
    if not (old / "registry.sqlite").is_file():
        return f"{old} neobsahuje registry.sqlite; není to datová složka aplikace."
    if new == old or old in new.parents:
        return "Nová složka nesmí být stará složka ani ležet uvnitř ní."
    if new.exists() and (not new.is_dir() or any(new.iterdir())):
        return f"{new} existuje a není prázdná."
    return None


def checkpoint(root):
    for file in sorted(root.rglob("*.sqlite")):
        db = sqlite3.connect(file)
        try:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            db.close()


def apply(root, changes, links):
    db = sqlite3.connect(root / "registry.sqlite")
    try:
        with db:
            for change in changes:
                if change["where"].startswith("registry.sqlite "):
                    table, column = change["where"].split(" ", 1)[1].split(".")
                    db.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?", (change["new"], change["rowid"]))
    finally:
        db.close()
    for change in changes:
        if change["where"].endswith("project.json"):
            file = root / change["where"]
            identity = json.loads(file.read_text(encoding="utf-8"))
            identity["source"]["value"] = change["new"]
            temp = file.with_suffix(".json.tmp")
            temp.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, file)
    for repo in sorted({link["repo"] for link in links}):
        paths = [link["new"] for link in links if link["repo"] == repo]
        result = subprocess.run(GIT + ["-C", repo, "worktree", "repair", *paths], capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"git worktree repair v {repo} selhal: {result.stderr.strip()}")


def run(old, new, *, dry_run=False, config_path=CONFIG, local_path=LOCAL_CONFIG, out=print):
    old, new = Path(old).resolve(), Path(new).resolve()
    config = load_config(config_path, local_path)
    reason = refuse(old, new, config)
    if reason:
        out(f"[move] odmítnuto: {reason}")
        return 1
    sections = config_sections(config, config_path.parent, old)
    local_before = local_path.read_text(encoding="utf-8") if local_path.exists() else ""
    local_after = local_before
    for section in sections:
        local_after = set_toml_value(local_after, section, "data", new.as_posix())
    if dry_run:
        db = connect(old / "registry.sqlite", readonly=True)
        try:
            changes = registry_changes(db, old, new) + identity_changes(old, old, new)
        finally:
            db.close()
        report(out, old, new, changes, worktree_links(old, old, new), sections, local_path, "změnilo by se")
        return 0
    checkpoint(old)
    new.parent.mkdir(parents=True, exist_ok=True)
    if new.exists():
        new.rmdir()
    shutil.move(str(old), str(new))
    log = new / LOG_NAME
    try:
        db = sqlite3.connect(new / "registry.sqlite")
        try:
            changes = registry_changes(db, old, new) + identity_changes(new, old, new)
        finally:
            db.close()
        links = worktree_links(new, old, new)
        log.write_text(json.dumps({"oldRoot": str(old), "newRoot": str(new), "changes": changes, "worktrees": links,
                                   "localConfig": str(local_path), "localConfigBefore": local_before},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        apply(new, changes, links)
        if local_after != local_before:
            local_path.write_text(local_after, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 – po přesunu musí člověk vždy dostat návod k návratu
        out(f"[move] CHYBA po přesunu: {exc}")
        out("[move] Návrat: spusťte obráceně  uv run python tools/move_data_root.py "
            f'"{new}" "{old}"  (vrátí složku i cesty, které už začínají novou složkou).')
        out(f"[move] Ručně: přesuňte {new} zpět na {old}; staré hodnoty jsou v {log}"
            f" (pole changes[].old, localConfigBefore) a opora.local.toml vraťte podle localConfigBefore.")
        return 2
    report(out, old, new, changes, links, sections, local_path, "změněno")
    return 0


def report(out, old, new, changes, links, sections, local_path, verb):
    out(f"[move] {old} -> {new}")
    for change in changes:
        out(f"[move] {verb}: {change['where']}: {change['old']} -> {change['new']}")
    for link in links:
        out(f"[move] {verb}: worktree {link['where']}: {link['old']} -> {link['new']}")
    for section in sections:
        out(f'[move] {verb}: {local_path.name} [{section}] data = "{new.as_posix()}"')
    if not sections:
        out("[move] pozor: žádná sekce opora.toml neukazuje na starou složku; opora.local.toml beze změny.")
    out(f"[move] celkem {len(changes)} hodnot, {len(links)} worktree, {len(sections)} sekcí konfigurace.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Přesune datovou složku Opora a přepíše v ní absolutní cesty.")
    parser.add_argument("old_root")
    parser.add_argument("new_root")
    parser.add_argument("--dry-run", action="store_true", help="jen vypsat, co by se změnilo")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    return run(args.old_root, args.new_root, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
