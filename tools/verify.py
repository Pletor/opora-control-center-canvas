"""Jeden příkaz, který ověří repozitář: lint, testy backendu, testy frontendu a odkazy v dokumentaci.

Odkazy v dokumentaci jsou ráčna, ne brána: dnešní stav je v `DOC_BASELINE` a smí jen klesat.
Když nálezů přibude, příkaz selže a řekne o kolik; když jich ubude, řekne, že je čas ráčnu utáhnout.
Nic neinstaluje, nic nespouští na pozadí a do repozitáře nezapisuje.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Kolik rozbitých odkazů v dokumentaci dnes existuje. Číslo smí jen klesat.
DOC_BASELINE = 89

# Kolik nálezů má dnes ruff ve starším kódu. Také ráčna: nové soubory musí být čisté,
# staré se uklízejí postupně a číslo smí jen klesat.
RUFF_BASELINE = 21

STEPS = (
    ("pytest", ["uv", "run", "pytest", "backend", "-q"]),
    ("vitest", ["npm", "test", "--silent"]),
)

RUFF = ["uv", "run", "ruff", "check", "backend", "tools", "database"]

# Testy, které padají z prostředí, ne z kódu: chybí volitelný balíček graphify.
KNOWN_FAILURES = (
    "test_generate_uses_official_graphify_and_persists_output",
    "test_real_graphify_refresh_publishes_only_selected_project",
)


def run(command):
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def only_known_failures(output):
    failed = [line for line in output.splitlines() if line.startswith("FAILED ")]
    return bool(failed) and all(any(known in line for known in KNOWN_FAILURES) for line in failed)


def check_ruff():
    """Ráčna nad nálezy ruffu: vrátí (stav, věta)."""
    code, output = run(RUFF)
    found = None
    for line in output.splitlines():
        if line.startswith("Found ") and line.endswith("errors."):
            found = int(line.split()[1])
        elif line.strip() == "All checks passed!":
            found = 0
    if found is None or code not in (0, 1):
        return False, "Výsledek ruffu nelze ověřit: " + output[-500:]
    if found > RUFF_BASELINE:
        return False, f"nálezů ruffu přibylo: {found} proti povoleným {RUFF_BASELINE}"
    if found < RUFF_BASELINE:
        return True, f"nálezů ruffu ubylo na {found}; utáhni RUFF_BASELINE v tools/verify.py"
    return True, f"nálezů ruffu je {found}, stejně jako povoluje ráčna"


def check_docs():
    """Ráčna nad rozbitými odkazy: vrátí (stav, věta)."""
    from tools.doc_check import check_repo

    found = len(check_repo(REPO_ROOT))
    if found > DOC_BASELINE:
        return False, f"rozbitých odkazů přibylo: {found} proti povoleným {DOC_BASELINE}"
    if found < DOC_BASELINE:
        return True, f"rozbitých odkazů ubylo na {found}; utáhni DOC_BASELINE v tools/verify.py"
    return True, f"rozbitých odkazů je {found}, stejně jako povoluje ráčna"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    only = set(argv)
    failures = []
    for name, command in STEPS:
        if only and name not in only:
            continue
        code, output = run(command)
        if code == 0:
            print(f"[ok] {name}")
            continue
        if name == "pytest" and only_known_failures(output):
            print(f"[ok] {name} (jen známá selhání kvůli chybějícímu balíčku graphify)")
            continue
        print(f"[chyba] {name}")
        print(output[-2000:])
        failures.append(name)
    if not only or "ruff" in only:
        passed, message = check_ruff()
        print(f"[{'ok' if passed else 'chyba'}] ruff: {message}")
        if not passed:
            failures.append("ruff")
    if not only or "docs" in only:
        passed, message = check_docs()
        print(f"[{'ok' if passed else 'chyba'}] docs: {message}")
        if not passed:
            failures.append("docs")
    print("hotovo" if not failures else "selhalo: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
