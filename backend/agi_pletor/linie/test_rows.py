"""Řádky editoru: přidání nezaloží větev (bod 1), pevné Main/Develop, smazat jde jen prázdný řádek."""
import pytest

from backend.agi_pletor.linie import rows
from backend.agi_pletor.linie.test_branches import make_repo, run
from backend.brain_opora.determinism.gate_payloads import GateError


def test_rows_without_git(tmp_path):
    repo = make_repo(tmp_path / "repo")
    before = run(repo, "for-each-ref", "refs/heads")
    first = rows.add(tmp_path, "p1", "Datový uzel", "work", {"branch": "develop"}, "develop")
    second = rows.add(tmp_path, "p1", "Experiment", "experiment")
    assert run(repo, "for-each-ref", "refs/heads") == before  # přidání řádku nezakládá větev
    found = rows.read(tmp_path, "p1")
    assert found["mapping"] == {"main": "main", "develop": "develop"}
    assert [row["id"] for row in found["rows"]] == ["main", "develop", first["id"], second["id"]]
    assert first["branch"] is None and first["base"] == {"branch": "develop", "sha": None}
    renamed = rows.patch(tmp_path, "p1", first["id"], {"name": "Uzel", "collapsed": True})
    assert renamed["name"] == "Uzel" and renamed["collapsed"] is True and renamed["target"] == "develop"
    assert run(repo, "for-each-ref", "refs/heads") == before  # přejmenování nepřejmenuje větev
    with pytest.raises(GateError) as caught:
        rows.remove(tmp_path, "p1", first["id"], {first["id"]})
    assert caught.value.code == "row_in_use"
    assert rows.remove(tmp_path, "p1", first["id"], set()) == {"removed": first["id"]}
    assert [row["id"] for row in rows.read(tmp_path, "p1")["rows"]] == ["main", "develop", second["id"]]


def test_legacy_topic_row_reads_as_items(tmp_path):
    kept = rows.add(tmp_path, "p1", "Starý", "items")
    path = tmp_path / "projects" / "p1" / "linie" / "rows.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"items"', '"topic"'), encoding="utf-8")
    assert [row["type"] for row in rows.read(tmp_path, "p1")["rows"] if row["id"] == kept["id"]] == ["items"]


@pytest.mark.parametrize("act, code", [
    (lambda root: rows.patch(root, "p1", "main", {"name": "x"}), "row_fixed"),
    (lambda root: rows.remove(root, "p1", "develop", set()), "row_fixed"),
    (lambda root: rows.patch(root, "p1", "row_nic", {"name": "x"}), "row_not_found"),
    (lambda root: rows.add(root, "p1", "x", "main"), "invalid_payload"),
    (lambda root: rows.add(root, "p1", "x", "topic"), "invalid_payload"),
    (lambda root: rows.add(root, "p1", " ", "work"), "invalid_payload"),
    (lambda root: rows.add(root, "p1", "x", "work", None, "dev elop"), "invalid_payload"),
])
def test_rows_refuse(tmp_path, act, code):
    with pytest.raises(GateError) as caught:
        act(tmp_path)
    assert caught.value.code == code
