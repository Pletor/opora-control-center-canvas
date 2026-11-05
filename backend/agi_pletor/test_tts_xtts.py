"""Hlas XTTS bez GPU a bez serveru: důvody nedostupnosti v pořadí, streamování přes falešný transport, close."""
import io

import pytest

from backend.agi_pletor import tts, tts_xtts


@pytest.fixture
def ready(tmp_path, monkeypatch):
    """Nainstalované prostředí a stažený model v tmp; server neběží."""
    python = tmp_path / "python.exe"
    python.write_bytes(b"")
    monkeypatch.setattr(tts_xtts, "python", lambda: python)
    monkeypatch.setattr(tts_xtts, "_process", {"proc": None, "port": None})
    folder = tmp_path / "pletor"
    tts_xtts.model_dir(folder).mkdir(parents=True)
    for name in tts_xtts.FILES:
        (tts_xtts.model_dir(folder) / name).write_bytes(b"x")
    return folder


def test_reasons_in_order(ready, monkeypatch):
    plenty, little = (lambda: 8000), (lambda: 400)
    assert tts_xtts.reason(ready, "xtts:default", plenty) is None
    assert "málo paměti GPU: volno 400 MB" in tts_xtts.reason(ready, "xtts:default", little)
    assert "qwen3:8b" in tts_xtts.reason(ready, "xtts:default", little)
    assert "bez GPU" in tts_xtts.reason(ready, "xtts:default", lambda: None)
    assert "jarvis.wav" in tts_xtts.reason(ready, "xtts:clone", plenty)
    tts_xtts.reference(ready).parent.mkdir()
    tts_xtts.reference(ready).write_bytes(b"RIFF")
    assert tts_xtts.reason(ready, "xtts:clone", plenty) is None
    (tts_xtts.model_dir(ready) / "model.pth").unlink()
    assert "není stažen" in tts_xtts.reason(ready, "xtts:default", plenty)
    monkeypatch.setattr(tts_xtts, "python", lambda: ready / "nic.exe")
    assert "uv sync --project tools/xtts_server" in tts_xtts.reason(ready, "xtts:default", plenty)


class FakeResponse(io.BytesIO):
    def read1(self, size=-1):
        return self.read(min(size, 3))  # po kouscích, jak chodí ze serveru


def test_stream_chunks_from_server(ready, monkeypatch):
    monkeypatch.setattr(tts_xtts, "free_vram_mb", lambda: 8000)
    monkeypatch.setattr(tts_xtts, "_ensure", lambda folder: 5555)
    sent = []
    urlopen = lambda request, timeout: sent.append(request) or FakeResponse(b"\x01\x00\x02\x00\x03")
    chunks = list(tts_xtts.stream(ready, "Ahoj.", "xtts:default", urlopen))
    assert b"".join(chunks) == b"\x01\x00\x02\x00\x03" and len(chunks) == 2
    assert sent[0].full_url == "http://127.0.0.1:5555/tts" and b'"reference": null' in sent[0].data


def test_stream_refusals(ready, monkeypatch):
    monkeypatch.setattr(tts_xtts, "_ensure", lambda folder: 5555)
    monkeypatch.setattr(tts_xtts, "free_vram_mb", lambda: 400)
    with pytest.raises(tts.EngineMissing, match="málo paměti GPU"):
        tts_xtts.stream(ready, "Ahoj.", "xtts:default")
    monkeypatch.setattr(tts_xtts, "free_vram_mb", lambda: 8000)

    def down(request, timeout):
        raise ConnectionRefusedError("spadl")
    with pytest.raises(tts.EngineMissing, match="neodpověděl"):
        tts_xtts.stream(ready, "Ahoj.", "xtts:default", down)
    with pytest.raises(tts.VoiceMissing):
        tts_xtts.stream(ready, "Ahoj.", "xtts:nikdo")
    (tts_xtts.model_dir(ready) / "vocab.json").unlink()
    with pytest.raises(tts.VoiceMissing, match="tts_fetch xtts"):
        tts_xtts.stream(ready, "Ahoj.", "xtts:default")


def test_close_ends_server(monkeypatch):
    class Proc:
        def __init__(self):
            self.stdin, self.killed = io.StringIO(), False

        def poll(self):
            return None

        def wait(self, timeout):
            assert self.stdin.closed

    proc = Proc()
    monkeypatch.setattr(tts_xtts, "_process", {"proc": proc, "port": 1})
    tts_xtts.close()
    assert tts_xtts._process["proc"] is None
    tts_xtts.close()  # podruhé nic
