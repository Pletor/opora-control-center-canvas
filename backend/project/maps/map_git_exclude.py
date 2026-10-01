"""Výstupy map jsou pro git ignorované, aniž by se měnil `.gitignore` projektu."""
import re
from pathlib import Path

from backend.integrations.gitio import git

FOLDER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$')
# Vlastní provozní soubory OPORA uvnitř složky mapy; projekt je nikdy nemá verzovat.
BOOKKEEPING = ('opora-build.lock', 'opora-receipt.json', '*.tmp')


def ensure_excluded(root, folder):
    """Když git výstupy mapy neignoruje, zapíše je do lokálního a nesledovaného `.git/info/exclude`.

    Složku, ve které projekt už verzuje soubory, celou neskryje (nové karty musí zůstat vidět);
    vyloučí v ní jen provozní soubory OPORA. Vrací True, když přibyl aspoň jeden řádek.
    Projekt bez gitu se nechá beze změny.
    """
    if not FOLDER.fullmatch(folder):
        raise ValueError('Neplatná složka mapy.')
    root = Path(root)
    if not (root / '.git').exists():
        return False
    # Ptáme se na dítě složky: `složka/` s lomítkem git 2.47 hlásí jako ignorovanou, kdykoli
    # `.gitignore` obsahuje prázdný řádek. check-ignore vrací nenulový kód, když cesta ignorovaná
    # není; `optional` ho převede na None.
    if git(root, 'check-ignore', '-q', '--no-index', folder + '/.opora-probe', timeout=5, optional=True) is not None:
        return False
    if git(root, 'ls-files', '--', folder, timeout=5, optional=True):
        lines = ['/' + folder + '/' + name for name in BOOKKEEPING]
    else:
        lines = ['/' + folder + '/']
    relative = git(root, 'rev-parse', '--git-path', 'info/exclude', timeout=5, optional=True)
    if not relative:
        return False
    exclude = Path(relative) if Path(relative).is_absolute() else root / relative
    exclude.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = exclude.read_text(encoding='utf-8')
    except FileNotFoundError:
        current = ''
    missing = [line for line in lines if line not in current.splitlines()]
    if not missing:
        return False
    with exclude.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(('' if not current or current.endswith('\n') else '\n') + ''.join(line + '\n' for line in missing))
    return True
