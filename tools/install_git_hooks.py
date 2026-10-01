"""Nainstaluje pre-commit hook, který před commitem spustí `tools/verify.py`.

Spouští se výhradně ručně (`uv run python tools/install_git_hooks.py`), nikdy aplikací.
Aplikace si při vlastních git operacích hooky vypíná (`backend/integrations/gitio.py`),
takže tenhle hook platí jen pro člověka a agenta, kteří commitují sami.
Existující hook se nikdy nepřepíše bez `--force`; odinstaluje se `--remove`.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

HOOK = """#!/bin/sh
# Brána repozitáře: lint, testy a ráčna nad odkazy v dokumentaci.
# Nainstaloval tools/install_git_hooks.py; odebrat jde `--remove`.
exec uv run python tools/verify.py
"""

MARK = "tools/install_git_hooks.py"


def hook_path(root=REPO_ROOT):
    return Path(root) / ".git" / "hooks" / "pre-commit"


def install(root=REPO_ROOT, *, force=False):
    """Vrátí (stav, věta). Cizí hook se bez `force` nepřepisuje."""
    target = hook_path(root)
    if not target.parent.exists():
        return False, "složka .git/hooks neexistuje; tohle není git repozitář"
    if target.exists():
        current = target.read_text(encoding="utf-8", errors="replace")
        if MARK in current:
            target.write_text(HOOK, encoding="utf-8")
            return True, "hook byl aktualizován"
        if not force:
            return False, "existuje cizí pre-commit hook; přepsat jde jen s --force"
    target.write_text(HOOK, encoding="utf-8")
    return True, "hook byl nainstalován"


def remove(root=REPO_ROOT):
    """Odebere jen hook, který tenhle skript nainstaloval."""
    target = hook_path(root)
    if not target.exists():
        return True, "hook tam není"
    if MARK not in target.read_text(encoding="utf-8", errors="replace"):
        return False, "pre-commit hook je cizí; nechávám ho být"
    target.unlink()
    return True, "hook byl odebrán"


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    root = REPO_ROOT
    if args and not args[0].startswith("--"):
        root = Path(args[0])
        args = args[1:]
    passed, message = remove(root) if "--remove" in args else install(root, force="--force" in args)
    print(message)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
