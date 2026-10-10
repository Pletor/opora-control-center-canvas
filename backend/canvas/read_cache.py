"""Paměť odvozených čtení projektu (karta P3): graf, stav Desktop v3, výpis verzí, stav zadání.

Záznam nese razítko, podle kterého platí: token potvrzených dat (`CanvasService.data_token`),
revizi stavu nebo surový text grafu. Volající záznam použije jen při shodném razítku, jinak
přepočítá a uloží nový; neplatný záznam se tedy nikdy nevrátí, jen přepíše. Klíč vždy začíná
druhem a ID projektu, takže smazání projektu zahodí všechny jeho záznamy najednou (`drop`).

Hodnoty jsou sdílené mezi požadavky a jen ke čtení. Kdo je mění, vezme si kopii. V testech
(`OPORA_READ_CACHE_GUARD=1`, nastavuje `backend/conftest.py`) se každý zásah do sdílené
hodnoty pozná při dalším čtení a skončí chybou, ať se nedostane do produkce.
"""
import json
import os
import threading
from collections import OrderedDict

# Strop záznamů: na jeden projekt a prostor připadá nejvýš pět druhů (graf, stav, verze, hlava
# verzí, stav zadání); 40 záznamů pokryje několik otevřených projektů a paměť zůstane omezená.
LIMIT = 40
GUARD_ENV = "OPORA_READ_CACHE_GUARD"


def _fingerprint(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=repr)


class ReadCache:
    def __init__(self, limit=LIMIT):
        self._limit = limit
        self._entries = OrderedDict()
        self._guard = threading.Lock()

    def get(self, key, stamp):
        """Hodnota pod klíčem, jen když její razítko je `stamp`; jinak None. `stamp` None nikdy neplatí."""
        if stamp is None:
            return None
        with self._guard:
            entry = self._entries.get(key)
            if entry is None or entry[0] != stamp:
                return None
            self._entries.move_to_end(key)
        _check(key, entry)
        return entry[1]

    def peek(self, key):
        """(razítko, hodnota) bez ověření razítka; pro levnější druhou kontrolu (revize, surový text)."""
        with self._guard:
            entry = self._entries.get(key)
        if entry is None:
            return None, None
        _check(key, entry)
        return entry[0], entry[1]

    def put(self, key, stamp, value):
        entry = (stamp, value, _fingerprint(value) if os.environ.get(GUARD_ENV) else None)
        with self._guard:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._limit:
                self._entries.popitem(last=False)
        return value

    def drop(self, project):
        """Zahodí všechny záznamy projektu (smazání nebo odpojení projektu)."""
        with self._guard:
            for key in [key for key in self._entries if key[1] == project]:
                del self._entries[key]

    def __len__(self):
        return len(self._entries)


def _check(key, entry):
    if entry[2] is not None and _fingerprint(entry[1]) != entry[2]:
        raise AssertionError(f"Sdílená hodnota cache {key[0]} byla změněna na místě; volající si má vzít kopii.")
