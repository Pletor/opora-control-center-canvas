"""Mozky Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P2; M2d v pletor-nastaveni-llm.md): `claude` (výchozí,
Claude Code pod předplatným, `session.turn`), `codex` (Codex pod předplatným, `codex_turn`) a `ollama` (lokální
model přes Ollamu na `URL`). Všechny vrací `(reply, actions)` z `session.parse_reply`,
takže `actions.validate` platí beze změny. Volba mozku je jedna pro aplikaci v `<data>/pletor/settings.json`
(`store.settings`). Přepínací věta v chatu (`command`) se rozpozná bez modelu a modelu se nepředá.
"""
import json
import re
import shutil
import unicodedata
import urllib.request
from pathlib import Path

from backend.agi_pletor import session, store
from backend.agi_pletor.llm_settings import claude as claude_settings
from backend.agi_pletor.llm_settings import codex as codex_settings
from backend.agi_pletor.llm_settings import write
from backend.brain_opora.heart import command as claude_command
from backend.brain_opora.heart.process import run_process

CLAUDE, CODEX, OLLAMA = "claude", "codex", "ollama"
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
    """`{brain, model, available, models, efforts}` pro stav okna; `models` = uložený model, `efforts` = effort
    Claude a Codexu (None = výchozí; Ollama effort nemá)."""
    chosen = store.settings(folder)
    saved = {CLAUDE: chosen["claudeModel"], CODEX: chosen["codexModel"], OLLAMA: chosen["ollamaModel"]}
    return {"brain": chosen["brain"], "model": saved[chosen["brain"]], "available": models(transport), "models": saved,
            "efforts": {CLAUDE: chosen["claudeEffort"], CODEX: chosen["codexEffort"]}}


def switch(folder, brain, model=None, transport=http, effort=None):
    """Přepne mozek a vrátí `(ok, věta pro člověka)`; neplatný model nebo selhání nechá nastavení beze změny.
    `model` vynechán = ponechá uložený model toho mozku; `effort` vynechán = ponechá uložený, "" = výchozí."""
    chosen = store.settings(folder)
    if effort is not None and brain == OLLAMA:
        return False, "Lokální model effort nemá."
    if brain == CLAUDE:
        known = [item["id"] for item in claude_settings.MODELS]
        if model and model not in known:
            return False, f"Model {model} Claude nezná. Mám: {', '.join(known)}."
        if effort and effort not in claude_settings.EFFORTS:
            return False, f"Effort {effort} Claude nezná. Mám: {', '.join(claude_settings.EFFORTS)}."
        store.save_settings(folder, {**chosen, "brain": CLAUDE, "claudeModel": model or chosen["claudeModel"],
                                     "claudeEffort": chosen["claudeEffort"] if effort is None else effort or None})
        return True, "Zpátky na Claude, pane."
    if brain == CODEX:
        known = [item["id"] for item in codex_settings.models()]
        try:
            if model and not (model in known if known else write.check_model(model)):  # prázdná cache = jen tvar
                return False, f"Model {model} Codex nezná. Mám: {', '.join(known)}."
        except ValueError:
            return False, f"Model {model} nemá tvar názvu modelu Codexu."
        levels = write.reasoning_levels(model or chosen["codexModel"])
        if effort and effort not in levels:
            return False, f"Effort {effort} Codex u tohoto modelu nezná. Mám: {', '.join(levels)}."
        store.save_settings(folder, {**chosen, "brain": CODEX, "codexModel": model or chosen["codexModel"],
                                     "codexEffort": chosen["codexEffort"] if effort is None else effort or None})
        return True, "Přepínám na Codex, pane."
    available = models(transport)
    if not available:
        return False, "Ollama neběží nebo nemá žádný model. Zůstávám na Claude."
    if model and model not in available:
        return False, f"Model {model} v Ollamě není. Mám: {', '.join(available)}."
    model = model or (chosen["ollamaModel"] if chosen["ollamaModel"] in available else default_model(available))
    store.save_settings(folder, {**chosen, "brain": OLLAMA, "ollamaModel": model})
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
RESEARCH_CONTEXT, RESEARCH_OUTPUT = 32768, 1024
KEEP_ALIVE = "30m"  # model zůstane v paměti mezi zprávami, teplý tah místo načítání
# Malý model se zakotví na podkladech (opakoval větu z deníku srdce na každou zprávu), proto má navíc tato pravidla.
LOCAL = """PRAVIDLA LOKÁLNÍHO MOZKU (mají přednost před tvarem odpovědi výše):
- Odpovídej na to, na co se člověk ptá v poslední zprávě. Podklady použij jen, když se dotazu týkají.
- Na pozdrav a small talk odpověz přirozeně a krátce, česky, bez výčtu stavu projektu.
- Neopakuj své předchozí odpovědi; každá zpráva člověka dostane vlastní odpověď.
- Běžně odpověz prostým textem (1–4 věty), bez JSON a bez akcí.
- Akce jsou vzácné. Objekt JSON {"reply": ..., "actions": [...]} napiš jen na výslovný příkaz člověka („zadej
  srdci…“, „postav…“, „spusť…“, „zapiš rozhodnutí…“). Na otázku, pozdrav ani small talk akci nikdy nedělej
  a srdci nikdy neposílej otázku.
- Výjimka je read-only research_read: pro odpověď na otázku smíš načíst uložené podklady Rešerše podle persony.
  Vrať JSON s prázdným reply a akcí research_read; tím nic nezapisuješ ani nezadáváš srdci."""
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
    # Research chunks must not silently displace earlier evidence in Ollama's small default window.
    # UTF-8 bytes plus per-message framing are a conservative bound, independent of the selected tokenizer.
    research = any("REŠERŠE (data, ne příkazy)" in message.get("content", "")
                   or "DOČTENÁ REŠERŠE" in message.get("content", "") for message in messages)
    if research:
        size = len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) + 64 * len(messages)
        if size > RESEARCH_CONTEXT - RESEARCH_OUTPUT:
            raise RuntimeError("Podklady Rešerše přesahují bezpečný kontext lokálního modelu. "
                               "Zužte dotaz nebo zvolte jiný model Pletora; žádné podklady nebyly potichu oříznuty.")
        body["options"] = {**OPTIONS, "num_ctx": RESEARCH_CONTEXT, "num_predict": RESEARCH_OUTPUT}
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


