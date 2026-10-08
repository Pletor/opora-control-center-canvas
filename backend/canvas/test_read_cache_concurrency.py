"""Deterministické proložení čtení cache a vytěsnění jiným vláknem."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from backend.canvas.read_cache import ReadCache


def test_hit_is_atomic_against_eviction():
    entered, proceed, written = Event(), Event(), Event()

    class PausedEntries(OrderedDict):
        def get(self, key, default=None):
            result = super().get(key, default)
            entered.set()
            assert proceed.wait(2)
            return result

    cache = ReadCache(limit=1)
    cache.put('first', 1, {'value': [1]})
    cache.entries = PausedEntries(cache.entries)

    def writer():
        cache.put('second', 1, {'value': [2]})
        written.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(cache.get, 'first', 1)
        assert entered.wait(2)
        write = pool.submit(writer)
        written.wait(.2)
        proceed.set()
        assert reader.result(timeout=2) == {'value': [1]}
        write.result(timeout=2)
    assert cache.get('second', 1) == {'value': [2]}


def test_input_and_output_are_not_shared():
    cache = ReadCache()
    value = {'nested': [1]}
    cache.put(('project', 'workspace'), 1, value)
    value['nested'].append(2)
    result = cache.get(('project', 'workspace'), 1)
    result['nested'].append(3)
    assert cache.get(('project', 'workspace'), 1) == {'nested': [1]}
    assert cache.get(('other', 'workspace'), 1) is None
    assert cache.get(('project', 'other'), 1) is None
