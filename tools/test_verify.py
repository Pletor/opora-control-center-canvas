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
