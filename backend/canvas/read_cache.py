"""Neměnné JSON snímky, procesní bajtový LRU rozpočet a pojistka vypnutí."""
from collections import OrderedDict
import json
import os
from pathlib import Path
from threading import RLock
import weakref

DEFAULT_BYTE_BUDGET = 32 * 1024 * 1024


def cache_enabled():
    return os.environ.get('OPORA_READ_CACHE', '1') != '0'


class CacheBudget:
    """Společný rozpočet payloadů; slabé reference neudržují zaniklé služby."""
    def __init__(self, size):
        self.size = max(0, size)
        self.used = 0
        self.lru = OrderedDict()
        self.lock = RLock()

    def discard(self, owner, key):
        size = self.lru.pop((owner, key), 0)
        self.used -= size
        cache = owner()
        if cache is not None:
            cache.entries.pop(key, None)

    def release(self, owner):
        with self.lock:
            for ref, key in list(self.lru):
                if ref == owner:
                    self.discard(ref, key)

    def clear(self):
        with self.lock:
            while self.lru:
                self.discard(*next(iter(self.lru)))


_PROCESS_BUDGET = CacheBudget(DEFAULT_BYTE_BUDGET)


class ReadCache:
    def __init__(self, limit=128, *, byte_budget=None, budget=None):
        # Menší izolovaný rozpočet lze injektovat v testu; produkce sdílí procesní.
        self.budget = budget if budget is not None else (
            _PROCESS_BUDGET if byte_budget is None else CacheBudget(byte_budget))
        self.limit = max(0, limit)
        self.entries = OrderedDict()
        self._lock = self.budget.lock
        self._owner = weakref.ref(self, self.budget.release)

    @property
    def bytes_used(self):
        with self._lock:
            return self.budget.used

    def _enabled(self):
        if cache_enabled():
            return True
        _PROCESS_BUDGET.clear()
        self.budget.clear()
        return False

    def get_snapshot(self, key, stamp):
        if not self._enabled():
            return None
        with self._lock:
            entry = self.entries.get(key)
            if entry is None or entry[0] != stamp:
                self.budget.discard(self._owner, key)
                return None
            self.entries.move_to_end(key)
            self.budget.lru.move_to_end((self._owner, key))
            return entry[1]

    @staticmethod
    def decode(snapshot):
        return json.loads(snapshot) if snapshot is not None else None

    def get(self, key, stamp):
        # Dekódování nikdy nedrží interní mutex cache.
        return self.decode(self.get_snapshot(key, stamp))

    def put(self, key, stamp, value):
        if not self._enabled():
            return value
        try:
            snapshot = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        except (TypeError, ValueError, UnicodeError):
            # Optimalizace nesmí shodit samotné čtení nestandardního obsahu.
            with self._lock:
                self.budget.discard(self._owner, key)
            return value
        self.put_snapshot(key, stamp, snapshot)
        return value

    def put_snapshot(self, key, stamp, snapshot):
        if not self._enabled():
            return
        if not isinstance(snapshot, bytes):
            raise TypeError('Snímek cache musí být neměnné bytes.')
        size = len(snapshot)
        with self._lock:
            self.budget.discard(self._owner, key)
            if size > self.budget.size // 4 or not self.limit:
                return
            while self.budget.used + size > self.budget.size:
                self.budget.discard(*next(iter(self.budget.lru)))
            while len(self.entries) >= self.limit:
                self.budget.discard(self._owner, next(iter(self.entries)))
            self.entries[key] = (stamp, snapshot)
            self.budget.lru[self._owner, key] = size
            self.budget.used += size


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
    return (db, db.total_changes, db.execute('PRAGMA data_version').fetchone()[0],
            db.execute('PRAGMA schema_version').fetchone()[0])


def scope_stamp(canvas, project, workspace):
    """Volající drží canvas.lock. Zápisy do libovolné tabulky invalidují celý scope."""
    db = canvas.db_for(project)
    if db.in_transaction or canvas.db.in_transaction:
        return None
    if not cache_enabled():
        return None
    if project != 'draft' and canvas.project_hub.source_info(project)['sourceKind'] == 'git':
        # Git má další živé vstupy; neprovádíme zde žádné zbytečné souborové I/O.
        return None
    return project, workspace, database_stamp(canvas.db), database_stamp(db)
