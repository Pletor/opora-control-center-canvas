"""Omezená procesní cache; každá revize nahradí předchozí, data ven jsou kopie."""
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from threading import RLock


class ReadCache:
    def __init__(self, limit=128):
        self.limit = limit
        self.entries = OrderedDict()
        self._lock = RLock()

    def get(self, key, stamp):
        with self._lock:
            entry = self.entries.get(key)
            if entry is None or entry[0] != stamp:
                self.entries.pop(key, None)
                return None
            self.entries.move_to_end(key)
            return deepcopy(entry[1])

    def put(self, key, stamp, value):
        with self._lock:
            self.entries[key] = (stamp, deepcopy(value))
            self.entries.move_to_end(key)
            while len(self.entries) > self.limit:
                self.entries.popitem(last=False)
        return value


def file_stamp(path):
    """Změnu obsahu/nahrazení poznáme i při stejné velikosti; chybění má vlastní otisk."""
    path = Path(path)
    try:
        stat = path.stat()
        return str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino
    except FileNotFoundError:
        return str(path), None


def database_stamp(db):
    # total_changes zachytí všechny naše SQL writery (i rollback), data_version jiné spojení.
    # Uprostřed transakce se snapshot nikdy necachuje.
    return db.total_changes, db.execute('PRAGMA data_version').fetchone()[0]


def scope_stamp(canvas, project, workspace):
    """Volající drží canvas.lock. Zápisy do libovolné tabulky invalidují celý scope."""
    db = canvas.db_for(project)
    if db.in_transaction or canvas.db.in_transaction:
        return None
    source = None
    if project != 'draft' and canvas.project_hub.source_info(project)['sourceKind'] == 'git':
        location, _ = canvas.location(project, workspace)
        # Git pohled má další vstupy (HEAD/index/status); nesmí použít SQLite-only cache.
        source = file_stamp(location / 'opora-canvas.json')
        return None
    return project, workspace, database_stamp(canvas.db), database_stamp(db), source
