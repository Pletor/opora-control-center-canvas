"""Stav srdce: povolení jen na loopbacku, strop dávek za hodinu, jeden prostor na projekt a lístek jednou."""
from collections import deque

from backend.flow.catalogs.heart import state
from backend.flow.catalogs.heart.state import HeartState


def test_enabled_only_on_loopback_and_not_off():
    assert state.enabled({}) is True
    assert state.enabled({"OPORA_HEART": "off"}) is False
    assert state.enabled({"OPORA_CANVAS_HOST": "0.0.0.0"}) is False
    assert state.enabled({"OPORA_CANVAS_HOST": "localhost"}) is True


def test_take_due_takes_one_workspace_per_project_and_respects_the_hourly_cap():
    heart = HeartState(object(), base_url="http://127.0.0.1:9", runner=lambda *a, **k: None, find=lambda: None)
    heart._add("p", "w1", {"type": "ticket", "ticketId": "t1"}, 10.0)
    heart._add("p", "w1", {"type": "ticket", "ticketId": "t1"}, 10.0)  # stejný lístek = jeden vstup
    heart._add("p", "w2", {"type": "commits"}, 10.0)
    assert heart.take_due(5.0) == []  # okno ještě běží
    assert heart.take_due(10.0) == [("p", "w1", [{"type": "ticket", "ticketId": "t1"}])]
    assert heart.running == {"p"} and heart.take_due(10.0) == []  # projekt má běžící dávku
    heart.running.clear()
    heart.starts["p"] = deque([9.0])
    assert heart.take_due(10.0, per_hour=1) == []  # strop za hodinu
    assert heart.next_allowed("p", 10.0, per_hour=1) == 9.0 + state.HOUR
    heart._add("p", "w2", {"type": "message", "text": "člověk"}, 10.0)
    assert [space for _, space, _ in heart.take_due(10.0, per_hour=1)] == ["w2"]  # zpráva člověka strop obchází