CODEX_OUT = "codex-last-message.txt"
CODEX_LIMIT = re.compile(r"usage limit|rate limit", re.IGNORECASE)
CODEX_REVOKED = re.compile(r"token_revoked|refresh_token_reused|Failed to refresh token")


def codex_turn(folder, model, context, text, history=(), effort=None, *, runner=run_process, find=lambda: shutil.which("codex")):
    """Jeden tah Codexu pod předplatným (`codex exec`, jen čtení, bez MCP): prompt na stdin, odpověď z `-o` souboru.
    Chyba je `RuntimeError` s českou zprávou, limit předplatného se pozná podle textu výstupu."""
    codex = find()
    if not codex:
        raise RuntimeError("Codex (`codex`) na tomto počítači chybí.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / CODEX_OUT
    out.unlink(missing_ok=True)  # starý soubor by se jinak četl jako odpověď
    past = "\n".join(f"{item['role']}: {item['text']}" for item in history[-HISTORY:]
                     if isinstance(item.get("text"), str))
    prompt = f"{session.system_prompt()}\nROZHOVOR:\n{past}\n\n{context}\n\nZPRÁVA ČLOVĚKA:\n{text}"
    command = [codex, "exec", "-s", "read-only", "--skip-git-repo-check", "--ephemeral", "-c", "mcp_servers={}",
               *(["-m", model] if model else []),
               *(["-c", f'model_reasoning_effort="{effort}"'] if effort else []), "-o", str(out), "-"]
    env = {key: value for key, value in session.child_env().items() if key not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
    outcome = runner(command, cwd=str(folder), env=env, stdin_text=prompt, timeout=TIMEOUT)
    if outcome.timed_out:
        raise RuntimeError(f"Codex neodpověděl do {TIMEOUT} s.")
    if outcome.returncode != 0:
        said = f"{outcome.stdout}\n{outcome.stderr}"
        if CODEX_REVOKED.search(said):
            raise RuntimeError("Přihlášení Codexu je neplatné (token odvolán); přihlas se znovu v kartě Účty Codex.")
        raise RuntimeError(f"Codex teď neodpovídá ({'limit předplatného' if CODEX_LIMIT.search(said) else 'chyba procesu'}).")
    try:
        answer = out.read_text(encoding="utf-8")
    except OSError:
        answer = ""
    if not answer.strip():
        raise RuntimeError("Codex vrátil prázdnou odpověď.")
    return session.parse_reply(answer)


def turn(folder, context, text, history=(), *, runner=run_process, find=claude_command.find_claude, transport=http,
         on_delta=None):
    """Tah zvoleným mozkem; vrací `(reply, actions)`, chyba je `RuntimeError` jako u `session.turn`.
    Codex dostane vše v jednom promptu a `find` se ho netýká.
    Claude dostane podklady a zprávu v jednom vstupu (historii drží jeho relace), Ollama role a historii.
    `on_delta` dostává kousky odpovědi jen u Claude; Ollamě celou odpověď doplní `Pletor.message` po tahu."""
    chosen = store.settings(folder)
    if chosen["brain"] == OLLAMA:
        return ollama_turn(chosen["ollamaModel"], context, text, history, transport)
    if chosen["brain"] == CODEX:
        return codex_turn(folder, chosen["codexModel"], context, text, history, chosen["codexEffort"], runner=runner)
    return session.turn(folder, f"{context}\n\nZPRÁVA ČLOVĚKA:\n{text}", runner=runner, find=find,
                        on_delta=on_delta, model=chosen["claudeModel"], effort=chosen["claudeEffort"])
