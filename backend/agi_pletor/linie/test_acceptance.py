"""Přijetí: zápis, zrušení, nasazení, validace sha/větve/cíle, vadný soubor = prázdno."""
import pytest

from backend.agi_pletor.linie import acceptance


def test_accept_revoke_deployed(tmp_path):
    assert acceptance.read(tmp_path) == {"branches": {}, "deployed": None}
    acceptance.accept(tmp_path, "feat/x", "abc1234", "develop", "ok", "2026-11-06T10:00:00Z")
    acceptance.accept(tmp_path, "feat/y", "a" * 40, "topic/1-tema", None, "t")
    stored = acceptance.read(tmp_path)
    assert stored["branches"]["feat/x"] == {"sha": "abc1234", "target": "develop", "at": "2026-11-06T10:00:00Z",
                                            "note": "ok"}
    assert stored["branches"]["feat/y"]["note"] == ""
    acceptance.revoke(tmp_path, "feat/x")
    acceptance.set_deployed(tmp_path, "abc1234", "t2")
    assert acceptance.read(tmp_path) == {"branches": {"feat/y": stored["branches"]["feat/y"]},
                                         "deployed": {"sha": "abc1234", "at": "t2"}}


@pytest.mark.parametrize("branch, sha, target", [
    ("feat/x", "abc12", "main"), ("feat/x", "ABC1234", "main"), ("feat/x", "g" * 7, "main"),
    ("", "abc1234", "main"), ("feat x", "abc1234", "main"),
    ("feat/x", "abc1234", "feat/y"), ("feat/x", "abc1234", "topic/"),
])
def test_accept_refuses(tmp_path, branch, sha, target):
    with pytest.raises(ValueError):
        acceptance.accept(tmp_path, branch, sha, target, "", "t")
    assert acceptance.read(tmp_path)["branches"] == {}


def test_broken_file_reads_empty(tmp_path):
    (tmp_path / "linie").mkdir()
    (tmp_path / "linie" / "acceptance.json").write_text("{nečitelné", encoding="utf-8")
    assert acceptance.read(tmp_path) == {"branches": {}, "deployed": None}
