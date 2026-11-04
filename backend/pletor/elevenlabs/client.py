"""Hlas Pletora přes ElevenLabs (REST, placený cloud): text odpovědi odchází z počítače a stojí znaky z tarifu.

Klíč `ELEVENLABS_API_KEY` je tajný: bere se z prostředí procesu, jinak z `.env` v kořeni repa (jen řádky
`ELEVENLABS_*`), posílá se jen v hlavičce `xi-api-key` a nikdy se nevrací klientovi ani nepíše do logu či chyb.
Dostupnost se ověřuje bez spotřeby znaků (`GET /v1/voices` + `GET /v1/user/subscription`, cache 60 s);
selhání syntézy (403 tarif, 401 klíč, limit) hlas do dalšího ověření označí za nedostupný s důvodem.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from backend.pletor.tts import EngineMissing

API = "https://api.elevenlabs.io/v1"
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
VOICE = "elevenlabs:voice"
TTL = 60
CHECK_TIMEOUT = 5
SPEAK_TIMEOUT = 20
FORMAT = "mp3_44100_128"  # MP3 jako Edge: okno ho dekóduje stejně
PAID_VOICES = {"free", "starter"}  # profesionální klon (PVC) chce tarif Creator a výš

_lock = threading.Lock()
_state = {"voice_id": None, "category": None, "checked": 0.0, "reason": None, "quota": None}


def settings(environ=None, env_file=None):
    """Nastavení z prostředí, jinak z `.env`; ostatní řádky `.env` se ignorují (žádný dotenv)."""
    found = {}
    try:
        lines = Path(env_file or ENV_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and key.strip().startswith("ELEVENLABS_"):
            found[key.strip()] = value.strip().strip("\"'")
    found.update({key: value for key, value in (os.environ if environ is None else environ).items()
                  if key.startswith("ELEVENLABS_") and value})
    return {"key": found.get("ELEVENLABS_API_KEY", ""), "voice": found.get("ELEVENLABS_VOICE") or "Pletor_MH",
            "voice_id": found.get("ELEVENLABS_VOICE_ID") or None,
            "model": found.get("ELEVENLABS_MODEL") or "eleven_flash_v2_5"}


def label():
    return f"ElevenLabs · {settings()['voice']}"


def problem(status, body, voice):
    """Česky srozumitelný důvod z chybové odpovědi ElevenLabs (bez klíče a bez surového těla)."""
    try:
        detail = json.loads(body).get("detail") or {}
    except (ValueError, AttributeError):
        detail = {}
    code = detail.get("status", "") if isinstance(detail, dict) else ""
    if code == "quota_exceeded" or status == 402:
        return "vyčerpán limit znaků ElevenLabs"
    if code == "subscription_required" or (status == 403 and "subscription" in str(detail).lower()):
        return f"hlas {voice} vyžaduje tarif Creator"
    if status in (401, 403):
        return "klíč ElevenLabs nemá oprávnění (Text to Speech, Voices: Read, User: Read)"
    if status == 429:
        return "ElevenLabs odmítá další požadavky (limit souběhu), zkus za chvíli"
    if status == 404:
        return f"hlas {voice} na účtu ElevenLabs není"
    return f"ElevenLabs vrátil HTTP {status}"


def _open(path, cfg, urlopen, body=None, timeout=CHECK_TIMEOUT):
    request = urllib.request.Request(f"{API}{path}", body, {"xi-api-key": cfg["key"], "Content-Type": "application/json"})
    try:
        return (urlopen or urllib.request.urlopen)(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        raise EngineMissing(problem(error.code, error.read(), cfg["voice"])) from None
    except OSError as error:  # síť, DNS, timeout; text chyby neobsahuje hlavičky ani klíč
        raise EngineMissing(f"ElevenLabs neodpověděl: {error.__class__.__name__}") from None


def _json(path, cfg, urlopen):
    with _open(path, cfg, urlopen) as response:
        return json.loads(response.read())


def _voice_id(cfg, urlopen):
    """Id hlasu: `ELEVENLABS_VOICE_ID`, jinak podle jména přes `GET /v1/voices` (jednou, pak z paměti)."""
    if cfg["voice_id"]:
        return cfg["voice_id"]
    if _state["voice_id"] is None:
        for voice in _json("/voices", cfg, urlopen).get("voices", []):
            name = str(voice.get("name", ""))  # premade hlasy se jmenují „Daniel - Steady Broadcaster“
            if cfg["voice"].casefold() in (name.casefold(), re.split(r"\s[-–]\s", name, maxsplit=1)[0].casefold()):
                _state.update(voice_id=voice["voice_id"], category=voice.get("category"))
                break
        else:
            raise EngineMissing(f"hlas {cfg['voice']} na účtu ElevenLabs není")
    return _state["voice_id"]


def _check(cfg, urlopen):
    """`(důvod, kvóta)` bez spotřeby znaků: hlas existuje, tarif ho smí a zbývají znaky."""
    if not cfg["key"]:
        return "chybí ELEVENLABS_API_KEY (prostředí nebo .env v kořeni repa)", None
    try:
        sub = _json("/user/subscription", cfg, urlopen)
        quota = {key: sub.get(key) for key in ("tier", "character_count", "character_limit")}
        _voice_id(cfg, urlopen)
    except EngineMissing as error:
        return str(error), None
    except (ValueError, KeyError, TypeError, AttributeError):
        return "ElevenLabs vrátil nečekanou odpověď", None
    if isinstance(quota["character_limit"], int) and (quota["character_count"] or 0) >= quota["character_limit"]:
        return "vyčerpán limit znaků ElevenLabs", quota
    if _state["category"] == "professional" and quota["tier"] in PAID_VOICES:
        return f"hlas {cfg['voice']} vyžaduje tarif Creator", quota
    return None, quota


def status(urlopen=None, now=time.monotonic):
    """`(důvod nebo None, kvóta {tier, character_count, character_limit} nebo None)`, cache 60 s."""
    with _lock:
        if not _state["checked"] or now() - _state["checked"] >= TTL:
            reason, quota = _check(settings(), urlopen)
            _state.update(checked=now(), reason=reason, quota=quota)
        return _state["reason"], _state["quota"]


def _remember(reason, now=time.monotonic):
    """Výsledek skutečné syntézy platí místo kontroly dalších 60 s (403 za tarif tak zůstane vidět)."""
    with _lock:
        _state.update(reason=reason, checked=now())


def stream(text, urlopen=None):
    """Text → kousky MP3, jak je cloud posílá. Chyba (tarif, klíč, limit, síť) je `EngineMissing` dřív, než route
    pošle 200, a do dalšího ověření hlas označí za nedostupný."""
    cfg = settings()
    if not cfg["key"]:
        raise EngineMissing("chybí ELEVENLABS_API_KEY (prostředí nebo .env v kořeni repa)")
    body = json.dumps({"text": text, "model_id": cfg["model"]}).encode()
    try:
        response = _open(f"/text-to-speech/{_voice_id(cfg, urlopen)}/stream?output_format={FORMAT}", cfg, urlopen,
                         body, SPEAK_TIMEOUT)
    except EngineMissing as error:
        _remember(str(error))
        raise
    _remember(None)

    def chunks():
        with response:
            while block := response.read1(65536):
                yield block
    return chunks()


def reset():
    """Zapomene id hlasu, kvótu i důvod (testy, změna nastavení)."""
    with _lock:
        _state.update(voice_id=None, category=None, checked=0.0, reason=None, quota=None)
