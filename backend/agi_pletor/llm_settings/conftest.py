"""Dočasný domov pro testy nastavení LLM: skutečné `~/.claude` a `~/.codex` se nikdy nečtou.

`home` přesměruje `Path.home()` do tmp a zakáže číst soubory s tajemstvím (otevření ke čtení = AssertionError).
"""
import builtins
import io
import pathlib

import pytest

SECRETS = {".credentials.json", ".claude.json", "auth.json", ".env"}


class Done:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.returncode = stdout, returncode


def fake_run(outputs, calls=None):
    """Falešný `subprocess.run`: výstup podle druhého argumentu (`--version`, `list`, …)."""
    def run(command, **kwargs):
        if calls is not None:
            calls.append(command)
        key = command[1] if len(command) > 1 else command[0]
        value = outputs.get(key, outputs.get(command[0]))
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, Done) else Done(value or "")
    return run


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    for target, name in ((builtins, "open"), (io, "open"), (pathlib.Path, "open")):
        original = getattr(target, name)

        def guarded(file, *args, _original=original, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            reading = not set(mode) & set("wax")  # test si tajné soubory sám zakládá, kód je smí jen nečíst
            assert not (reading and pathlib.PurePath(str(file)).name in SECRETS), f"tajný soubor otevřen: {file}"
            return _original(file, *args, **kwargs)
        monkeypatch.setattr(target, name, guarded)
    return tmp_path
