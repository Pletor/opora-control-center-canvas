"""Hlas Pletora (P3b): česká syntéza řeči lokálně na CPU přes Piper TTS (`piper-tts`, GPL-3, skupina `tts`).

Modely leží v `<data>/pletor/voices/<hlas>.onnx` + `.onnx.json`; stahuje je jen `tts_fetch` na výslovný příkaz,
za běhu se nic nestahuje. Hlas se načte jednou a drží v paměti; `piper` se importuje až při prvním načtení.
"""
import io
import threading
import wave
from pathlib import Path

VOICES = {"cs_CZ-jirka-medium": ("Jirka", "male"), "cs_CZ-kasandra-medium": ("Kasandra", "female")}
DEFAULT = "cs_CZ-jirka-medium"
TEXT_LIMIT = 600
FOLDER = "voices"

_cache = {}
_lock = threading.Lock()


class VoiceMissing(LookupError):
    """Hlas není mezi známými, nebo jeho model není stažený."""


class EngineMissing(RuntimeError):
    """Balíček `piper-tts` není nainstalovaný."""


def voices_dir(folder):
    return Path(folder) / FOLDER


def _model(folder, name):
    path = voices_dir(folder) / f"{name}.onnx"
    return path if name in VOICES and path.is_file() and Path(f"{path}.json").is_file() else None


def available(folder):
    """Jen skutečně stažené hlasy `[{id, label, gender}]` a výchozí (Jirka, jinak první stažený, jinak `None`)."""
    found = [{"id": name, "label": label, "gender": gender} for name, (label, gender) in VOICES.items()
             if _model(folder, name)]
    ids = [voice["id"] for voice in found]
    return {"available": found, "default": DEFAULT if DEFAULT in ids else (ids[0] if ids else None)}


def _load(path):
    try:
        from piper import PiperVoice
    except ImportError as error:
        raise EngineMissing("Piper TTS není nainstalovaný: uv sync --group tts.") from error
    return PiperVoice.load(path, use_cuda=False)  # GPU drží Ollama; Piper je i na CPU rychlejší než realtime


def _voice(folder, name, load):
    path = _model(folder, name)
    if path is None:
        raise VoiceMissing(f"uv run python -m backend.agi_pletor.tts_fetch {name if name in VOICES else DEFAULT}")
    with _lock:
        if path not in _cache:
            _cache[path] = (load or _load)(path)
        return _cache[path]


def warm(folder, name, load=None):
    """Načte hlas dopředu (první načtení trvá 3–5 s, syntéza věty pak ~0,2 s); chyba se ukáže až při syntéze."""
    try:
        _voice(folder, name, load)
    except (VoiceMissing, EngineMissing, OSError, RuntimeError):
        pass


def synthesize(folder, text, name=DEFAULT, load=None):
    """Text → WAV 16 bit mono v rychlosti modelu (22 050 Hz). Formát se píše vždy, i když model nic nevysloví."""
    voice = _voice(folder, name, load)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(voice.config.sample_rate)
        voice.synthesize_wav(text, wav, set_wav_format=False)
    return buffer.getvalue()
