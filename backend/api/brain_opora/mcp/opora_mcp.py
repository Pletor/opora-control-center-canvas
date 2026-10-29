"""MCP server OPORY nad bránou mozku (docs/brain-control-api.md §3, krok H1d), jen standardní knihovna.

    python <abs>/opora_mcp.py

JSON-RPC 2.0 přes stdio, jedna zpráva na řádek. Nástroje jsou druhy brány pro roli (`GET /api/gate/kinds`),
volání jde na `POST /api/gate/requests`. Server nemá vlastní logiku, jen překládá.
Prostředí: OPORA_BASE_URL (výchozí http://127.0.0.1:8740), OPORA_PROJECT, OPORA_WORKSPACE a buď token srdce
(OPORA_GATE_TOKEN / OPORA_HEART_TOKEN), nebo OPORA_WORKER_NAME (pracovník: relaci brány založí server při prvním
volání a token drží jen v paměti, nikam ho nezapisuje). Na stdout jde jen JSON-RPC, záznam jde na stderr.
"""
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

NAME, VERSION = "opora", "0.1.0"
DEFAULT_BASE = "http://127.0.0.1:8740"
HEADER = "X-Opora-Gate-Token"
TIMEOUT = 60
ASK_WAIT = 30
PREFIX = "opora_"
_OPENER = build_opener(ProxyHandler({}))  # loopback bez systémové proxy


class Refusal(Exception):
    """Neúspěch volání brány; `payload` jde agentovi jako výsledek s `isError`."""

    def __init__(self, payload):
        super().__init__(payload.get("error", ""))
        self.payload = payload


def log(*parts):
    print("[opora-mcp]", *parts, file=sys.stderr, flush=True)


def tool_name(kind):
    return PREFIX + kind.replace(".", "_")


def ask_schema(schema):
    """Schéma `ask` s volbou `wait`, kterou server bráně neposílá (čeká na odpověď ve schránce)."""
    wait = {"type": "boolean", "description": f"Počkat až {ASK_WAIT} s na odpověď ve schránce a vrátit ji."}
    return {**schema, "properties": {**schema.get("properties", {}), "wait": wait}}


def as_tool(kind):
    schema = kind.get("input") or {"type": "object"}
    return {"name": tool_name(kind["kind"]), "description": kind.get("description", ""),
            "inputSchema": ask_schema(schema) if kind["kind"] == "ask" else schema}


