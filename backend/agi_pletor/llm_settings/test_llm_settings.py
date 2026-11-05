"""Souhrn: rozbitá sekce vrátí `{available: false, reason}` a ostatní projdou."""
from backend.agi_pletor import llm_settings


def test_section_fails_alone(monkeypatch):
    def broken():
        raise ValueError("vadný soubor")

    monkeypatch.setattr(llm_settings, "SECTIONS", {"claude": broken, "codex": lambda: {"available": True},
                                                   "ollama": lambda: {"available": False, "reason": "neběží"},
                                                   "cswap": lambda: {"available": True, "accounts": []}})
    assert llm_settings.read_all() == {
        "claude": {"available": False, "reason": "ValueError: vadný soubor"}, "codex": {"available": True},
        "ollama": {"available": False, "reason": "neběží"}, "cswap": {"available": True, "accounts": []}}
