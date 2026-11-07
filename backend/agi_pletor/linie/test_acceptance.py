"""Nasazené SHA: zápis, validace sha, vadný soubor = nic nenasazeno."""
import pytest

from backend.agi_pletor.linie import acceptance


def test_deployed(tmp_path):
    assert acceptance.read_deployed(tmp_path) is None
    assert acceptance.set_deployed(tmp_path, "abc1234", "t2") == {"sha": "abc1234", "at": "t2"}
    assert acceptance.read_deployed(tmp_path) == {"sha": "abc1234", "at": "t2"}


@pytest.mark.parametrize("sha", ["abc12", "ABC1234", "g" * 7, None])
def test_deployed_refuses(tmp_path, sha):
    with pytest.raises(ValueError):
        acceptance.set_deployed(tmp_path, sha, "t")
    assert acceptance.read_deployed(tmp_path) is None


def test_broken_file_reads_empty(tmp_path):
    (tmp_path / "linie").mkdir()
    (tmp_path / "linie" / "deployed.json").write_text("{nečitelné", encoding="utf-8")
    assert acceptance.read_deployed(tmp_path) is None
