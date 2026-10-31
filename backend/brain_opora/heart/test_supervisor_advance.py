"""`HeartSupervisor._advance_one`: posun prostoru zapíše HEAD do `heads` a výjimku jen zaloguje."""
from types import SimpleNamespace

from backend.brain_opora.heart import supervisor
from backend.brain_opora.heart.supervisor import HeartSupervisor


def _bare():
    sup = HeartSupervisor.__new__(HeartSupervisor)
    sup.service = object()
    sup.heads = {}
    return sup


def _patch(monkeypatch, root, fast_forward):
    monkeypatch.setattr(supervisor, "WorkspaceSources", lambda service: SimpleNamespace(root=lambda p, w: root))
    monkeypatch.setattr(supervisor.workspace_fast_forward, "fast_forward", fast_forward)


def test_advance_one_sets_head_when_moved(monkeypatch):
    sup = _bare()
    _patch(monkeypatch, "/tmp/ws", lambda root, sha: "abc123")
    sup._advance_one("p", "w1", "main-sha")
    assert sup.heads == {("p", "w1"): "abc123"}


def test_advance_one_swallows_exceptions(monkeypatch):
    sup = _bare()

    def boom(root, sha):
        raise RuntimeError("git spadl")

    _patch(monkeypatch, "/tmp/ws", boom)
    sup._advance_one("p", "w1", "main-sha")
    assert sup.heads == {}
