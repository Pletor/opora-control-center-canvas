from backend.claude_code.assistant.metrics import observe
from backend.claude_code.assistant.registry import SessionRegistry


def result(uid, cost, tokens=100):
    return {"type": "result", "uuid": uid, "total_cost_usd": cost, "duration_ms": 500,
            "usage": {"input_tokens": 10, "output_tokens": 5}, "num_turns": 2,
            "modelUsage": {"claude-test": {"inputTokens": tokens, "outputTokens": 20,
                                           "cacheReadInputTokens": 30, "cacheCreationInputTokens": 0,
                                           "contextWindow": 200000}}}


def test_cumulative_snapshot_not_added_and_replayed_result_not_counted():
    first = observe(None, result("a", 0.1))
    second = observe(first, result("b", 0.2, 200))
    assert second["costUsd"] == 0.2
    assert second["models"]["claude-test"]["inputTokens"] == 200
    assert second["completed"] == 2
    assert second["durationMs"] == 1000
    assert observe(second, result("b", 0.2, 200)) is second
    assert first["completed"] == 1


def test_context_uses_current_input_and_cache_not_outputs_or_subagents():
    message = {"type": "assistant", "message": {"model": "claude-test", "usage": {
        "input_tokens": 10, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20,
        "output_tokens": 500}}}
    metrics = observe(None, message)
    assert metrics["contextTokens"] == 130
    assert observe(metrics, {**message, "parent_tool_use_id": "agent"}) is metrics
    compact = observe(metrics, {"type": "system", "subtype": "compact_boundary"})
    assert "contextTokens" not in compact


def test_unknown_and_invalid_measurements_are_not_zero():
    metrics = observe(None, {"type": "result", "usage": {"input_tokens": True, "output_tokens": -1},
                             "total_cost_usd": float("nan")})
    assert metrics["costUsd"] is None
    assert metrics["lastUsage"] == {}
    assert metrics["models"] == {}
    assert observe(metrics, {"type": "stream_event"}) is metrics


def test_persistence_resume_and_new_cli_epoch(tmp_path):
    registry = SessionRegistry(tmp_path)
    session = registry.create("p", "draft", "opus")
    init = {"type": "system", "subtype": "init", "session_id": "cli1", "model": "claude-test"}
    metrics = observe(observe(None, init), result("a", 0.1))
    registry.update(session["id"], metrics=metrics)
    restored = SessionRegistry(tmp_path).get(session["id"])["metrics"]
    assert restored == metrics
    assert observe(restored, init) is restored
    new = observe(restored, {**init, "session_id": "cli2"})
    assert "costUsd" not in new and "models" not in new
    assert new["completed"] == 1


def test_errors_count_as_results_not_verified_success():
    metrics = observe(None, {**result("a", 0), "is_error": True})
    assert metrics["completed"] == metrics["errors"] == 1
