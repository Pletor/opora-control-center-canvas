"""Jeden tah Pletora = jeden proces `claude -p` pod předplatným (žádné API), jedna relace na celou aplikaci.

Relace a její rotace jsou stejné jako u srdce (`brain_opora/heart/session.py`): `<data>/pletor/session.json`,
`--resume` do `ROTATE_AT` tokenů kontextu, nová relace i po změně `persona.md`. Pletor nemá žádné nástroje
(`--tools ""`), žádné MCP ani háčky a z prostředí se odstraní klíče API. Proces spouští stejný runner jako dávku
srdce (`process.run_process`); testy vstřikují falešný.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from backend.brain_opora.heart import batch, command, session
from backend.brain_opora.heart.process import run_process

PERSONA = Path(__file__).resolve().parent / "persona.md"
MODEL = "sonnet"  # mluví s člověkem: kvalita věty před cenou Haiku; bez poradce
TIMEOUT = 180
MAX_TURNS = 2  # bez nástrojů stačí jeden tah; druhý je rezerva


def build_command(claude, session_id, resume):
    return [claude, "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
            "--model", MODEL, *(["--resume", session_id] if resume else ["--session-id", session_id]),
            "--setting-sources", "project", "--strict-mcp-config", "--tools", "", "--permission-mode", "dontAsk",
            "--system-prompt-file", str(PERSONA), "--disable-slash-commands", "--max-turns", str(MAX_TURNS)]


def child_env(environ=None):
    env = dict(os.environ if environ is None else environ)
    for key in command.STRIPPED:
        env.pop(key, None)
    return env | {"PYTHONIOENCODING": "utf-8"}


def parse_reply(text):
    """`(reply, actions)` z textu modelu: objekt JSON (i obalený blokem kódu); jinak celý text a žádné akce."""
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start:end + 1])
        except ValueError:
            value = None
        if isinstance(value, dict) and isinstance(value.get("reply"), str):
            return value["reply"].strip(), value.get("actions")
    return text, []


_KEY = re.compile(r'"reply"\s*:\s*"')


class ReplyStream:
    """Z narůstajícího textu modelu průběžně vytahuje hodnotu pole `"reply"` objektu JSON (i v bloku kódu).
    `feed(kus)` vrátí nově dekódovaný text; escape rozdělený mezi kousky počká na další kus. Prostý text bez klíče
    nevrátí nic (doplní ho `Pletor.message` po tahu)."""

    def __init__(self):
        self.raw, self.state = "", "key"  # key → text → done

    def feed(self, piece):
        self.raw += piece
        if self.state == "key":
            found = _KEY.search(self.raw)
            if not found:
                return ""
            self.raw, self.state = self.raw[found.end():], "text"
        if self.state != "text":
            return ""
        out, raw, i = [], self.raw, 0
        while i < len(raw):
            if raw[i] == '"':
                self.state, i = "done", len(raw)
                break
            if raw[i] != "\\":
                out.append(raw[i])
                i += 1
                continue
            size = 2
            if raw[i + 1:i + 2] == "u":
                high = raw[i + 2:i + 6].lower()
                size = 12 if len(high) == 4 and "d800" <= high < "dc00" else 6  # pár náhradníků = jeden znak
            if i + size > len(raw):
                break
            try:
                out.append(json.loads(f'"{raw[i:i + size]}"'))
            except ValueError:
                out.append(raw[i + 1])
            i += size
        self.raw = raw[i:]
        return "".join(out)


def stream_lines(on_delta):
    """`on_line` pro `run_process`: z řádků `stream_event` / `text_delta` posílá do `on_delta` kousky pole `reply`."""
    stream = ReplyStream()

    def line(text):
        try:
            event = json.loads(text)
        except ValueError:
            return
        if not isinstance(event, dict) or event.get("type") != "stream_event":
            return
        delta = (event.get("event") or {}).get("delta") or {}
        if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
            piece = stream.feed(delta["text"])
            if piece:
                on_delta(piece)

    return line


def turn(folder, stdin_text, *, runner=run_process, find=command.find_claude, on_delta=None):
    """Spustí tah a vrátí `(reply, actions)`; chyba procesu je `RuntimeError` s českou zprávou.
    `on_delta(text)` dostává za běhu kousky odpovědi (`stream_lines`)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    claude = find()
    if not claude:
        raise RuntimeError("Claude Code (`claude`) na tomto počítači chybí.")
    digest = hashlib.sha256(PERSONA.read_bytes()).hexdigest()
    session_id, resume = session.choose(folder, prompt_digest=digest)
    outcome = runner(build_command(claude, session_id, resume), cwd=str(folder), env=child_env(),
                     stdin_text=stdin_text, timeout=TIMEOUT,
                     on_line=stream_lines(on_delta) if on_delta else None)
    result = batch.parse(outcome.stdout)
    if outcome.timed_out:
        raise RuntimeError(f"Pletor neodpověděl do {TIMEOUT} s.")
    if result and isinstance(result.get("session_id"), str):
        ok = not result.get("is_error")
        # chybný tah (třeba ztracená relace) vynutí rotaci, aby se další tah nezasekl na --resume
        session.record(folder, result["session_id"],
                       session.context_tokens(outcome.stdout, result) if ok else session.ROTATE_AT + 1, digest)
    if result is None or result.get("is_error"):
        detail = "limit předplatného" if batch.rate_limited(result, outcome.stderr) else "chyba procesu"
        raise RuntimeError(f"Pletor teď neodpovídá ({detail}).")
    return parse_reply(result.get("result"))
