"""Klient TypeSafe Jev: jediné místo, kde Opora volá placené API (docs/asistent.md §13, §13.2).

Jev negeneruje text. Na `state + questions` vrací typované odpovědi (`choice`, `score`, `noul`)
s pravděpodobností. Asistentovi jen zrychluje volbu podkladu; když klíč chybí nebo služba
neodpoví, vrátí `None` a asistent běží jako bez něj. Klíč žije jen v hlavičce požadavku.
"""

import json
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
TIMEOUT_SECONDS = 3.0
MAX_RESPONSE_BYTES = 256 * 1024


def _post(url, body, headers, timeout):
    """Výchozí přenos: bez proxy; vrací `(status, bytes)`."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def evaluate(state, questions, *, key, timeout=TIMEOUT_SECONDS, post=_post):
    """Odpovědi `{klíč otázky: odpověď}`, nebo `None` při jakékoli poruše. Nikdy nevyhodí."""
    if not key or not questions:
        return None
    body = json.dumps({"state": state, "model": MODEL, "questions": questions}, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
    try:
        status, raw = post(ENDPOINT, body, headers, timeout)
        if status != 200 or not raw or len(raw) > MAX_RESPONSE_BYTES:
            return None
        answers = json.loads(raw).get("answers")
    except Exception:  # noqa: BLE001 — síť, timeout, neplatný JSON: Jev je jen zrychlení, ne podmínka
        return None
    return answers if isinstance(answers, dict) else None
