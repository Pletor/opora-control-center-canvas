"""Kroky dávky srdce z proudu `claude -p --output-format stream-json` (docs/brain-heart-channel.md §1).

`Steps.feed(řádek)` je volaný průběžně (`process.run_process(on_line=…)`), takže `current.steps` ve stavu srdce roste
za běhu. Krok je `{t, kind, text}`: `t` ms od začátku dávky, `kind` thinking / text / tool / result, text zkrácený na
400 znaků a zbavený tajemství. Kroků je nejvýš 80; `reply` je závěrečný text srdce (nejvýš 2000 znaků).
"""
import json
import re

MAX_STEPS, STEP_CHARS, REPLY_CHARS = 80, 400, 2000
# `token: …`, `Authorization: Bearer …`, `api_key=…`, `--password x`; shortcut: heuristika, ne úplný skener tajemství
SECRET = re.compile(r"(?i)((?:token|authorization|bearer|api[-_ ]?key|secret|password|heslo)[\"']?\s*[:=\s]\s*)"
                    r"[\"']?(?:bearer\s+)?[^\s\"',;}]+")


def redact(text, secret=""):
    """Text bez tajemství: hodnoty za klíči `token`, `Authorization` … a doslovný token dávky."""
    text = SECRET.sub(r"\1***", str(text))
    return text.replace(secret, "***") if secret else text


def _result_text(content):
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content if isinstance(content, str) else ""


def _tool_text(part):
    detail = part.get("input")
    body = (detail.get("command") if isinstance(detail, dict) else None) or json.dumps(detail, ensure_ascii=False)
    return f"{part.get('name')}: {body}"


class Steps:
    def __init__(self, clock, started, secret="", steps=None):
        self.clock, self.started, self.secret = clock, started, secret
        self.steps = [] if steps is None else steps  # sdílený seznam: stejný objekt drží `current.steps`
        self.reply = None

    def _add(self, kind, text):
        if text and len(self.steps) < MAX_STEPS:
            text = redact(" ".join(str(text).split()), self.secret)[:STEP_CHARS]
            self.steps.append({"t": int((self.clock() - self.started) * 1000), "kind": kind, "text": text})

    def feed(self, line):
        try:
            event = json.loads(line)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            self.reply = redact(event["result"].strip(), self.secret)[:REPLY_CHARS]
            return
        message = event.get("message")
        for part in (message.get("content") if isinstance(message, dict) else None) or []:
            kind = part.get("type") if isinstance(part, dict) else None
            if kind == "thinking":
                self._add("thinking", part.get("thinking"))
            elif kind == "text" and event.get("type") == "assistant":
                self._add("text", part.get("text"))
            elif kind == "tool_use":
                self._add("tool", _tool_text(part))
            elif kind == "tool_result":
                self._add("result", _result_text(part.get("content")))
