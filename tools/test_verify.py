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
