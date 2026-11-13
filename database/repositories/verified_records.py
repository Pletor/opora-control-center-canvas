"""Paměť ověřených záznamů adresovaných obsahem (OP-A3AE94).

Revize zadání, manifesty grafu a záznamy obsahu jsou neměnné a jejich ID je otisk obsahu. Ověření tvaru a otisku
je čistá funkce (tabulka, rozsah, ID, uložený text), takže stejný text stačí ověřit jednou za život procesu.
Agent-state Ample bez paměti četl tytéž revize stokrát a 124 s držel zámek projektu, na který čekaly zápisy srdce.
Klíč nese otisk uloženého textu: změněný nebo podvržený řádek se ověří znovu a odmítne.
"""
import hashlib
import threading
from collections import OrderedDict

LIMIT = 8192
_seen, _lock = OrderedDict(), threading.Lock()


def once(table, scope, record_id, text, check):
    """Spustí `check()` (při chybě vyhodí), jen když tento přesný text pod (tabulka, rozsah, ID) ještě neprošel."""
    key = (table, *scope, record_id, hashlib.blake2b(text.encode("utf-8"), digest_size=16).digest())
    with _lock:
        if key in _seen:
            _seen.move_to_end(key)
            return
    check()
    with _lock:
        _seen[key] = None
        if len(_seen) > LIMIT:
            _seen.popitem(last=False)


def forget():
    """Pro testy: prázdná paměť."""
    with _lock:
        _seen.clear()
