"""Spustí jeden případ funkce Dílny v odděleném procesu: `python -I _run_case.py <cesta.py> <vstup JSON>`.

Výstup `run(vstup)` jde jako JSON na stdout. Chyba načtení modulu = kód 2, chyba funkce = výjimka (kód 1).
"""
import importlib.util
import json
import sys


def main(path, raw):
    try:
        spec = importlib.util.spec_from_file_location("dilna_funkce", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        run = module.run
    except Exception as error:  # noqa: BLE001 – rozlišit načtení od běhu funkce
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(2)
    # ensure_ascii: -I ignoruje PYTHONIOENCODING a konzole Windows nemusí být v UTF-8
    print(json.dumps(run(json.loads(raw)), sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
