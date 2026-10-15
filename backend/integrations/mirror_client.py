"""Klient Zrcadla (BioCortexAI): lokální vývojový sidecar na loopbacku (docs/zrcadlo.md).

Zrcadlo je orientační ukazatel, nikdy podmínka: `health`, `predict` a `observe` vrací `None`, když je
vypnuté, adresa není loopback, služba neodpoví do 2 s, odpoví jinak než 200 nebo neplatným tvarem.
Nikdy nevyhodí. Požadavek jde jen na `http://127.0.0.1|localhost:<port>`, bez proxy a bez přesměrování
(stejný opener jako `typesafe_client`: 3xx = porucha).

Zapnutí: `opora.local.toml` `[mirror] enabled = true, url = "...", projects = ["<id>"]`; `uv run opora` ho předá
proměnnými `OPORA_MIRROR_URL` (prázdná = vypnuto) a `OPORA_MIRROR_PROJECTS` (id oddělená čárkou). Projekt
mimo seznam Zrcadlo nevolá. Nelokální nebo neplatná adresa = vypnuto + varování v logu.
"""

import json
import logging
import math
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from backend.integrations.typesafe_client import build_opener

URL_ENV = "OPORA_MIRROR_URL"
PROJECTS_ENV = "OPORA_MIRROR_PROJECTS"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
TIMEOUT_SECONDS = 2.0
MAX_RESPONSE_BYTES = 64 * 1024
MAX_TITLE = 500
MAX_TEXT = 8000
MAX_MICROSTEP = 500
MAX_ID = 100
HORMONES = ("dopamin", "serotonin", "kortizol", "oxytocin")
TESTS = ("pass", "fail")
# Služba přijímá kola kritika 0–2; brána `verified` dovoluje 0–3, proto se skutečnost ořízne na 2.
MAX_ROUNDS = 2
LOGGER = logging.getLogger(__name__)
_warned = set()


def loopback_url(value):
    """Základní adresa služby `http://127.0.0.1|localhost[:port]` bez cesty, nebo None."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        return None
    if (parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS or parts.username or parts.password
            or parts.path not in ("", "/") or parts.query or parts.fragment):
        return None
    return f"http://{parts.hostname}" + (f":{port}" if port else "")


def settings(environ=None):
    """`{url, projects}` z prostředí backendu; `url` None = vypnuto (prázdné nebo nelokální s varováním)."""
    env = os.environ if environ is None else environ
    raw = (env.get(URL_ENV) or "").strip()
    url = loopback_url(raw)
    if raw and url is None and raw not in _warned:
        _warned.add(raw)
        LOGGER.warning("Zrcadlo: adresa %r v [mirror] url není http://127.0.0.1 ani localhost; Zrcadlo je vypnuté.", raw[:80])
    projects = frozenset(item.strip() for item in (env.get(PROJECTS_ENV) or "").split(",") if item.strip())
    return {"url": url, "projects": projects}


def client_for(project, environ=None):
    """Klient Zrcadla pro projekt, nebo None (vypnuto, neplatná adresa, projekt není v `[mirror] projects`)."""
    found = settings(environ)
    if found["url"] is None or project not in found["projects"]:
        return None
    return MirrorClient(found["url"])


def _request(method, url, body, timeout):
    """Výchozí přenos: jen loopback, bez proxy a bez přesměrování; vrací `(status, bytes)`."""
    if loopback_url(url.rsplit("/", 1)[0]) is None:
        raise ValueError("Adresa Zrcadla není loopback.")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with build_opener().open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def _unit(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _rounds(value):
    return type(value) is int and 0 <= value <= MAX_ROUNDS


def valid_health(data):
    if isinstance(data, dict) and data.get("ok") is True and isinstance(data.get("model"), str) \
            and type(data.get("events")) is int:
        return {"ok": True, "model": data["model"][:200], "events": data["events"]}
    return None


def valid_prediction(data):
    if not isinstance(data, dict):
        return None
    pid, expected, confidence = data.get("predictionId"), data.get("expected"), data.get("confidence")
    if not isinstance(pid, str) or not pid or len(pid) > MAX_ID or not isinstance(expected, dict) \
            or expected.get("tests") not in TESTS or not _rounds(expected.get("criticRounds")) or not _unit(confidence):
        return None
    return {"predictionId": pid, "expected": {"tests": expected["tests"], "criticRounds": expected["criticRounds"]},
            "confidence": confidence}


def valid_observation(data):
    if not isinstance(data, dict):
        return None
    hormones = data.get("hormones")
    if not _unit(data.get("predictionError")) or not _unit(data.get("accuracy")) or not isinstance(hormones, dict) \
            or not all(_number(hormones.get(name)) for name in HORMONES):
        return None
    return {"predictionError": data["predictionError"], "accuracy": data["accuracy"],
            "hormones": {name: hormones[name] for name in HORMONES}}


class MirrorClient:
    """Volání jedné služby Zrcadla. Každá metoda vrací ověřený dict, nebo None. Nikdy nevyhodí."""

    def __init__(self, url, *, timeout=TIMEOUT_SECONDS, transport=_request):
        self.url = loopback_url(url)
        self.timeout = timeout
        self.transport = transport

    def _call(self, method, path, body, check):
        if self.url is None:
            return None
        try:
            data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
            status, raw = self.transport(method, self.url + path, data, self.timeout)
            if status != 200 or not raw or len(raw) > MAX_RESPONSE_BYTES:
                return None
            return check(json.loads(raw))
        except Exception:  # noqa: BLE001 — síť, timeout, neplatný JSON: Zrcadlo je orientační, ne podmínka
            return None

    def health(self):
        return self._call("GET", "/health", None, valid_health)

    def predict(self, *, fragment_id, discipline, title, text, microstep):
        body = {"fragmentId": str(fragment_id)[:200], "discipline": str(discipline)[:100], "title": str(title)[:MAX_TITLE],
                "text": str(text)[:MAX_TEXT], "microstep": None if microstep is None else str(microstep)[:MAX_MICROSTEP]}
        return self._call("POST", "/predict", body, valid_prediction)

    def observe(self, *, prediction_id, actual):
        if not isinstance(prediction_id, str) or not prediction_id or not isinstance(actual, dict):
            return None
        rounds = actual.get("criticRounds")
        tests = actual.get("tests")
        extra = {}
        if tests == "untested":  # služba čeká pass/fail: pro neběžené testy odvodit z planApproved (§13)
            approved = actual["planApproved"] if type(actual.get("planApproved")) is bool else False
            tests = "pass" if approved else "fail"
            extra["testsReported"] = "untested"
        if type(actual.get("planApproved")) is bool:
            extra["planApproved"] = actual["planApproved"]
        if type(actual.get("planScore")) is int:
            extra["planScore"] = actual["planScore"]
        body = {"predictionId": prediction_id[:MAX_ID],
                "actual": {"tests": tests, "criticRounds": min(rounds, MAX_ROUNDS) if type(rounds) is int else rounds,
                           "unexpected": bool(actual.get("unexpected")), **extra}}
        return self._call("POST", "/observe", body, valid_observation)
