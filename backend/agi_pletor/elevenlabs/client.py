"""Hlas Pletora přes ElevenLabs (REST, placený cloud): text odpovědi odchází z počítače a stojí znaky z tarifu.

Klíč `ELEVENLABS_API_KEY` je tajný: bere se z prostředí procesu, jinak z `.env` v kořeni repa (jen řádky
`ELEVENLABS_*`), posílá se jen v hlavičce `xi-api-key` a nikdy se nevrací klientovi ani nepíše do logu či chyb.
Hlasů je víc (`elevenlabs:brian`, `elevenlabs:bill`, `elevenlabs:custom` z `.env`). Dostupnost se ověřuje bez
spotřeby znaků (`GET /v1/user/subscription` jednou za účet, `GET /v1/voices` za hlas, cache 60 s); selhání syntézy
(403 tarif, 401 klíč, limit) do dalšího ověření označí za nedostupný jen ten hlas, který selhal.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from backend.agi_pletor.tts import EngineMissing, VoiceMissing

API = "https://api.elevenlabs.io/v1"
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
PREFIX = "elevenlabs:"
LEGACY = "elevenlabs:voice"  # jediný hlas do #334; uložená volba se mapuje na `custom`, jinak na `brian`
PREMADE = {"brian": ("Brian", "Brian · hluboký, konejšivý"), "bill": ("Bill", "Bill · moudrý, vyrovnaný")}
TTL = 60
CHECK_TIMEOUT = 5
SPEAK_TIMEOUT = 20
FORMAT = "mp3_44100_128"  # MP3 jako Edge: okno ho dekóduje stejně
PAID_VOICES = {"free", "starter"}  # profesionální klon (PVC) chce tarif Creator a výš

_lock = threading.Lock()
_account = {"checked": 0.0, "reason": None, "quota": None}  # klíč, síť a kvóta platí pro všechny hlasy
_voices = {}  # klíč hlasu → {voice_id, category, checked, reason}: selhání jednoho hlasu nezhasne ostatní


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
            "custom": bool(found.get("ELEVENLABS_VOICE") or found.get("ELEVENLABS_VOICE_ID")),
            "model": found.get("ELEVENLABS_MODEL") or "eleven_multilingual_v2"}


def voices(cfg=None):
    """`{klíč: (jméno na účtu, štítek)}` v pořadí výchozí volby: Brian, Bill, a `custom` jen z `.env`."""
    cfg = cfg or settings()
    found = dict(PREMADE)
    if cfg["custom"]:
        found["custom"] = (cfg["voice"], cfg["voice"])
    return found


def key(voice, cfg=None):
    """Id hlasu (`elevenlabs:brian`) → klíč; stará volba `elevenlabs:voice` → `custom`, jinak `brian`."""
    cfg = cfg or settings()
    if voice == LEGACY:
        return "custom" if cfg["custom"] else "brian"
    name = voice.removeprefix(PREFIX)
    if name not in voices(cfg):
        raise VoiceMissing(f"ElevenLabs hlas {voice} nezná (známé: {', '.join(PREFIX + k for k in voices(cfg))})")
    return name


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


def _open(path, cfg, urlopen, body=None, timeout=CHECK_TIMEOUT, voice=""):
    request = urllib.request.Request(f"{API}{path}", body, {"xi-api-key": cfg["key"], "Content-Type": "application/json"})
    try:
        return (urlopen or urllib.request.urlopen)(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        raise EngineMissing(problem(error.code, error.read(), voice)) from None
    except OSError as error:  # síť, DNS, timeout; text chyby neobsahuje hlavičky ani klíč
        raise EngineMissing(f"ElevenLabs neodpověděl: {error.__class__.__name__}") from None


def _json(path, cfg, urlopen):
    with _open(path, cfg, urlopen) as response:
        return json.loads(response.read())


def _state(name):
    return _voices.setdefault(name, {"voice_id": None, "category": None, "checked": 0.0, "reason": None})


def _voice_id(cfg, name, urlopen):
    """Id hlasu: u `custom` `ELEVENLABS_VOICE_ID`, jinak podle jména přes `GET /v1/voices` (jednou, pak z paměti)."""
    if name == "custom" and cfg["voice_id"]:
        return cfg["voice_id"]
    state, wanted = _state(name), voices(cfg)[name][0]
    if state["voice_id"] is None:
        for voice in _json("/voices", cfg, urlopen).get("voices", []):
            title = str(voice.get("name", ""))  # premade hlasy se jmenují „Brian - Deep, Resonant and Comforting“
            if wanted.casefold() in (title.casefold(), re.split(r"\s[-–]\s", title, maxsplit=1)[0].casefold()):
                state.update(voice_id=voice["voice_id"], category=voice.get("category"))
                break
        else:
            raise EngineMissing(f"hlas {wanted} na účtu ElevenLabs není")
    return state["voice_id"]


def _check_account(cfg, urlopen):
    """`(důvod, kvóta)` účtu bez spotřeby znaků: klíč platí a zbývají znaky."""
    if not cfg["key"]:
        return "chybí ELEVENLABS_API_KEY (prostředí nebo .env v kořeni repa)", None
    try:
        sub = _json("/user/subscription", cfg, urlopen)
        quota = {key: sub.get(key) for key in ("tier", "character_count", "character_limit")}
    except EngineMissing as error:
        return str(error), None
    except (ValueError, TypeError, AttributeError):
        return "ElevenLabs vrátil nečekanou odpověď", None
    if isinstance(quota["character_limit"], int) and (quota["character_count"] or 0) >= quota["character_limit"]:
        return "vyčerpán limit znaků ElevenLabs", quota
    return None, quota


def _check_voice(cfg, name, quota, urlopen):
    """Proč tenhle hlas nejde (není na účtu, PVC na free tarifu), jinak `None`."""
    try:
        _voice_id(cfg, name, urlopen)
    except EngineMissing as error:
        return str(error)
    except (ValueError, KeyError, TypeError, AttributeError):
        return "ElevenLabs vrátil nečekanou odpověď"
    if _state(name)["category"] == "professional" and (quota or {}).get("tier") in PAID_VOICES:
        return f"hlas {voices(cfg)[name][0]} vyžaduje tarif Creator"
    return None


def status(name, urlopen=None, now=time.monotonic):
    """`(důvod nebo None, kvóta {tier, character_count, character_limit} nebo None)` hlasu `name`, cache 60 s.
    Účet (klíč, síť, kvóta) je společný všem hlasům, důvod hlasu má každý vlastní."""
    cfg = settings()
    with _lock:
        if not _account["checked"] or now() - _account["checked"] >= TTL:
            reason, quota = _check_account(cfg, urlopen)
            _account.update(checked=now(), reason=reason, quota=quota)
        if _account["reason"]:
            return _account["reason"], _account["quota"]
        state = _state(name)
        if not state["checked"] or now() - state["checked"] >= TTL:
            state.update(checked=now(), reason=_check_voice(cfg, name, _account["quota"], urlopen))
        return state["reason"], _account["quota"]


def _remember(name, reason, now=time.monotonic):
    """Výsledek skutečné syntézy platí pro tenhle hlas místo kontroly dalších 60 s (403 za tarif zůstane vidět)."""
    with _lock:
        _state(name).update(reason=reason, checked=now())


def stream(text, voice, urlopen=None):
    """Text → kousky MP3 hlasem `voice` (`elevenlabs:brian`…), jak je cloud posílá. Neznámý hlas je `VoiceMissing`,
    chyba (tarif, klíč, limit, síť) `EngineMissing` dřív, než route pošle 200, a do dalšího ověření zhasne jen
    tenhle hlas."""
    cfg = settings()
    name = key(voice, cfg)
    if not cfg["key"]:
        raise EngineMissing("chybí ELEVENLABS_API_KEY (prostředí nebo .env v kořeni repa)")
    body = json.dumps({"text": text, "model_id": cfg["model"]}).encode()
    try:
        with _lock:
            voice_id = _voice_id(cfg, name, urlopen)
        response = _open(f"/text-to-speech/{voice_id}/stream?output_format={FORMAT}", cfg, urlopen, body,
                         SPEAK_TIMEOUT, voices(cfg)[name][0])
    except EngineMissing as error:
        _remember(name, str(error))
        raise
    _remember(name, None)

    def chunks():
        with response:
            while block := response.read1(65536):
                yield block
    return chunks()


def reset():
    """Zapomene id hlasů, kvótu i důvody (testy, změna nastavení)."""
    with _lock:
        _account.update(checked=0.0, reason=None, quota=None)
        _voices.clear()
