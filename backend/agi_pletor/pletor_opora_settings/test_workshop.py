"""Dílna D0: měření funkcí v odděleném procesu, determinismus, chyby funkce a název."""
import json

import pytest

from backend.agi_pletor.pletor_opora_settings import workshop


def tool(folder, name, code, cases):
    (folder / f"{name}.py").write_text(code, encoding="utf-8")
    (folder / f"{name}.cases.json").write_text(json.dumps(cases), encoding="utf-8")


CASE = [{"name": "a", "input": {}, "expected": {"ok": True}}]


def test_sample_passes_and_is_deterministic():
    assert {"name": "rozdel_vety", "path": "rozdel_vety.py", "cases": 4} in workshop.list_tools()
    result = workshop.measure(workshop.TOOLS, "rozdel_vety")
    assert (result["passed"], result["total"], result["failed"]) == (4, 4, [])
    assert result["deterministic"] is True and result["error"] is None


def test_random_function_is_not_deterministic(tmp_path):
    tool(tmp_path, "nahoda", "import random\n\ndef run(vstup):\n    return {'x': random.random()}\n", CASE)
    assert workshop.measure(tmp_path, "nahoda")["deterministic"] is False


def test_exception_timeout_and_load_error(tmp_path):
    tool(tmp_path, "pada", "def run(vstup):\n    raise ValueError('rozbito')\n", CASE)
    failed = workshop.measure(tmp_path, "pada")["failed"]
    assert failed == [{"name": "a", "got": "ValueError: rozbito", "expected": {"ok": True}}]

    tool(tmp_path, "visi", "import time\n\ndef run(vstup):\n    time.sleep(30)\n", CASE)
    result = workshop.measure(tmp_path, "visi", timeout=1)
    assert result["passed"] == 0 and "limit" in result["failed"][0]["got"]

    tool(tmp_path, "bez_run", "x = 1\n", CASE)
    assert "AttributeError" in workshop.measure(tmp_path, "bez_run")["error"]


def test_child_env_has_no_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_DATA_ROOT", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    code = "import os\n\ndef run(vstup):\n    return {'keys': sorted(k for k in os.environ if 'OPORA' in k or 'API_KEY' in k)}\n"
    tool(tmp_path, "prostredi", code, [{"name": "a", "input": {}, "expected": {"keys": []}}])
    assert workshop.measure(tmp_path, "prostredi")["passed"] == 1


def test_bad_name_and_unknown():
    with pytest.raises(ValueError):
        workshop.measure(workshop.TOOLS, "../rozdel_vety")
    with pytest.raises(LookupError):
        workshop.measure(workshop.TOOLS, "neni")
