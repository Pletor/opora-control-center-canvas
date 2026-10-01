"""Složky map jsou pro git ignorované, aniž by se měnil `.gitignore` projektu."""
import re
from pathlib import Path

from backend.integrations.gitio import git

FOLDER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$')


def ensure_excluded(root, folder):
    """Když git složku neignoruje, přidá ji do lokálního a nesledovaného `.git/info/exclude`.

    Vrací True, když byl řádek přidán. Projekt bez gitu se nechá beze změny.
    """
    if not FOLDER.fullmatch(folder):
        raise ValueError('Neplatná složka mapy.')
    root = Path(root)
    if not (root / '.git').exists():
        return False
    # check-ignore vrací nenulový kód, když cesta ignorovaná není; `optional` ho převede na None.
    if git(root, 'check-ignore', '-q', '--no-index', folder + '/', timeout=5, optional=True) is not None:
        return False
    relative = git(root, 'rev-parse', '--git-path', 'info/exclude', timeout=5, optional=True)
    if not relative:
        return False
    exclude = Path(relative) if Path(relative).is_absolute() else root / relative
    exclude.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = exclude.read_text(encoding='utf-8')
    except FileNotFoundError:
        current = ''
    line = '/' + folder + '/'
    if line in current.splitlines():
        return False
    with exclude.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(('' if not current or current.endswith('\n') else '\n') + line + '\n')
    return True
