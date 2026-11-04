"""Jeden tah Pletora = jeden proces `claude -p` pod předplatným (žádné API), jedna relace na celou aplikaci.

Relace a její rotace jsou stejné jako u srdce (`brain_opora/heart/session.py`): `<data>/pletor/session.json`,
`--resume` do `ROTATE_AT` tokenů kontextu, nová relace i po změně `persona.md`. Pletor nemá žádné nástroje
(`--tools ""`), žádné MCP ani háčky a z prostředí se odstraní klíče API. Proces spouští stejný runner jako dávku
srdce (`process.run_process`); testy vstřikují falešný.
"""
import hashlib
import json
import os
from pathlib import Path

from backend.brain_opora.heart import batch, command, session
from backend.brain_opora.heart.process import run_process

PERSONA = Path(__file__).resolve().parent / "persona.md"
MODEL = "sonnet"  # mluví s člověkem: kvalita věty před cenou Haiku; bez poradce
TIMEOUT = 180
MAX_TURNS = 2  # bez nástrojů stačí jeden tah; druhý je rezerva


def build_command(claude, session_id, resume):
    return [claude, "-p", "--output-format", "stream-json", "--verbose", "--model", MODEL,
            *(["--resume", session_id] if resume else ["--session-id", session_id]),
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


def turn(folder, stdin_text, *, runner=run_process, find=command.find_claude):
    """Spustí tah a vrátí `(reply, actions)`; chyba procesu je `RuntimeError` s českou zprávou."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    claude = find()
    if not claude:
        raise RuntimeError("Claude Code (`claude`) na tomto počítači chybí.")
    digest = hashlib.sha256(PERSONA.read_bytes()).hexdigest()
    session_id, resume = session.choose(folder, prompt_digest=digest)
    outcome = runner(build_command(claude, session_id, resume), cwd=str(folder), env=child_env(),
                     stdin_text=stdin_text, timeout=TIMEOUT)
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
