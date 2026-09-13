

def test_docker_oracle_runs_real_python_and_rejects_test_tampering(tmp_path):
    import uuid

    from backend.agents.runs.coding_tools import run_tests
    source = tmp_path / "calculator.py"
    source.write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    baseline = run_tests(tmp_path, uuid.uuid4().hex)
    assert baseline["exitCode"] != 0
    source.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = run_tests(tmp_path, uuid.uuid4().hex)
    assert result["exitCode"] == 0
    assert "Ran 4 tests" in result["output"]
    source.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    assert run_tests(tmp_path, uuid.uuid4().hex)["exitCode"] != 0
