"""Ověřený neměnný záznam se znovu neověřuje; jiný text pod stejným ID se ověří znovu (OP-A3AE94)."""
import pytest

from database.repositories import verified_records


def test_same_text_is_checked_once_and_changed_text_again():
    verified_records.forget()
    calls = []
    check = lambda: calls.append(1)  # noqa: E731
    verified_records.once("t", ("p", "w"), "a" * 40, '{"x":1}', check)
    verified_records.once("t", ("p", "w"), "a" * 40, '{"x":1}', check)
    assert calls == [1]
    verified_records.once("t", ("p", "w"), "a" * 40, '{"x":2}', check)
    verified_records.once("t", ("p", "other"), "a" * 40, '{"x":1}', check)
    assert calls == [1, 1, 1]


def test_failed_check_is_not_remembered():
    verified_records.forget()

    def bad():
        raise ValueError("tampered")
    for _ in range(2):
        with pytest.raises(ValueError):
            verified_records.once("t", ("p", "w"), "b" * 40, "{}", bad)