class Gate:
    """Spojení s bránou: role podle prostředí, líná relace pracovníka, cache druhů na proces."""

    def __init__(self, environ):
        self.base = (environ.get("OPORA_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.project, self.workspace = environ.get("OPORA_PROJECT", ""), environ.get("OPORA_WORKSPACE", "")
        self.token = environ.get("OPORA_GATE_TOKEN") or environ.get("OPORA_HEART_TOKEN") or None
        self.worker = None if self.token else environ.get("OPORA_WORKER_NAME") or None
        self.name = self.worker or "heart"
        self.kinds, self.cursor = None, 0

    def call(self, method, path, body=None, token=None):
        """Jedno HTTP volání; odmítnutí serveru i nedostupný server jsou `Refusal` s `code` a `hint`."""
        headers = {"Accept": "application/json", "Origin": self.base, "X-Opora-Actor": "agent; name=" + self.name}
        if token:
            headers[HEADER] = token
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json"
        try:
            request = Request(self.base + path, data=data, headers=headers, method=method)
            with _OPENER.open(request, timeout=TIMEOUT) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            try:
                detail = json.loads(error.read() or b"{}")
            except ValueError:
                detail = {}
            detail = detail if isinstance(detail, dict) else {}
            raise Refusal({"status": error.code, "code": detail.get("code") or f"http_{error.code}",
                           "error": detail.get("error") or f"HTTP {error.code}",
                           "hint": detail.get("hint") or "Pošlete vstup podle inputSchema nástroje."}) from None
        except (URLError, OSError) as error:
            raise Refusal({"status": None, "code": "server_unreachable", "error": f"OPORA {self.base} neodpovídá: "
                           f"{getattr(error, 'reason', error)}", "hint": "OPORA neběží: spusťte ji (uv run opora) "
                           "nebo nastavte OPORA_BASE_URL."}) from None

    def session_token(self):
        """Token srdce z prostředí, nebo relace pracovníka založená při prvním volání (jen v paměti)."""
        if self.token:
            return self.token
        if not self.worker:
            raise Refusal({"status": None, "code": "mcp_env_missing", "error": "Chybí OPORA_WORKER_NAME i token.",
                           "hint": "Nastavte OPORA_WORKER_NAME (pracovník) nebo OPORA_GATE_TOKEN (srdce)."})
        issued = self.call("POST", "/api/gate/sessions", {"project": self.project, "workspace": self.workspace,
                                                          "worker": {"name": self.worker}})
        self.token = issued["token"]
        log("relace brány", issued.get("sessionId"), "do", issued.get("expiresAt"))
        return self.token

    def tools(self):
        """Druhy pro roli (cache na proces); pracovník je čte bez tokenu, relace vznikne až prvním voláním."""
        if self.kinds is None:
            self.kinds = self.call("GET", "/api/gate/kinds", token=self.token)["kinds"]
        return [as_tool(kind) for kind in self.kinds]

    def request(self, kind, body):
        return self.call("POST", "/api/gate/requests", {"kind": kind, "body": body}, self.session_token())

    def await_answer(self, ticket_id, budget=ASK_WAIT, clock=time.monotonic):
        """Long-poll schránky (druh `inbox`), dokud nepřijde odpověď na lístek nebo nevyprší `budget` sekund."""
        deadline = clock() + budget
        while True:
            wait = min(ASK_WAIT, max(1, round(deadline - clock())))
            box = self.request("inbox", {"after": self.cursor, "wait": wait}).get("answer") or {}
            self.cursor = box.get("last", self.cursor)
            found = next((t for t in box.get("tickets", []) if t.get("ticketId") == ticket_id), None)
            if found or clock() >= deadline:
                return found

    def invoke(self, name, arguments):
        """`tools/call` → výsledek brány; `ask` s `wait` navíc počká na odpověď."""
        self.tools()  # naplní cache druhů, když agent volá bez tools/list
        kinds = {tool_name(kind["kind"]): kind["kind"] for kind in self.kinds}
        if name not in kinds:
            raise Refusal({"status": None, "code": "unknown_tool", "error": f"Neznámý nástroj {name}.",
                           "hint": "Povolené nástroje: " + ", ".join(kinds) + "."})
        body = dict(arguments or {})
        wait = kinds[name] == "ask" and bool(body.pop("wait", False))
        result = self.request(kinds[name], body)
        if not wait:
            return result
        answered = self.await_answer(result["ticketId"])
        return {**result, "answer": answered.get("answer") if answered else None, "answered": bool(answered)} | (
            {} if answered else {"hint": "Odpověď zatím nepřišla; později ji vrátí opora_inbox."})


def text_result(payload, error=False):
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {"content": [{"type": "text", "text": text}]} | ({"isError": True} if error else {})


def handle(gate, message):
    """Jedna zpráva JSON-RPC → odpověď, nebo None u notifikace."""
    method, params, mid = message.get("method"), message.get("params") or {}, message.get("id")
    if "id" not in message:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": NAME, "version": VERSION}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        try:
            result = {"tools": gate.tools()}
        except Refusal as refusal:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32000, "message": refusal.payload["error"],
                                                           "data": refusal.payload}}
    elif method == "tools/call":
        try:
            result = text_result(gate.invoke(params.get("name"), params.get("arguments")))
        except Refusal as refusal:
            result = text_result(refusal.payload, error=True)
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(gate, source, sink):
    """Smyčka stdio: řádek dovnitř, nejvýš řádek ven."""
    for line in source:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            reply = handle(gate, message) if isinstance(message, dict) else {
                "jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        except Exception as error:  # noqa: BLE001 – server nesmí spadnout na jedné zprávě
            log("chyba zprávy:", repr(error))
            reply = {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32603, "message": str(error)}}
        if reply is not None:
            sink.write(json.dumps(reply, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
            sink.flush()


def main():
    gate = Gate(os.environ)
    log("start", gate.base, "role", "heart" if gate.token else "worker", gate.project, gate.workspace)
    serve(gate, sys.stdin.buffer, sys.stdout.buffer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
