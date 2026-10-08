from tools.verify import only_known_failures


def test_only_known_failures_accepts_the_graphify_pair():
    output = "\n".join([
        "FAILED backend/api/project/test_graphify_routes.py::test_generate_uses_official_graphify_and_persists_output",
        "FAILED backend/project/maps/test_map_refresh.py::test_real_graphify_refresh_publishes_only_selected_project",
        "2 failed, 800 passed",
    ])
    assert only_known_failures(output) is True


def test_only_known_failures_rejects_anything_else():
    output = "FAILED backend/canvas/test_sync_report.py::test_report_pairs_existing_sources"
    assert only_known_failures(output) is False


def test_only_known_failures_needs_a_failure_to_talk_about():
    assert only_known_failures("800 passed") is False


def test_ruff_unknown_output_never_passes(monkeypatch):
    from tools import verify
    monkeypatch.setattr(verify, "run", lambda command: (2, "Invalid configuration"))
    assert verify.check_ruff()[0] is False
    monkeypatch.setattr(verify, "run", lambda command: (1, ""))
    assert verify.check_ruff()[0] is False


def test_subprocess_output_is_utf8_on_windows():
    import sys
    from tools.verify import run
    code, output = run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([0xe2, 0x9c, 0x88]))"])
    assert code == 0 and output == "✈"
