"""Hlas Pletora s falešným Piperem: cache hlasu, jen stažené hlasy, WAV hlavička, chybějící model."""
import io
import wave

import pytest

from backend.pletor import tts


class FakeVoice:
    class config:
        sample_rate = 22050

    def synthesize_wav(self, text, wav, set_wav_format=True):
        assert set_wav_format is False
        wav.writeframes(b"\x01\x00" * len(text))


def seed(folder, *names):
    target = tts.voices_dir(folder)
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        (target / f"{name}.onnx").write_bytes(b"\x08model")
        (target / f"{name}.onnx.json").write_text("{}", encoding="utf-8")


def test_voice_loads_once_and_returns_wav(tmp_path):
    seed(tmp_path, tts.DEFAULT)
    loads = []
    load = lambda path: loads.append(path) or FakeVoice()
    first = tts.synthesize(tmp_path, "Ahoj.", tts.DEFAULT, load=load)
    tts.synthesize(tmp_path, "Ještě jednou.", tts.DEFAULT, load=load)
    assert len(loads) == 1
    assert first[:4] == b"RIFF" and first[8:12] == b"WAVE"
    with wave.open(io.BytesIO(first)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 22050, 5)


def test_missing_or_unknown_voice(tmp_path):
    seed(tmp_path, "cs_CZ-kasandra-medium")
    (tts.voices_dir(tmp_path) / "cs_CZ-kasandra-medium.onnx.json").unlink()  # model bez configu není stažený hlas
    for name in (tts.DEFAULT, "cs_CZ-kasandra-medium", "../secret"):
        with pytest.raises(tts.VoiceMissing):
            tts.synthesize(tmp_path, "Ahoj.", name, load=lambda path: FakeVoice())


def test_available_lists_only_downloaded(tmp_path):
    assert tts.available(tmp_path) == {"available": [], "default": None}
    seed(tmp_path, "cs_CZ-kasandra-medium")
    assert tts.available(tmp_path) == {
        "available": [{"id": "cs_CZ-kasandra-medium", "label": "Kasandra", "gender": "female"}],
        "default": "cs_CZ-kasandra-medium"}
    seed(tmp_path, tts.DEFAULT)
    assert tts.available(tmp_path)["default"] == tts.DEFAULT


def test_warm_swallows_missing_voice(tmp_path):
    tts.warm(tmp_path, tts.DEFAULT, load=lambda path: FakeVoice())
