"""Dílna D0: funkce `tools/<nazev>.py` s případy `<nazev>.cases.json`, měření a kontrola determinismu.

Kontrakt: docs/navrhy/2026-11-05-dilna-skillu.md §3a, §6. Každý případ běží dvakrát v odděleném procesu
(`python -I _run_case.py`) s časovým limitem, v dočasné složce a bez `OPORA_*` a klíčů API v prostředí.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from backend.brain_opora.heart.command import STRIPPED

TOOLS = Path(__file__).parent / "tools"
RUNNER = Path(__file__).parent / "_run_case.py"
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
LIMIT = 2000  # znaků výstupu nebo chyby v odpovědi


def _valid(name):
    if not NAME.match(name or ""):
        raise ValueError("Název funkce je [a-z][a-z0-9_]*.")
    return name


def _cases(path):
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not all(isinstance(c, dict) and "name" in c and "input" in c
                                              and "expected" in c for c in cases):
        raise ValueError("Případy jsou seznam {name, input, expected}.")
    return cases


def list_tools(folder=TOOLS):
    """Funkce ve složce: `[{name, path, cases}]`, `cases` = počet případů (0, když chybí nebo jsou neplatné)."""
    tools = []
    for path in sorted(Path(folder).glob("*.py")):
        if not NAME.match(path.stem):
            continue
        try:
            count = len(_cases(path.with_suffix(".cases.json")))
        except (OSError, ValueError):
            count = 0
        tools.append({"name": path.stem, "path": path.name, "cases": count})
    return tools


def _env():
    secret = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)
    return {key: value for key, value in os.environ.items()
            if not key.startswith("OPORA_") and key not in STRIPPED and not secret.search(key)}


def _once(path, case, timeout, cwd, env):
    """Jeden běh případu → (kód, text). Kód 0 = stdout s JSON, 2 = modul nejde načíst, jinak chyba funkce."""
    try:
        done = subprocess.run([sys.executable, "-I", str(RUNNER), str(path), json.dumps(case["input"])],
                              cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 1, f"Časový limit {timeout} s vypršel."
    if done.returncode:
        lines = [line for line in done.stderr.splitlines() if line.strip()]
        return done.returncode, (lines[-1] if lines else f"Kód {done.returncode}.")[:LIMIT]
    return 0, done.stdout.strip()[:LIMIT]


def measure(folder, name, timeout=20):
    """Změří funkci: `{name, passed, total, failed: [{name, got, expected}], durationMs, deterministic, error}`.

    Neznámá funkce je `LookupError`, špatný název `ValueError`. `error` je vyplněné jen při chybě načtení
    modulu nebo případů; chyba funkce (výjimka, limit, nevalidní JSON) je selhaný případ s `got` = text chyby.
    """
    path = Path(folder) / f"{_valid(name)}.py"
    if not path.is_file():
        raise LookupError(f"Funkce {name} neexistuje.")
    result = {"name": name, "passed": 0, "total": 0, "failed": [], "durationMs": 0, "deterministic": True,
              "error": None}
    try:
        cases = _cases(path.with_suffix(".cases.json"))
    except (OSError, ValueError) as error:
        return {**result, "error": f"Případy nejdou načíst: {error}"[:LIMIT]}
    started, env = time.perf_counter(), _env()
    with tempfile.TemporaryDirectory(prefix="dilna-") as cwd:
        for case in cases:
            (code, first), (_, second) = (_once(path, case, timeout, cwd, env) for _ in range(2))
            if code == 2:
                return {**result, "error": f"Modul nejde načíst: {first}",
                        "durationMs": round((time.perf_counter() - started) * 1000)}
            result["deterministic"] &= first == second
            got = first
            if code == 0:
                try:
                    got = json.loads(first)
                except ValueError:
                    got = f"Výstup není JSON: {first}"[:LIMIT]
            if code == 0 and got == case["expected"]:
                result["passed"] += 1
            else:
                result["failed"].append({"name": case["name"], "got": got, "expected": case["expected"]})
    result["total"] = len(cases)
    result["durationMs"] = round((time.perf_counter() - started) * 1000)
    return result
