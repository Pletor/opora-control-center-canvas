"""Účty Codexu přes codex-swap (https://github.com/aneym/codex-swap, MIT, alfa 0.1.5): čtení, přepnutí, přidání.

Tvar sekce je stejný jako u `cswap.read()`, aby UI použilo tytéž dílky. codex-swap nemá `list --json`, proto:
aktivní slot z textu `codex-swap status` (`Active: slot N` / `unmanaged` / `No auth.json`), e-maily a plán ze
`~/.codex-swap/sequence.json` (bez tokenů), využití z `codex-swap usage --json` (jen z lokálních běhů Codexu).
`auth.json` Pletor nikdy neotevírá. Nikdy `codex logout` (odvolá refresh tokeny a zabije ostatní sloty) ani mazání
`auth.json`; z OPORY jen `status`, `usage --json`, `add`, `switch N`, `import-profile` a `codex login --device-auth`.
Device login běží v odděleném dočasném `CODEX_HOME`: v živém domově by při startu odhlásil dnešní účet a server by mu
odvolal tokeny (ověřeno 2026-11-07, codex 0.164). Hotové přihlášení se uloží jako slot přes `import-profile`.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend.agi_pletor.llm_settings.cswap import TIMEOUT, mask

INSTALL_HINT = "uv tool install codex-swap"
ACTIVE = re.compile(r"Active:\s*slot\s+(\d+)")
URL = re.compile(r"https://\S+")
USER_CODE = re.compile(r"\b[A-Z0-9]{4,5}-[A-Z0-9]{4,6}\b")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
START_LINES = 40  # device login vypíše adresu a kód na prvních řádcích
SELF_WAIT = 10
_lock = threading.Lock()
_process = None  # běžící `codex login --device-auth`
_home = None  # jeho dočasný CODEX_HOME


def _run(which, run, *args):
    binary = which("codex-swap")
    if not binary:
        raise ValueError(f"codex-swap není nainstalovaný ({INSTALL_HINT}).")
    return run([binary, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat() if isinstance(epoch, (int, float)) else None


def _pct(window, now, exhausted):
    if exhausted:
        return 100.0
    if not isinstance(window, dict) or not isinstance(window.get("used_percent"), (int, float)):
        return None
    reset = window.get("resets_at")
    return 0.0 if isinstance(reset, (int, float)) and now >= reset else float(window["used_percent"])


def account(slot, row, usage, active, now):
    info = usage.get(slot) if isinstance(usage.get(slot), dict) else {}
    primary, secondary, exhausted = info.get("primary"), info.get("secondary"), info.get("exhausted") is True
    return {
        "slot": int(slot), "label": mask(row.get("email")) or row.get("label") or "?", "alias": row.get("plan_type") or None,
        "active": active == int(slot), "usage5h": _pct(primary, now, exhausted), "usage7d": _pct(secondary, now, exhausted),
        "resetsAt": _iso((primary or {}).get("resets_at") if isinstance(primary, dict) else None),
    }


def _status(which, run):
    """`(active_slot | None, managed)`; odhlášený Codex je „managed“ (přihlášením se nic neztratí)."""
    text = ANSI.sub("", _run(which, run, "status").stdout or "")
    found = ACTIVE.search(text)
    return (int(found.group(1)) if found else None), "unmanaged" not in text


def read(which=shutil.which, run=subprocess.run, home=None, now=None):
    if not which("codex-swap"):
        return {"available": False, "reason": "codex-swap není nainstalovaný.", "installHint": INSTALL_HINT}
    try:
        active, managed = _status(which, run)
        done = _run(which, run, "usage", "--json")
        usage = (json.loads(done.stdout).get("data") or {}) if done.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        return {"available": False, "reason": f"codex-swap neodpověděl ({type(error).__name__})."}
    path = (home or Path.home()) / ".codex-swap" / "sequence.json"
    rows = (json.loads(path.read_text(encoding="utf-8")).get("accounts") or {}) if path.is_file() else {}
    clock = datetime.now(timezone.utc).timestamp() if now is None else now
    return {"available": True, "managed": managed, "accounts": [
        account(slot, row, usage if isinstance(usage, dict) else {}, active, clock)
        for slot, row in sorted(rows.items(), key=lambda item: int(item[0])) if str(slot).isdigit() and isinstance(row, dict)]}


def cancel():
    """Ukončí rozpracované přihlášení a smaže jeho dočasný domov; živý účet Codexu se nemění."""
    global _process, _home
    if _process is not None and _process.poll() is None:
        _process.kill()
    _process = None
    if _home is not None:
        shutil.rmtree(_home, ignore_errors=True)
        _home = None


def start(*, find=lambda: shutil.which("codex"), popen=subprocess.Popen, mkdtemp=tempfile.mkdtemp):
    """Spustí device login v dočasném `CODEX_HOME` a vrátí `{url, userCode}` (kód člověk zadá na stránce)."""
    global _process, _home
    codex = find()
    if not codex:
        raise ValueError("Codex (`codex`) na tomto počítači chybí.")
    with _lock:
        cancel()
        _home = mkdtemp(prefix="opora-codex-login-")
        env = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"} | {"CODEX_HOME": _home}
        _process = popen([codex, "login", "--device-auth"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
        url = user_code = None
        for number, line in enumerate(_process.stdout):
            line = ANSI.sub("", line)
            if not url and (found := URL.search(line)):
                url = found.group(0)
            if not user_code and (found := USER_CODE.search(line)):
                user_code = found.group(0)
            if (url and user_code) or number >= START_LINES:
                break
        if not url:
            cancel()
            raise ValueError("`codex login --device-auth` nevypsal adresu k přihlášení.")
        return {"url": url, "userCode": user_code}


def finish(code="", *, run=subprocess.run, which=shutil.which):
    """Po dokončeném přihlášení uloží nový účet jako slot (`import-profile`); bez přihlášení uloží živý účet (`add`)."""
    global _process
    with _lock:
        if _process is None:
            done = _run(which, run, "add")
        else:
            try:
                _process.wait(timeout=SELF_WAIT)
            except subprocess.TimeoutExpired:
                raise ValueError("Přihlášení ještě neskončilo: zadej kód na stránce a dokonči ho.")
            if _process.returncode != 0:
                cancel()
                raise ValueError("Přihlášení Codexu se nezdařilo nebo vypršelo.")
            done = _run(which, run, "import-profile", str(Path(_home) / "auth.json"))
            cancel()
        if done.returncode != 0:
            if "already saved" in (done.stdout or ""):
                raise ValueError("Tento účet už je uložený. Otevři odkaz v anonymním okně a přihlas se jiným účtem.")
            raise ValueError(f"codex-swap skončil kódem {done.returncode}.")
    return read(which=which, run=run)


def switch_to(slot, *, run=subprocess.run, which=shutil.which):
    if not isinstance(slot, int) or slot < 1:
        raise ValueError("slot je číslo účtu od 1.")
    done = _run(which, run, "switch", str(slot))
    if done.returncode != 0:
        raise ValueError(f"codex-swap switch skončil kódem {done.returncode}.")
    return read(which=which, run=run)
