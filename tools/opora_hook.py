"""Native Claude hook client; stdout is always one valid JSON object and nothing else."""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

MAX_STDIN = 128_000
TIMEOUT_SECONDS = 3
LANGUAGES = {"typescript", "python"}
OPERATIONS = {"definition", "references", "hover", "documentSymbols"}
MEMORY_MAX_TOKENS = 600


def closed(reason):
    return {"continue": False, "stopReason": reason[:240]}


def load_client(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"endpoint", "bindingId", "sessionId", "project", "workspace", "nodeId", "token"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Neplatný privátní Hook client.")
    parsed = urllib.parse.urlparse(data["endpoint"])
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path != "/api/agent-hooks":
        raise ValueError("Hook client nepovoluje vzdálený endpoint.")
    if not all(isinstance(data[key], str) and data[key] for key in data):
        raise ValueError("Neplatný privátní Hook client.")
    return data


def request(client, path, payload):
    parsed = urllib.parse.urlparse(client["endpoint"])
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    req = urllib.request.Request(f"{origin}{path}", raw, method="POST", headers={
        "Content-Type": "application/json", "Origin": origin, "Authorization": "Bearer " + client["token"],
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_STDIN + 1)
    if len(body) > MAX_STDIN:
        raise ValueError("Hook odpověď překročila limit.")
    result = json.loads(body.decode("utf-8"))
    if not isinstance(result, dict):
        raise TypeError("Hook odpověď není JSON objekt.")
    return result


def relative(path):
    if not isinstance(path, str) or not path or len(path) > 2048 or "\\" in path:
        raise ValueError("Neplatná relativní cesta.")
    if any(not part or part in {".", ".."} for part in path.split("/")):
        raise ValueError("Neplatná relativní cesta.")
    return path


def hook(client, only_session=None):
    raw = sys.stdin.buffer.read(MAX_STDIN + 1)
    if len(raw) > MAX_STDIN:
        raise ValueError("Hook stdin překročil limit.")
    event = json.loads(raw.decode("utf-8"))
    if not isinstance(event, dict):
        raise TypeError("Hook stdin není JSON objekt.")
    if only_session is not None and event.get("session_id") != only_session:
        return {}
    return request(client, "/api/agent-hooks/event", {"bindingId": client["bindingId"], "event": event})


def ack(client, revision):
    if revision < 0:
        raise ValueError("Neplatná ACK revize.")
    return request(client, "/api/agent-hooks/ack", {"bindingId": client["bindingId"], "sessionId": client["sessionId"], "taskRevision": revision})


def code_query(client, language, operation, path, line, character):
    if language not in LANGUAGES or operation not in OPERATIONS or line < 0 or character < 0:
        raise ValueError("Neplatný code-query požadavek.")
    return request(client, "/api/code-intelligence/query", {"project": client["project"], "workspace": client["workspace"],
        "language": language, "operation": operation, "path": relative(path), "line": line, "character": character})


def semantic(client, path, query):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Neplatný semantic dotaz.")
    return request(client, "/api/semantic-search/query", {"project": client["project"], "workspace": client["workspace"],
        "path": relative(path), "query": query, "limit": 5})


def memory(client, query):
    """Paměť role u této karty. Roli klient neposílá — rozhoduje o ní vždy server podle uzlu."""
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Neplatný dotaz do paměti role.")
    return request(client, "/api/memory/recall", {"role": None, "project": client["project"],
        "workspace": client["workspace"], "nodeId": client["nodeId"], "query": query,
        "maxTokens": MEMORY_MAX_TOKENS})


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--client", required=True)
    parser.add_argument("--only-session")
    parser.add_argument("action", nargs="?")
    parser.add_argument("args", nargs="*")
    args = parser.parse_args(argv)
    try:
        client = load_client(args.client)
        if args.only_session is not None:
            uuid.UUID(args.only_session)
            if args.action is not None or args.args:
                raise ValueError("--only-session je pouze pro hook event režim.")
        if args.action is None and not args.args:
            result = hook(client, args.only_session)
        elif args.action == "ack" and len(args.args) == 1:
            result = ack(client, int(args.args[0]))
        elif args.action == "code-query" and len(args.args) == 5:
            result = code_query(client, args.args[0], args.args[1], args.args[2], int(args.args[3]), int(args.args[4]))
        elif args.action == "semantic" and len(args.args) == 2:
            result = semantic(client, args.args[0], args.args[1])
        elif args.action == "memory" and len(args.args) == 1:
            result = memory(client, args.args[0])
        else:
            raise ValueError("Neplatná Hook akce.")
    except (OSError, TypeError, ValueError, UnicodeError, json.JSONDecodeError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        result = closed("Hook client nebo řídicí API není dostupné; bezpečně zastaveno.")
    sys.stdout.write(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
