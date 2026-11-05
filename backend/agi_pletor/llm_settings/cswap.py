"""Účty Claude Code z přepínače claude-swap (`cswap list --json`, schéma v1), jen ke čtení.

Pletor `cswap` neinstaluje a nespouští nic jiného než `list --json` (žádné add/switch/auto/run/remove).
Výstup nese úplné e-maily; ven jde jen maskovaný štítek, tokeny `list --json` nevypisuje vůbec.
"""
import json
import shutil
import subprocess

TIMEOUT = 15  # `list` může u každého účtu číst využití z API Anthropicu
INSTALL_HINT = "uv tool install claude-swap"


def mask(email):
    """`jan@domena.cz` → `j***@d***.cz`; text bez zavináče zůstane."""
    if not isinstance(email, str) or "@" not in email:
        return email if isinstance(email, str) else ""
    local, _, domain = email.partition("@")
    name, dot, tld = domain.rpartition(".")
    host = f"{name[:1]}***{dot}{tld}" if dot else f"{domain[:1]}***"
    return f"{local[:1]}***@{host}"


def _window(usage, key):
    window = usage.get(key) if isinstance(usage, dict) else None
    return window if isinstance(window, dict) else {}


def account(row):
    usage = row.get("usage")
    five, seven = _window(usage, "fiveHour"), _window(usage, "sevenDay")
    return {
        "slot": row.get("number"),
        "label": mask(row.get("email")),
        "alias": mask(row.get("alias")) or None,
        "active": row.get("active") is True,
        "usage5h": five.get("pct"),
        "usage7d": seven.get("pct"),
        "resetsAt": five.get("resetsAt") or seven.get("resetsAt"),
    }


def read(which=shutil.which, run=subprocess.run):
    binary = which("cswap")
    if not binary:
        return {"available": False, "reason": "claude-swap není nainstalovaný.", "installHint": INSTALL_HINT}
    try:
        done = run([binary, "list", "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "reason": f"cswap list neodpověděl ({type(error).__name__})."}
    if done.returncode != 0:
        # stderr/obálka chyby může nést e-mail, ven jde jen kód
        return {"available": False, "reason": f"cswap list skončil kódem {done.returncode}."}
    payload = json.loads(done.stdout)
    rows = payload.get("accounts") if isinstance(payload, dict) else None
    return {"available": True, "accounts": [account(row) for row in rows or [] if isinstance(row, dict)]}
