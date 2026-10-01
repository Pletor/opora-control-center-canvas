"""Read-only CLI client for Opora's local code-intelligence API (no model calls)."""

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _endpoint(value):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_HOSTS or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("endpoint musí být čistá lokální http URL (127.0.0.1/localhost).")
    return value.rstrip("/")


def _read_response(request, *, opener):
    with opener(request, timeout=15) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Odpověď API překročila limit 2 MiB.")
    return json.loads(data.decode("utf-8"))


def _request(endpoint, path, payload=None, *, opener):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        endpoint + path,
        data=body,
        method="GET" if body is None else "POST",
        headers={"Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {})},
    )
    return _read_response(request, opener=opener)


def build_parser():
    parser = argparse.ArgumentParser(description="Read-only local LSP-first Opora code-intelligence client.")
    parser.add_argument("--endpoint", type=_endpoint, default="http://127.0.0.1:8740")
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="Static provider status; does not start an LSP server.")
    status.add_argument("--project", required=True)
    status.add_argument("--workspace", required=True)
    query = commands.add_parser("query", help="One bounded LSP query (server is shut down after the response).")
    query.add_argument("--project", required=True)
    query.add_argument("--workspace", required=True)
    query.add_argument("--language", required=True, choices=("typescript", "python"))
    query.add_argument("--path", required=True, help="Workspace-relative file path.")
    query.add_argument("--operation", required=True, choices=("definition", "references", "hover", "documentSymbols"))
    query.add_argument("--line", required=True, type=int, help="0-based LSP line.")
    query.add_argument("--character", required=True, type=int, help="0-based UTF-16 LSP character.")
    return parser


def main(argv=None, *, opener=urlopen):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            response = _request(args.endpoint, "/api/code-intelligence/status?" + urlencode({"project": args.project, "workspace": args.workspace}), opener=opener)
        else:
            payload = {name: getattr(args, name) for name in ("project", "workspace", "language", "path", "operation", "line", "character")}
            response = _request(args.endpoint, "/api/code-intelligence/query", payload, opener=opener)
    except HTTPError as exc:
        detail = exc.read(8192).decode("utf-8", "replace")
        print(f"code-intelligence API HTTP {exc.code}: {detail}", file=sys.stderr)
        return 1
    except (URLError, OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"code-intelligence API unavailable: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
