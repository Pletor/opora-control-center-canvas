"""Relace srdce: navázání, rotace nad 60k tokenů kontextu posledního tahu, počítání dávek a odolnost vůči
poškozenému souboru."""
import json

from backend.brain_opora.heart import session


def ids(*values):
    items = iter(values)
    return lambda: next(items)


def test_first_batch_starts_a_new_session_then_resumes(tmp_path):
    assert session.load(tmp_path) == session.EMPTY
    assert session.choose(tmp_path, ids("s1")) == ("s1", False)
    assert session.record(tmp_path, "s1", 12_000) == {"sessionId": "s1", "batches": 1, "lastInputTokens": 12_000}
    assert session.choose(tmp_path, ids("s2")) == ("s1", True)
    assert session.record(tmp_path, "s1", 30_000)["batches"] == 2


def test_rotation_above_the_limit(tmp_path):
    session.record(tmp_path, "s1", session.ROTATE_AT + 1)
    assert session.choose(tmp_path, ids("s2")) == ("s2", False)
    assert session.record(tmp_path, "s2", 5_000) == {"sessionId": "s2", "batches": 1, "lastInputTokens": 5_000}


def test_input_tokens_sum_cache_and_ignore_garbage():
    usage = {"input_tokens": 10, "cache_read_input_tokens": 50_000, "cache_creation_input_tokens": 11_000,
             "output_tokens": 999}
    assert session.input_tokens(usage) == 61_010
    assert session.input_tokens(None) == 0 and session.input_tokens({"input_tokens": "x"}) == 0


def test_corrupt_file_means_no_session(tmp_path):
    (tmp_path / session.FILE).write_text("{nope", encoding="utf-8")
    assert session.load(tmp_path) == session.EMPTY
    (tmp_path / session.FILE).write_text('{"sessionId": 5}', encoding="utf-8")
    assert session.choose(tmp_path, ids("s9")) == ("s9", False)


def test_changed_prompt_starts_a_new_session(tmp_path):
    session.record(tmp_path, "s1", 5_000, "a" * 64)
    assert session.choose(tmp_path, ids("s2"), prompt_digest="a" * 64) == ("s1", True)
    assert session.choose(tmp_path, ids("s3"), prompt_digest="b" * 64) == ("s3", False)  # nová pravidla = nová relace
    session.record(tmp_path, "s0", 5_000)  # relace z doby před otiskem promptu
    assert session.choose(tmp_path, ids("s4"), prompt_digest="b" * 64) == ("s4", False)


def turn(read, created, fresh=2, parent=None, model="claude-haiku-5-5"):
    return json.dumps({"type": "assistant", "parent_tool_use_id": parent, "message": {
        "model": model, "usage": {"input_tokens": fresh, "cache_read_input_tokens": read,
                                  "cache_creation_input_tokens": created, "output_tokens": 100}}})


def test_context_is_the_last_main_turn_not_the_sum_of_all_turns():
    """Dávka Ample 18:44Z: 21 tahů, součet 541k, ale kontext posledního tahu 58,6k; rotace patří kontextu."""
    stream = "\n".join([json.dumps({"type": "system", "subtype": "init"}), turn(18_000, 3_500),
                        turn(21_500, 9_000), turn(30_500, 28_000, fresh=100),
                        turn(5_000, 1_000, parent="toolu_1"),  # pod-agent se nepočítá
                        json.dumps({"type": "result", "usage": {"input_tokens": 104, "cache_read_input_tokens": 70_000,
                                                                "cache_creation_input_tokens": 40_500}})])
    result = json.loads(stream.splitlines()[-1])
    assert session.last_turn_usage(stream)["cache_read_input_tokens"] == 30_500
    assert session.context_tokens(stream, result) == 58_600 < session.ROTATE_AT < session.input_tokens(result["usage"])


def test_context_without_turns_is_estimated_from_the_cumulative_usage():
    usage = {"input_tokens": 100, "cache_read_input_tokens": 498_000, "cache_creation_input_tokens": 43_000}
    assert session.context_tokens("", {"usage": usage, "num_turns": 21}) == 100 + 43_000 + 23_714
    assert session.context_tokens(None, None) == 0
    assert session.parts(usage | {"output_tokens": 7}) == {"fresh": 100, "cacheRead": 498_000,
                                                          "cacheCreation": 43_000, "output": 7}
