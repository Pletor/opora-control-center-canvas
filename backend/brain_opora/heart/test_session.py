"""Relace srdce: navázání, rotace nad 60k tokenů vstupu, počítání dávek a odolnost vůči poškozenému souboru."""
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
