"""Bajtový rozpočet sdílený cache a nezávislé neměnné snímky."""
import json
from backend.canvas.read_cache import ReadCache


def test_byte_budget_evicts_lru_and_rejects_oversized_entry():
    cache = ReadCache(byte_budget=80)
    value = 'ž' * 8
    size = len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())
    for i in range(4):
        cache.put(i, 1, value)
        assert cache.bytes_used <= 80
    assert cache.get(0, 1) == value
    cache.put(4, 1, value)
    assert cache.get(1, 1) is None
    assert cache.get(0, 1) == value
    assert cache.bytes_used == 4 * size
    cache.put(0, 2, 'x' * 30)
    assert cache.get(0, 2) is None
    assert cache.bytes_used == 3 * size
    cache.get(2, 2)
    assert cache.bytes_used == 2 * size


def test_shared_budget_covers_multiple_cache_owners():
    first = ReadCache(byte_budget=80)
    second = ReadCache(budget=first.budget)
    for i in range(4):
        first.put(i, 1, 'x' * 16)
    second.put(0, 1, 'x' * 16)
    assert first.get(0, 1) is None
    assert first.bytes_used == second.bytes_used == 72


def test_disabled_cache_does_not_serialize_or_return_old_values(monkeypatch):
    cache = ReadCache(byte_budget=80)
    cache.put('key', 1, {})
    monkeypatch.setenv('OPORA_READ_CACHE', '0')
    assert cache.get('key', 1) is None
    cache.put('key', 1, object())
    assert cache.bytes_used == 0
    monkeypatch.setenv('OPORA_READ_CACHE', '1')
    assert cache.get('key', 1) is None


def test_snapshot_is_immutable_and_survives_eviction():
    cache = ReadCache(limit=1)
    cache.put('first', 1, {'value': [1]})
    snapshot = cache.get_snapshot('first', 1)
    assert isinstance(snapshot, bytes)
    cache.put('second', 1, {})
    assert cache.decode(snapshot) == {'value': [1]}


def test_serialization_failure_bypasses_cache_without_hiding_value():
    cache = ReadCache(byte_budget=80)
    cache.put('key', 1, {})
    for value in (object(), '\ud800'):
        assert cache.put('key', 2, value) is value
        assert cache.get('key', 2) is None
        assert cache.bytes_used == 0


def test_owner_collection_releases_shared_budget():
    import gc
    import weakref
    cache = ReadCache(byte_budget=80)
    budget = cache.budget
    cache.put('key', 1, {'value': 1})
    owner = weakref.ref(cache)
    assert budget.used > 0
    del cache
    gc.collect()
    assert owner() is None
    assert budget.used == 0
    assert not budget.lru
