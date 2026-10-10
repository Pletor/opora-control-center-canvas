import pytest

from backend.canvas.read_cache import ReadCache


def test_value_is_returned_only_for_the_same_stamp():
    cache = ReadCache()
    value = {"nodes": [1]}
    cache.put(("graph", "p1", "draft"), ("u", 3), value)
    assert cache.get(("graph", "p1", "draft"), ("u", 3)) is value
    assert cache.get(("graph", "p1", "draft"), ("u", 4)) is None
    assert cache.get(("graph", "p2", "draft"), ("u", 3)) is None
    # Bez razítka (zápis, Git) se z cache nikdy nečte, i když tam něco leží.
    cache.put(("graph", "p1", "draft"), None, value)
    assert cache.get(("graph", "p1", "draft"), None) is None
    assert cache.peek(("graph", "p1", "draft")) == (None, value)


def test_limit_drops_the_least_recently_used_entry():
    cache = ReadCache(limit=2)
    cache.put(("a", "p1", "w"), 1, "A")
    cache.put(("b", "p1", "w"), 1, "B")
    assert cache.get(("a", "p1", "w"), 1) == "A"
    cache.put(("c", "p1", "w"), 1, "C")
    assert len(cache) == 2
    assert cache.get(("b", "p1", "w"), 1) is None
    assert cache.get(("a", "p1", "w"), 1) == "A"


def test_drop_forgets_every_entry_of_one_project_only():
    cache = ReadCache()
    cache.put(("graph", "p1", "draft"), 1, "g1")
    cache.put(("state", "p1", "draft"), 1, "s1")
    cache.put(("graph", "p2", "draft"), 1, "g2")
    cache.drop("p1")
    assert cache.get(("graph", "p1", "draft"), 1) is None
    assert cache.get(("state", "p1", "draft"), 1) is None
    assert cache.get(("graph", "p2", "draft"), 1) == "g2"


def test_guard_detects_in_place_change_of_a_shared_value(monkeypatch):
    monkeypatch.setenv("OPORA_READ_CACHE_GUARD", "1")
    cache = ReadCache()
    value = {"decisions": []}
    cache.put(("state", "p1", "draft"), 1, value)
    value["decisions"].append({"id": "x"})
    with pytest.raises(AssertionError, match="změněna na místě"):
        cache.get(("state", "p1", "draft"), 1)
