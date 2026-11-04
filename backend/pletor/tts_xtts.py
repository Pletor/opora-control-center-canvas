"""Hlas Pletora přes XTTS-v2 (Coqui, licence modelu CPML: jen nekomerčně) na GPU v odděleném procesu.

Torch s CUDA žije ve vlastním prostředí `tools/xtts_server/.venv` (`uv sync --project tools/xtts_server`).
Pomocný server se spustí líně při první potřebě, drží model ve VRAM a skončí s backendem (`close()` nebo
zavřený stdin). Model leží v `<data>/pletor/voices/xtts/` (stahuje jen `tts_fetch xtts`), vlastní hlas ke
klonování v `xtts/reference/jarvis.wav` (6–15 s); bez něj klon chybí a čte vestavěný mluvčí.
"""
import json
import queue
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

from backend.pletor.tts import EngineMissing, VoiceMissing, voices_dir

VOICES = {"xtts:default": ("Výchozí", "male"), "xtts:clone": ("Klon (jarvis.wav)", "male")}
FILES = ("model.pth", "config.json", "vocab.json", "speakers_xtts.pth")
NEED_MB = 2600  # naměřeno: model + inference ~2,3 GB VRAM, rezerva na špičku dlouhé věty
START_TIMEOUT = 180  # první načtení modelu z disku do GPU (studený start ~20–40 s)
SERVER = Path(__file__).resolve().parents[2] / "tools" / "xtts_server"
FETCH = "uv run python -m backend.pletor.tts_fetch xtts"
MEDIA = "audio/pcm;rate=24000"  # okno z kousků skládá AudioBuffer samo, bez čekání na celou větu

_lock = threading.Lock()
_process = {"proc": None, "port": None}


def model_dir(folder):
    return voices_dir(folder) / "xtts"


def reference(folder):
    return model_dir(folder) / "reference" / "jarvis.wav"


def downloaded(folder):
    return all((model_dir(folder) / name).is_file() for name in FILES)


def python():
    return SERVER / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def free_vram_mb():
    """Volná paměť GPU v MB podle `nvidia-smi`, nebo `None` bez GPU NVIDIA."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5, check=True).stdout
        return int(out.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def reason(folder, voice, vram=None):
    """Proč hlas XTTS nejde použít (`None` = jde). Běžící server už paměť drží, VRAM se pak neměří."""
    if voice == "xtts:clone" and not reference(folder).is_file():
        return f"chybí vlastní vzorek {reference(folder)} (6–15 s WAV)"
    if not python().is_file():
        return "nenainstalováno: uv sync --project tools/xtts_server"
    if not downloaded(folder):
        return f"model není stažen: {FETCH}"
    if _process["proc"] is not None and _process["proc"].poll() is None:
        return None
    free = (vram or free_vram_mb)()
    if free is None:
        return "bez GPU NVIDIA (nvidia-smi neodpovídá)"
    if free < NEED_MB:
        return (f"málo paměti GPU: volno {free} MB z potřebných ~{NEED_MB} MB; "
                "přepni lokální mozek na menší model (qwen3:8b) nebo ho vypni")
    return None


def _start(folder):
    try:
        proc = subprocess.Popen([str(python()), str(SERVER / "server.py"), str(model_dir(folder))],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    except OSError as error:
        raise EngineMissing(f"XTTS se nespustil: {error}") from error
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(proc.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=START_TIMEOUT)
    except queue.Empty:
        line = ""
    if not line.startswith("READY "):
        proc.kill()
        raise EngineMissing("XTTS se nespustil (podrobnosti v konzoli backendu).")
    _process.update(proc=proc, port=int(line.split()[1]))


def _ensure(folder):
    with _lock:
        if _process["proc"] is None or _process["proc"].poll() is not None:
            _start(folder)
        return _process["port"]


def warm(folder, voice="xtts:default"):
    """Spustí server dopředu, aby první odpověď nečekala na načtení modelu; chyba se ukáže až při syntéze."""
    if reason(folder, voice) is None:
        try:
            _ensure(folder)
        except EngineMissing:
            pass


def stream(folder, text, voice="xtts:default", urlopen=urllib.request.urlopen):
    """Text → kousky PCM 16 bit LE mono 24 kHz (`MEDIA`), jak je GPU vyrábí (první ~0,5 s po požadavku). Server odpoví až
    s prvním kouskem, takže chyba je výjimka tady: nestažený model 404, ostatní důvody (VRAM, instalace, pád) 503."""
    if voice not in VOICES or not downloaded(folder):
        raise VoiceMissing(FETCH)
    problem = reason(folder, voice)
    if problem:
        raise EngineMissing(problem)
    body = {"text": text, "reference": str(reference(folder)) if voice == "xtts:clone" else None}
    request = urllib.request.Request(f"http://127.0.0.1:{_ensure(folder)}/tts", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
    try:
        response = urlopen(request, timeout=60)
    except OSError as error:
        raise EngineMissing(f"XTTS neodpověděl: {error}") from error

    def chunks():
        with response:
            while block := response.read1(65536):
                yield block
    return chunks()


def close():
    """Ukončí pomocný server a uvolní VRAM (lifespan backendu)."""
    with _lock:
        proc, _process["proc"] = _process["proc"], None
    if proc is not None and proc.poll() is None:
        proc.stdin.close()  # server skončí sám při zavřeném stdin; kill je pojistka
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
