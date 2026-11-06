"""Přijetí hlavy větve člověkem a nasazené SHA (kontrakt §5): `<pletor>/linie/acceptance.json`.

Tvar `{"branches": {větev: {sha, target, at, note}}, "deployed": {sha, at} | null}`. Zapisuje jen člověk (routa);
platnost (`sha == HEAD větve`) počítá `view.py`, tady se jen ukládá.
"""
import json
import re
from pathlib import Path

FILE = "acceptance.json"
SHA = re.compile(r"[0-9a-f]{7,40}")
TARGET = re.compile(r"main|develop|topic/\S+")


def _path(folder):
    return Path(folder) / "linie" / FILE


def read(folder):
    """Uložený stav; chybějící nebo vadný soubor = nic přijato, nic nasazeno."""
    try:
        value = json.loads(_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    value = value if isinstance(value, dict) else {}
    branches = value.get("branches") if isinstance(value.get("branches"), dict) else {}
    deployed = value.get("deployed") if isinstance(value.get("deployed"), dict) else None
    return {"branches": branches, "deployed": deployed}


def _write(folder, value):
    path = _path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)  # celý soubor, nebo nic: rozepsané přijetí nesmí zůstat
    return value


def _sha(sha):
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("sha je 7–40 znaků 0-9a-f.")
    return sha


def _branch(branch):
    if not isinstance(branch, str) or not branch.strip() or any(c.isspace() for c in branch):
        raise ValueError("Větev je neprázdný název bez mezer.")
    return branch


def accept(folder, branch, sha, target, note, now):
    """Zapíše přijetí přesně této hlavy do cíle `main`, `develop` nebo `topic/*`."""
    _branch(branch), _sha(sha)
    if not isinstance(target, str) or not TARGET.fullmatch(target):
        raise ValueError("Cíl přijetí je main, develop nebo topic/<název>.")
    value = read(folder)
    value["branches"][branch] = {"sha": sha, "target": target, "at": now, "note": note or ""}
    return _write(folder, value)


def revoke(folder, branch):
    value = read(folder)
    value["branches"].pop(_branch(branch), None)
    return _write(folder, value)


def set_deployed(folder, sha, now):
    value = read(folder)
    value["deployed"] = {"sha": _sha(sha), "at": now}
    return _write(folder, value)
