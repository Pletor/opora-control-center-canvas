"""Mozky Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P2): `claude` (výchozí, Claude Code pod předplatným,
`session.turn`) a `ollama` (lokální model přes Ollamu na `URL`). Oba vrací `(reply, actions)` z `session.parse_reply`,
takže `actions.validate` platí beze změny. Volba mozku je jedna pro aplikaci v `<data>/pletor/settings.json`
(`store.settings`). Přepínací věta v chatu (`command`) se rozpozná bez modelu a modelu se nepředá.
"""
import json
import re
import unicodedata
import urllib.request

from backend.brain_opora.heart import command as claude_command
from backend.brain_opora.heart.process import run_process
from backend.pletor import session, store

CLAUDE, OLLAMA = "claude", "ollama"
URL = "http://127.0.0.1:11434"
TIMEOUT = 180
TAGS_TIMEOUT = 3  # stav se čte při každém pollu okna; neběžící Ollama nesmí okno brzdit
PREFERRED = ("qwen3.5", "gemma")


def http(method, path, body=None, timeout=TIMEOUT):
    """Transport do Ollamy: JSON tam i zpět. Testy vstřikují falešný, žádná síť."""
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(URL + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def models(transport=http):
    """Nainstalované chatovací modely Ollamy (`/api/tags`, bez embeddingů); chyba nebo neběžící Ollama = `[]`."""
    try:
        listed = transport("GET", "/api/tags", None, TAGS_TIMEOUT)["models"]
        names = [item["name"] for item in listed]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [name for name in names if isinstance(name, str) and "embed" not in name]


def default_model(available):
    return next((name for name in available if name.startswith(PREFERRED)), available[0] if available else None)


def status(folder, transport=http):
    """`{brain, model, available}` pro stav okna."""
    chosen = store.settings(folder)
    model = chosen["ollamaModel"] if chosen["brain"] == OLLAMA else session.MODEL
    return {"brain": chosen["brain"], "model": model, "available": models(transport)}


def switch(folder, brain, model=None, transport=http):
    """Přepne mozek a vrátí `(ok, věta pro člověka)`; selhání nechá nastavení beze změny (zůstává předchozí mozek)."""
    chosen = store.settings(folder)
    if brain == CLAUDE:
        store.save_settings(folder, {**chosen, "brain": CLAUDE})
        return True, "Zpátky na Claude, pane."
    available = models(transport)
    if not available:
        return False, "Ollama neběží nebo nemá žádný model. Zůstávám na Claude."
    if model and model not in available:
        return False, f"Model {model} v Ollamě není. Mám: {', '.join(available)}."
    model = model or (chosen["ollamaModel"] if chosen["ollamaModel"] in available else default_model(available))
    store.save_settings(folder, {"brain": OLLAMA, "ollamaModel": model})
    return True, f"Lokální mozek zapnut, pane ({model}). Teď nic nestojím."


def _plain(text):
    folded = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in folded if not unicodedata.combining(char)).strip().rstrip(".!?").strip()


_VERB = r"(?:\w+,?\s+)?(?:prepni|prepnout|switch)(?:\s+se)?(?:\s+(?:zpet|zpatky|back))?\s+(?:na|to)\s+"
_TO_OLLAMA = re.compile(_VERB + r"(?:(?:lokalni|local)\s+(?:mozek|brain|model)|ollam[auy]?)")
_TO_CLAUDE = re.compile(_VERB + r"(?:claude|predplatne|subscription|cloud)")
_TO_MODEL = re.compile(_VERB + r"model\s+(\S+)")


def command(text):
    """Přepínací věta → `(mozek, model | None)`, jinak `None`. Celá zpráva musí být příkaz (zmínka v delší větě ne)."""
    plain = _plain(text)
    if _TO_OLLAMA.fullmatch(plain):
        return OLLAMA, None
    if _TO_CLAUDE.fullmatch(plain):
        return CLAUDE, None
    found = _TO_MODEL.fullmatch(plain)
    return (OLLAMA, found.group(1)) if found else None


def ollama_turn(model, stdin_text, transport=http):
    """Jeden tah lokálního modelu; nedostupná Ollama nebo vadná odpověď je `RuntimeError` s českou zprávou.

    shortcut: Ollama nemá relaci, tah vidí jen persona + podklady této zprávy; upgrade: přidat posledních N zpráv
    ze `store.messages`, až bude lokální mozek potřebovat paměť rozhovoru.
    """
    body = {"model": model, "stream": False, "format": "json", "think": False,
            "messages": [{"role": "system", "content": session.PERSONA.read_text(encoding="utf-8")},
                         {"role": "user", "content": stdin_text}]}
    try:
        answer = transport("POST", "/api/chat", body, TIMEOUT)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Lokální mozek ({model}) teď neodpovídá: {error}") from error
    content = (answer.get("message") or {}).get("content") if isinstance(answer, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"Lokální mozek ({model}) vrátil prázdnou odpověď.")
    return session.parse_reply(content)


def turn(folder, stdin_text, *, runner=run_process, find=claude_command.find_claude, transport=http):
    """Tah zvoleným mozkem; vrací `(reply, actions)`, chyba je `RuntimeError` jako u `session.turn`."""
    chosen = store.settings(folder)
    if chosen["brain"] == OLLAMA:
        return ollama_turn(chosen["ollamaModel"], stdin_text, transport)
    return session.turn(folder, stdin_text, runner=runner, find=find)
