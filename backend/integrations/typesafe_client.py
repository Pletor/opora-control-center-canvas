"""Klient TypeSafe Jev: jediné místo, kde Opora volá placené API (docs/asistent.md §13, §13.2).

Jev negeneruje text. Na `state + questions` vrací typované odpovědi (`choice`, `score`, `noul`)
s pravděpodobností. Asistentovi jen zrychluje volbu podkladu; když klíč chybí nebo služba
neodpoví, vrátí `None` a asistent běží jako bez něj. Klíč žije jen v hlavičce požadavku.

Poskytovatel (docs/schranka-neurony.md §7): `typesafe` (výchozí) nebo `celeris`, který implementuje
totéž System One API. Adresa a model jsou jen z pevného seznamu `PROVIDERS`; požadavek se nikdy
nepřesměruje (opener bez obsluhy přesměrování, 3xx = porucha), aby klíč neodešel jinam.
Volba poskytovatele přichází z `opora.local.toml` (`[jev] provider`) přes proměnnou `OPORA_JEV_PROVIDER`.
"""

import json
import logging
import os
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
CELERIS_ENDPOINT = "https://inference.celeris.ai/celeris-1-decision/v1/systemone"
CELERIS_MODEL = "celeris-1-decision"
PROVIDERS = {"typesafe": (ENDPOINT, MODEL), "celeris": (CELERIS_ENDPOINT, CELERIS_MODEL)}
DEFAULT_PROVIDER = "typesafe"
PROVIDER_ENV = "OPORA_JEV_PROVIDER"
ALLOWED_ENDPOINTS = frozenset(endpoint for endpoint, _model in PROVIDERS.values())
TIMEOUT_SECONDS = 3.0
MAX_RESPONSE_BYTES = 256 * 1024
LOGGER = logging.getLogger(__name__)


def provider_from(value):
    """Platný poskytovatel; prázdná hodnota = výchozí, neznámá = výchozí s varováním v logu."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_PROVIDER
    name = value.strip().lower() if isinstance(value, str) else None
    if name in PROVIDERS:
        return name
    LOGGER.warning("Neznámý poskytovatel Jev %r v [jev] provider; použije se %s.", str(value)[:40], DEFAULT_PROVIDER)
    return DEFAULT_PROVIDER


def configured_provider(environ=None):
    """Poskytovatel z prostředí backendu (`OPORA_JEV_PROVIDER`, nastaví ho `uv run opora` z TOML)."""
    return provider_from((os.environ if environ is None else environ).get(PROVIDER_ENV))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Přesměrování se nenásleduje: urllib pak vyhodí HTTPError s kódem 3xx."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener():
    """Opener bez proxy a bez přesměrování (nahrazuje výchozí HTTPRedirectHandler)."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _post(url, body, headers, timeout):
    """Výchozí přenos: jen adresa z allowlistu, bez proxy a bez přesměrování; vrací `(status, bytes)`."""
    if url not in ALLOWED_ENDPOINTS:
        raise ValueError("Adresa Jev není na seznamu povolených.")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with build_opener().open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def evaluate(state, questions, *, key, provider=DEFAULT_PROVIDER, timeout=TIMEOUT_SECONDS, post=_post):
    """Odpovědi `{klíč otázky: odpověď}`, nebo `None` při jakékoli poruše. Nikdy nevyhodí.

    Neznámý `provider` nic neodešle (adresa se bere jen z `PROVIDERS`)."""
    if not key or not questions or provider not in PROVIDERS:
        return None
    endpoint, model = PROVIDERS[provider]
    body = json.dumps({"state": state, "model": model, "questions": questions}, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
    try:
        status, raw = post(endpoint, body, headers, timeout)
        if status != 200 or not raw or len(raw) > MAX_RESPONSE_BYTES:
            return None
        answers = json.loads(raw).get("answers")
    except Exception:  # noqa: BLE001 — síť, timeout, neplatný JSON: Jev je jen zrychlení, ne podmínka
        return None
    return answers if isinstance(answers, dict) else None
