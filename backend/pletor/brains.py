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


_ACTION = re.compile(r"\b(?:prepn\w*|zapn\w*|pouzij\w*|pust\w*|jdi|vrat\w*|switch|use)\b")
_LOCAL = re.compile(r"\b(?:lokaln\w*|mistn\w*|local|ollam\w*|offline|zdarma)\b")
_CLOUD = re.compile(r"\b(?:claud\w*|klaud\w*|klod\w*|kloud\w*|cloud|predplatn\w*|subscription|sonn?et\w*)\b")
_MODEL = re.compile(r"\bmodel\s+(\S+)")
SHORT = 8  # slov: příkaz je krátká věta, zmínka v dlouhé odpovědi se za příkaz nebere


def command(text):
    """Přepínací věta → `(mozek, model | None)`, jinak `None`. Řeč z mikrofonu přichází s interpunkcí, bez diakritiky a
    s přeslechy („Klaud“), proto se hledá sloveso přepnutí + cíl v krátké větě, ne přesné znění."""
    plain = _plain(text)
    if len(plain.split()) > SHORT or not _ACTION.search(plain):
        return None
    if _LOCAL.search(plain):
        return OLLAMA, None
    if _CLOUD.search(plain):
        return CLAUDE, None
    found = _MODEL.search(plain)
    return (OLLAMA, found.group(1)) if found else None


HISTORY = 8  # posledních zpráv rozhovoru, které lokální model vidí (Claude má vlastní relaci `--resume`)
OPTIONS = {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1, "num_ctx": 8192}
KEEP_ALIVE = "30m"  # model zůstane v paměti mezi zprávami, teplý tah místo načítání
# Malý model se zakotví na podkladech (opakoval větu z deníku srdce na každou zprávu), proto má navíc tato pravidla.
LOCAL = """PRAVIDLA LOKÁLNÍHO MOZKU (mají přednost před tvarem odpovědi výše):
- Odpovídej na to, na co se člověk ptá v poslední zprávě. Podklady použij jen, když se dotazu týkají.
- Na pozdrav a small talk odpověz přirozeně a krátce, česky, bez výčtu stavu projektu.
- Neopakuj své předchozí odpovědi; každá zpráva člověka dostane vlastní odpověď.
- Běžně odpověz prostým textem (1–4 věty), bez JSON a bez akcí.
- Akce jsou vzácné. Objekt JSON {"reply": ..., "actions": [...]} napiš jen na výslovný příkaz člověka („zadej
  srdci…“, „postav…“, „spusť…“, „zapiš rozhodnutí…“). Na otázku, pozdrav ani small talk akci nikdy nedělej
  a srdci nikdy neposílej otázku."""
RETRY = "Předchozí odpověď neodpovídala dotazu, odpověz přímo na: {text}"


def _norm(text):
    return " ".join(str(text or "").lower().split()).rstrip(".!?")


def ollama_messages(context, text, history=()):
    """`messages` pro `/api/chat`: persona + pravidla, podklady jako fakta, historie (human→user, pletor→assistant),
    nakonec jen zpráva člověka, aby model odpovídal na ni, ne na podklady."""
    persona = session.PERSONA.read_text(encoding="utf-8")
    roles = {"human": "user", "pletor": "assistant"}
    past = [{"role": roles[item["role"]], "content": item["text"]} for item in history
            if item.get("role") in roles and isinstance(item.get("text"), str)][-HISTORY:]
    return [{"role": "system", "content": f"{persona}\n{context}\n\n{LOCAL}"}, *past, {"role": "user", "content": text}]


def _chat(model, messages, transport):
    body = {"model": model, "stream": False, "think": False, "keep_alive": KEEP_ALIVE, "options": OPTIONS,
            "messages": messages}
    try:
        answer = transport("POST", "/api/chat", body, TIMEOUT)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Lokální mozek ({model}) teď neodpovídá: {error}") from error
    content = (answer.get("message") or {}).get("content") if isinstance(answer, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"Lokální mozek ({model}) vrátil prázdnou odpověď.")
    return session.parse_reply(content)


def ollama_turn(model, context, text, history=(), transport=http):
    """Jeden tah lokálního modelu nad podklady a historií; nedostupná Ollama nebo vadná odpověď je `RuntimeError`.
    Zopakuje-li model doslova některou svou nedávnou odpověď na jinou zprávu, tah se jednou zopakuje s výzvou
    k přímé odpovědi (živě: qwen3:8b vrátil na „Proč odpovídáš pořád stejně?“ odpověď na „Jak se máš?“)."""
    messages = ollama_messages(context, text, history)
    reply, actions = _chat(model, messages, transport)
    recent = history[-HISTORY:]
    said = {_norm(item.get("text")) for item in recent if item.get("role") == "pletor"}
    asked = [_norm(item.get("text")) for item in recent if item.get("role") == "human"][-1:]
    if _norm(reply) in said and [_norm(text)] != asked:
        messages[-1] = {"role": "user", "content": f"{text}\n\n({RETRY.format(text=text)})"}
        reply, actions = _chat(model, messages, transport)
    return reply, actions


def turn(folder, context, text, history=(), *, runner=run_process, find=claude_command.find_claude, transport=http):
    """Tah zvoleným mozkem; vrací `(reply, actions)`, chyba je `RuntimeError` jako u `session.turn`.
    Claude dostane podklady a zprávu v jednom vstupu (historii drží jeho relace), Ollama role a historii."""
    chosen = store.settings(folder)
    if chosen["brain"] == OLLAMA:
        return ollama_turn(chosen["ollamaModel"], context, text, history, transport)
    return session.turn(folder, f"{context}\n\nZPRÁVA ČLOVĚKA:\n{text}", runner=runner, find=find)
