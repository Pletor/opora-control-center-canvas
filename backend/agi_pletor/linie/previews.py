"""Náhledy větví z Velínu (kontrakt §5): worktree větve + build + `tools/serve-preview.py` nad kopií dat.

Registr `<pletor>/linie/previews.json` `{slug: {slug, branch, project, worktree, data, port, pid, state, sha,
startedAt, url, log}}`; `state` je `building | running | failed | stopped`. Soubory náhledu leží v
`<pletor>/linie/previews/<slug>/` (`tree/`, `data/`, `build.log`, `server.log`). Main ani 8740 se nemění.
"""
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

from backend.integrations.gitio import git
from backend.paths import REPO_ROOT

FILE = "previews.json"
FIRST_PORT = 8790
PROTECTED = {8740, 8768, 8780}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LOCK = threading.Lock()
RUNNING = {}  # slug → Popen; po restartu serveru prázdné, stav se pak ověřuje portem


def slug(branch):
    return re.sub(r"[^a-z0-9-]+", "-", branch.lower()).strip("-")


def _root(folder):
    return Path(folder) / "linie"


def _read(folder):
    try:
        value = json.loads((_root(folder) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _save(folder, records):
    path = _root(folder) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _update(folder, name, **changes):
    with LOCK:
        records = _read(folder)
        records[name] = {**records.get(name, {}), **changes}
        _save(folder, records)
        return records[name]


def _listening(port):
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", int(port))) == 0


def free_port(taken=()):
    """První volný port od 8790; chráněné porty a porty jiných náhledů nikdy."""
    port = FIRST_PORT
    while port in PROTECTED or port in taken or _listening(port):
        port += 1
    return port


def _link_node_modules(tree):
    link, target = Path(tree) / "node_modules", REPO_ROOT / "node_modules"
    if link.exists() or link.is_symlink():
        return
    if os.name == "nt":  # symlink na Windows chce práva vývojáře; junction ne
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True,
                       capture_output=True, creationflags=NO_WINDOW)
    else:
        os.symlink(target, link, target_is_directory=True)


def _unlink_node_modules(tree):
    """Junction napřed: mazání stromu nesmí sáhnout do node_modules hlavního repozitáře."""
    link = Path(tree) / "node_modules"
    try:
        if link.is_symlink():
            os.unlink(link)
        else:
            os.rmdir(link)  # u junction smaže jen odkaz, cíl zůstane
    except OSError:
        pass


def _copy_data(data_root, project, data):
    data.mkdir(parents=True, exist_ok=True)
    source = Path(data_root) / "registry.sqlite"
    if source.exists():
        live, copy = sqlite3.connect(source), sqlite3.connect(data / "registry.sqlite")
        try:
            live.backup(copy)
        finally:
            live.close()
            copy.close()
    # shortcut: složka projektu se kopíruje souborově i s jeho sqlite (WAL jde s ní); při rozbitých
    # kopiích přejít na backup i u databáze projektu.
    shutil.copytree(Path(data_root) / "projects" / project, data / "projects" / project, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("maps", "worktrees"))
    # Brain je git repozitář s aktivními verzemi skillů srdce; bez něj server náhledu nenastartuje.
    for name in ("brain", "brain-pins"):
        if (Path(data_root) / name).is_dir():
            shutil.copytree(Path(data_root) / name, data / name, dirs_exist_ok=True)


def _build(tree, log):
    npm = "npm.cmd" if os.name == "nt" else "npm"
    with open(log, "wb") as out:
        return subprocess.run([npm, "run", "build"], cwd=tree, stdout=out, stderr=subprocess.STDOUT,
                              timeout=900, check=False, creationflags=NO_WINDOW).returncode == 0


def _spawn(tree, port, data, log):
    out = open(log, "wb")  # noqa: SIM115 – log drží běžící proces
    command = [sys.executable, "tools/serve-preview.py", "--port", str(port), "--data", str(data)]
    return subprocess.Popen(command, cwd=tree, stdout=out, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)


def _background(work):
    threading.Thread(target=work, daemon=True).start()


def start(folder, root, branch, project, data_root, now, *, build=_build, spawn=_spawn, run=_background):
    """Připraví worktree a kopii dat, zapíše `building` a na pozadí sestaví a spustí náhled."""
    exists = git(root, "rev-parse", "--verify", "-q", branch + "^{commit}", optional=True)
    if branch.startswith("-") or not exists:
        raise ValueError(f"Větev {branch} v repozitáři neexistuje.")
    name = slug(branch)
    if not name:
        raise ValueError("Z názvu větve nejde složit název náhledu.")
    if name in _read(folder):
        stop(folder, name)
    base = _root(folder) / "previews" / name
    tree, data = base / "tree", base / "data"
    git(root, "worktree", "prune")
    # Odpojená hlava: větev může být vybraná v jiném stromu (i v tom, ze kterého běží server).
    if (tree / ".git").exists():
        git(tree, "checkout", "--detach", branch, timeout=120)
    else:
        git(root, "worktree", "add", "--detach", str(tree), branch, timeout=300)
    _link_node_modules(tree)
    _copy_data(data_root, project, data)
    taken = {r.get("port") for key, r in _read(folder).items() if key != name and r.get("state") != "stopped"}
    port = free_port(taken)
    record = _update(folder, name, slug=name, branch=branch, project=project, worktree=str(tree),
                     data=str(data), port=port, pid=None, state="building",
                     sha=git(tree, "rev-parse", "HEAD"), startedAt=now,
                     url=f"http://127.0.0.1:{port}/?screen=pletor", log=str(base / "build.log"))

    def work():
        try:
            built = build(tree, base / "build.log")
        except (OSError, subprocess.SubprocessError):
            built = False
        if not built:
            _update(folder, name, state="failed")
            return
        process = spawn(tree, port, data, base / "server.log")
        RUNNING[name] = process
        _update(folder, name, pid=process.pid, state="running")

    run(work)
    return record


def _alive(record):
    process = RUNNING.get(record.get("slug"))
    if process is not None:
        return process.poll() is None
    # shortcut: po restartu serveru chybí Popen; běh se pozná jen podle portu, ne podle pid.
    return bool(record.get("port")) and _listening(record["port"])


def status(folder):
    """Záznamy registru se živě ověřeným stavem: `running`, který neběží, je `stopped`."""
    records = list(_read(folder).values())
    for record in records:
        if record.get("state") == "running" and not _alive(record):
            record["state"] = "stopped"
    return records


def stop(folder, name):
    record = _read(folder).get(name)
    if record is None:
        raise KeyError(name)
    process = RUNNING.pop(name, None)
    if process is not None:
        process.terminate()
    elif record.get("pid") and record.get("state") == "running" and _alive(record):
        try:
            os.kill(record["pid"], signal.SIGTERM)
        except OSError:
            pass
    return _update(folder, name, state="stopped")


def remove(folder, root, name):
    """Stop + smazat worktree i kopii dat; záznam zmizí z registru."""
    record = stop(folder, name)
    tree = Path(record.get("worktree") or _root(folder) / "previews" / name / "tree")
    _unlink_node_modules(tree)
    git(root, "worktree", "remove", "--force", str(tree), optional=True, timeout=120)
    shutil.rmtree(_root(folder) / "previews" / name, ignore_errors=True)
    git(root, "worktree", "prune", optional=True)
    with LOCK:
        records = _read(folder)
        records.pop(name, None)
        _save(folder, records)
    return {"slug": name, "removed": True}


def log(folder, name, limit=20000):
    """Konec build a server logu náhledu `{build, server}`."""
    if name not in _read(folder):
        raise KeyError(name)
    base = _root(folder) / "previews" / name

    def tail(file):
        try:
            return (base / file).read_text(encoding="utf-8", errors="replace")[-limit:]
        except OSError:
            return ""

    return {"build": tail("build.log"), "server": tail("server.log")}
