"""Historie session z přepisu Claude Code `~/.claude/projects/*/<claudeSessionId>.jsonl`.

Vrací jen text uživatele a asistenta: kontext `<opora_context>` se z uživatelských zpráv
odstraní, výsledky nástrojů, meta zprávy a příkazy (`<command-…>`) se přeskočí.
Čte se nejvýš posledních 2 MB a vrací se nejvýš 500 zpráv.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024
MAX_MESSAGES = 500
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
CONTEXT_RE = re.compile(r"<opora_context>.*?</opora_context>\s*", re.DOTALL)
COMMAND_PREFIXES = ("<command-", "<local-command-")


def find_transcript(claude_session_id, home=None):
    if not isinstance(claude_session_id, str) or not UUID_RE.match(claude_session_id):
        return None
    projects = Path(home or Path.home()) / ".claude" / "projects"
    if not projects.is_dir():
        return None
    matches = [path for path in projects.glob(f"*/{claude_session_id}.jsonl") if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _read_tail(path, limit=MAX_BYTES):
    with open(path, "rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - limit))
        data = handle.read(limit)
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[1:] if size > limit else lines


def _texts(content):
    if isinstance(content, str):
        return content, False
    if not isinstance(content, list):
        return "", False
    parts, tool_result = [], False
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_result":
            tool_result = True
        elif block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts), tool_result


def parse_lines(lines, max_messages=MAX_MESSAGES):
    messages = []
    last_assistant_id = None
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict) or item.get("isMeta") or item.get("type") not in ("user", "assistant"):
            continue
        message = item.get("message") if isinstance(item.get("message"), dict) else {}
        text, tool_result = _texts(message.get("content"))
        if item["type"] == "user":
            last_assistant_id = None
            if tool_result:
                continue
            text = CONTEXT_RE.sub("", text).strip()
            if not text or text.lstrip().startswith(COMMAND_PREFIXES):
                continue
            messages.append({"role": "user", "text": text})
            continue
        text = text.strip()
        if not text:
            continue
        message_id = message.get("id")
        # Claude Code zapisuje jednu odpověď po blocích; bloky téže zprávy se spojí.
        if message_id and message_id == last_assistant_id and messages and messages[-1]["role"] == "assistant":
            messages[-1]["text"] += "\n\n" + text
        else:
            messages.append({"role": "assistant", "text": text})
        last_assistant_id = message_id
    return messages[-max_messages:]


def read_transcript(claude_session_id, home=None):
    path = find_transcript(claude_session_id, home)
    if path is None:
        return []
    try:
        return parse_lines(_read_tail(path))
    except OSError:
        return []
