"""Read-only adaptéry zdrojů pro sledování sessions navázaných na uzel.

Hermes: pouze GET na nakonfigurované loopback API (Bearer klíč jen server-side).
Claude: pouze fixní soubory lane (state.json, events.jsonl) pod jedním kořenem.

Žádný adaptér nespouští model ani proces. Ven posílají jen bezpečná metadata:
názvy nástrojů z allowlistu, obecné české popisy, časy a čítače. Nikdy obsah
zpráv, prompty, reasoning, vstupy/výstupy nástrojů ani příkazové řádky.
"""

import ctypes
import json
import os
import re
import stat
import sys
import urllib.error
import urllib.request
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

DEFAULT_HERMES_URL = "http://127.0.0.1:8642"
MAX_HTTP_BYTES = 8_000_000
MAX_STATE_BYTES = 64_000
MAX_EVENTS_TAIL_BYTES = 4_000_000
MAX_EVENTS_HEAD_BYTES = 256_000
MAX_LINE_BYTES = 1_000_000
MAX_EVENTS = 50
HERMES_PAGE = 50
RECENT_ACTIVITY_SECONDS = 120
PID_TIME_TOLERANCE_SECONDS = 2.0

SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
LANE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_REPARSE_POINT = 0x400

# Jen tyto názvy nástrojů se smí dostat do UI; ostatní (včetně MCP) dostanou obecný popis.
SAFE_TOOL_NAMES = frozenset({
    # Claude Code
    "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "BashOutput", "KillShell",
    "Glob", "Grep", "LS", "WebFetch", "WebSearch", "Task", "Agent", "TodoWrite", "Skill",
    # Hermes
    "terminal", "process", "read_file", "write_file", "patch", "search_files", "web_search",
    "web_extract", "browser_navigate", "browser_snapshot", "browser_click", "browser_type",
    "execute_code", "delegate_task", "todo", "memory", "session_search", "clarify",
    "vision_analyze", "send_message", "skill_view", "skills_list", "cronjob",
})


class SourceError(Exception):
    """Chyba zdroje s bezpečnou českou zprávou určenou pro UI."""


def valid_session_id(value):
    return isinstance(value, str) and bool(SESSION_ID_RE.fullmatch(value)) and ".." not in value


def valid_lane(value):
    return isinstance(value, str) and bool(LANE_RE.fullmatch(value))


def parse_time(value):
    """Epoch sekundy nebo ISO s časovou zónou -> aware UTC datetime; jinak None.

    ISO bez zóny neumíme spolehlivě přiřadit, proto ho nepovažujeme za důvěryhodný čas.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if not 946684800 <= value <= 4102444800:
            return None
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str) and 10 <= len(value) <= 64:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    return None


def iso(moment):
    return moment.isoformat() if moment is not None else None


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return value


def tool_label(name):
    return name if isinstance(name, str) and name in SAFE_TOOL_NAMES else None


def tool_call_summary(name):
    label = tool_label(name)
    return f"Volání nástroje: {label}" if label else "Volání nástroje (neuvedený nástroj)"


def tool_result_summary(name, is_error=False):
    label = tool_label(name)
    if is_error:
        return f"Nástroj vrátil chybu: {label}" if label else "Nástroj vrátil chybu"
    return f"Nástroj dokončen: {label}" if label else "Nástroj dokončen"


def activity_status(last_at, now, source_name):
    """Stav jen z uložených událostí; nikdy nevydává `running`."""
    if last_at is None:
        return "unknown", f"{source_name}: nové události nemají důvěryhodný čas."
    age = (now - last_at).total_seconds()
    if age <= RECENT_ACTIVITY_SECONDS:
        return "recent_activity", (
            f"{source_name}: nové uložené události před {max(0, int(age))} s; "
            "neprokazuje to právě běžící proces."
        )
    return "idle", f"{source_name}: poslední uložená událost je starší než {RECENT_ACTIVITY_SECONDS} s."


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HermesSessionSource:
    """GET-only klient Hermes API na loopbacku.

    Konfigurace pouze z argumentů (router je plní z OPORA_HERMES_API_URL a
    OPORA_HERMES_API_KEY). Bez proxy, bez přesměrování, s timeoutem a stropem
    velikosti odpovědi. Klíč nikdy neopouští hlavičku požadavku.
    """

    source = "hermes"

    def __init__(self, base_url=None, api_key=None, *, fetch=None, timeout=3.0):
        self.config_error = None
        try:
            self.base_url = self._validated_base_url(base_url or DEFAULT_HERMES_URL)
        except ValueError:
            self.base_url = None
            self.config_error = "Adresa Hermes API není platná loopback HTTP adresa."
        self._api_key = api_key if isinstance(api_key, str) and api_key.strip() else None
        self._timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler)
        self._fetch = fetch or self._http_fetch

    @staticmethod
    def _validated_base_url(base_url):
        parts = urlsplit(base_url)
        if parts.scheme != "http" or (parts.hostname or "").lower() not in _LOOPBACK_HOSTS:
            raise ValueError("hermes_url_must_be_loopback_http")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("hermes_url_invalid")
        return base_url.rstrip("/")

    def build_request(self, path):
        request = urllib.request.Request(self.base_url + path, method="GET")
        request.add_header("Accept", "application/json")
        if self._api_key:
            request.add_header("Authorization", "Bearer " + self._api_key)
        return request

    def _http_fetch(self, path):
        try:
            with self._opener.open(self.build_request(path), timeout=self._timeout) as resp:
                raw = resp.read(MAX_HTTP_BYTES + 1)
                if len(raw) > MAX_HTTP_BYTES:
                    return "too_large", None
                return resp.status, json.loads(raw)
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None, None

    def _get(self, path):
        if self.config_error:
            raise SourceError(self.config_error)
        if self._fetch == self._http_fetch and not self._api_key:
            raise SourceError("Hermes API nemá nakonfigurovaný server-side klíč.")
        status, body = self._fetch(path)
        if status in (401, 403):
            raise SourceError("Hermes API odmítlo ověření.")
        if status == 404:
            raise SourceError("Session v Hermes neexistuje.")
        if status == "too_large":
            raise SourceError("Odpověď Hermes API překročila povolenou velikost.")
        if status != 200 or not isinstance(body, dict):
            raise SourceError("Hermes API není dostupné.")
        return body

    def session_meta(self, session_id):
        if not valid_session_id(session_id):
            raise SourceError("Neplatný identifikátor session.")
        body = self._get("/api/sessions/" + quote(session_id, safe=""))
        session = body.get("session")
        if body.get("object") != "hermes.session" or not isinstance(session, dict):
            raise SourceError("Hermes API vrátilo neočekávaný tvar session.")
        if session.get("id") != session_id:
            raise SourceError("Hermes API vrátilo jinou session, než byla vyžádána.")
        count = session.get("message_count")
        model = session.get("model")
        parent = session.get("parent_session_id")
        return {
            "sessionId": session_id,
            "model": model[:120] if isinstance(model, str) and model else None,
            "startedAt": parse_time(session.get("started_at")),
            "endedAt": parse_time(session.get("ended_at")),
            "messageCount": count if type(count) is int and count >= 0 else None,
            "parentSessionId": parent if valid_session_id(parent) else None,
            # Metriky jsou za CELOU session, ne jen za práci na uzlu.
            "metrics": {
                "inputTokens": _number(session.get("input_tokens")),
                "outputTokens": _number(session.get("output_tokens")),
                "costUsd": _number(session.get("actual_cost_usd")),
            },
        }

    def verify(self, session_id):
        meta = self.session_meta(session_id)
        if meta["messageCount"] is None:
            raise SourceError("Hermes neuvádí počet zpráv; výchozí bod vazby nelze bezpečně určit.")
        return {"model": meta["model"], "baselineCursor": meta["messageCount"]}

    def _message_events(self, session_id, position, message, baseline_at):
        if message.get("session_id") not in (None, session_id):
            return [], False
        at = parse_time(message.get("timestamp"))
        if at is not None and baseline_at is not None and at < baseline_at:
            return [], False
        role = message.get("role")
        base = f"hermes-{position}"
        events = []
        tool_calls = message.get("tool_calls")
        if role == "assistant" and isinstance(tool_calls, list) and tool_calls:
            for index, call in enumerate(tool_calls[:20]):
                function = call.get("function") if isinstance(call, dict) else None
                name = function.get("name") if isinstance(function, dict) else None
                events.append({"id": f"{base}-{index}", "at": iso(at), "kind": "tool_call",
                               "summary": tool_call_summary(name)})
        elif role == "tool":
            events.append({"id": base, "at": iso(at), "kind": "tool_result",
                           "summary": tool_result_summary(message.get("tool_name"))})
        elif role == "assistant":
            events.append({"id": base, "at": iso(at), "kind": "assistant_message", "summary": "Odpověď modelu"})
        elif role == "user":
            events.append({"id": base, "at": iso(at), "kind": "user_message", "summary": "Nová zpráva uživatele"})
        else:
            events.append({"id": base, "at": iso(at), "kind": "message", "summary": "Nová zpráva v session"})
        return events, True

    def observe(self, session_id, *, baseline_cursor, baseline_at, now):
        meta = self.session_meta(session_id)
        count = meta["messageCount"]
        result = {
            "sourceAvailable": True,
            "model": meta["model"],
            "metrics": meta["metrics"],
            "events": [],
            "lastActivityAt": None,
        }
        if count is None or count < baseline_cursor:
            return {**result, "status": "unknown",
                    "statusReason": "Hermes: počet zpráv nelze porovnat s bodem navázání."}
        events, last_at, untimed = [], None, False
        if count > baseline_cursor:
            offset = max(baseline_cursor, count - HERMES_PAGE)
            body = self._get(
                f"/api/sessions/{quote(session_id, safe='')}/messages?limit={HERMES_PAGE}&offset={offset}"
            )
            data = body.get("data")
            if body.get("object") != "list" or body.get("session_id") != session_id or not isinstance(data, list):
                raise SourceError("Hermes API vrátilo neočekávaný tvar zpráv.")
            for index, message in enumerate(data[:HERMES_PAGE]):
                position = offset + index
                if not isinstance(message, dict) or position < baseline_cursor:
                    continue
                produced, accepted = self._message_events(session_id, position, message, baseline_at)
                if not accepted:
                    continue
                at = parse_time(message.get("timestamp"))
                if at is None:
                    untimed = True
                elif last_at is None or at > last_at:
                    last_at = at
                events.extend(produced)
        result["events"] = events[-MAX_EVENTS:]
        result["lastActivityAt"] = iso(last_at)
        if meta["endedAt"] is not None:
            return {**result, "status": "completed",
                    "statusReason": "Hermes uvádí ukončenou session (ended_at); nepotvrzuje dokončení projektu."}
        if count == baseline_cursor:
            return {**result, "status": "idle",
                    "statusReason": "Hermes: od navázání žádné nové zprávy; otevřená session neznamená běh."}
        if last_at is None and untimed:
            return {**result, "status": "unknown", "statusReason": "Hermes: nové zprávy nemají důvěryhodný čas."}
        status, reason = activity_status(last_at, now, "Hermes")
        return {**result, "status": status, "statusReason": reason}


def _is_link_or_reparse(path):
    try:
        info = os.lstat(path)
    except OSError:
        return True
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _win_process_create_time(pid):
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return ticks / 10_000_000 - 11_644_473_600
    finally:
        kernel32.CloseHandle(handle)


def default_process_create_time(pid):
    """Čas vytvoření ŽIVÉHO procesu v epoch sekundách, jinak None (neověřeno)."""
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform == "win32":
        try:
            return _win_process_create_time(pid)
        except Exception:  # noqa: BLE001 - sonda nesmí shodit čtení; neověřeno = None.
            return None
    return None


def _iter_lines(handle, start, limit_bytes):
    """Čte řádky od `start`, nejvýš `limit_bytes`; příliš dlouhé řádky vrací jako None."""
    handle.seek(start)
    consumed = 0
    while consumed < limit_bytes:
        offset = start + consumed
        line = handle.readline(MAX_LINE_BYTES + 1)
        if not line:
            return
        consumed += len(line)
        if len(line) > MAX_LINE_BYTES and not line.endswith(b"\n"):
            while True:
                rest = handle.readline(MAX_LINE_BYTES)
                consumed += len(rest)
                if not rest or rest.endswith(b"\n"):
                    break
            yield offset, None
            continue
        yield offset, line


def _load_line(line):
    if line is None:
        return None
    text = line.strip()
    if not text:
        return None
    try:
        raw = json.loads(text)
    except ValueError:
        return None
    return raw if isinstance(raw, dict) else None


def _claude_events(raw, offset):
    kind = raw.get("type")
    at = iso(parse_time(raw.get("_observedAt")))
    base = f"claude-{offset}"
    if kind == "system":
        if raw.get("subtype") == "init":
            return [{"id": base, "at": at, "kind": "session_init", "summary": "Session zahájena; model potvrzen zdrojem"}]
        return []
    message = raw.get("message")
    blocks = message.get("content") if isinstance(message, dict) else None
    blocks = blocks if isinstance(blocks, list) else []
    if kind == "assistant":
        events, text = [], False
        for index, block in enumerate(blocks[:20]):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                events.append({"id": f"{base}-{index}", "at": at, "kind": "tool_call",
                               "summary": tool_call_summary(block.get("name"))})
            elif block.get("type") == "text":
                text = True
        if not events and text:
            events.append({"id": base, "at": at, "kind": "assistant_message", "summary": "Odpověď modelu"})
        return events
    if kind == "user":
        events = []
        for index, block in enumerate(blocks[:20]):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                failed = block.get("is_error") is True
                events.append({"id": f"{base}-{index}", "at": at, "kind": "tool_error" if failed else "tool_result",
                               "summary": tool_result_summary(None, failed)})
        return events
    if kind == "result":
        failed = raw.get("is_error") is True
        return [{"id": base, "at": at, "kind": "result_error" if failed else "result",
                 "summary": "Modelový tah skončil chybou" if failed else "Modelový tah dokončen (neověřuje hotový produkt)"}]
    return []


class ClaudeLaneSource:
    """Čte jen `<root>/<lane>/state.json` a `events.jsonl` (Claude stream-json + `_observedAt`)."""

    source = "claude"

    def __init__(self, root, *, process_create_time=None):
        self.root = None
        if isinstance(root, str | os.PathLike) and str(root):
            try:
                candidate = Path(root).resolve(strict=True)
            except OSError:
                candidate = None
            if candidate is not None and candidate.is_dir():
                self.root = candidate
        self._process_create_time = process_create_time or default_process_create_time

    def _lane_dir(self, lane):
        if self.root is None:
            raise SourceError("Kořen Claude lanes není nakonfigurován nebo neexistuje.")
        if not valid_lane(lane):
            raise SourceError("Neplatný identifikátor lane.")
        entry = self.root / lane
        if _is_link_or_reparse(entry) or not entry.is_dir():
            raise SourceError("Lane neexistuje nebo není běžná složka.")
        if entry.resolve().parent != self.root:
            raise SourceError("Lane leží mimo nakonfigurovaný kořen.")
        return entry

    def _open(self, lane_dir, filename):
        path = lane_dir / filename
        if not path.exists():
            return None
        if _is_link_or_reparse(path) or not stat.S_ISREG(os.lstat(path).st_mode):
            raise SourceError("Soubor lane není běžný soubor.")
        return path.open("rb")

    def _state(self, lane_dir):
        handle = self._open(lane_dir, "state.json")
        if handle is None:
            return None
        with handle:
            raw = handle.read(MAX_STATE_BYTES + 1)
        if len(raw) > MAX_STATE_BYTES:
            raise SourceError("state.json překročil povolenou velikost.")
        try:
            data = json.loads(raw)
        except ValueError:
            raise SourceError("state.json není platný JSON.") from None
        if not isinstance(data, dict):
            raise SourceError("state.json má neočekávaný tvar.")
        return data

    def _scan(self, lane_dir, session_id):
        handle = self._open(lane_dir, "events.jsonl")
        out = {"initSessionIds": set(), "model": None, "events": deque(maxlen=MAX_EVENTS),
               "lastAt": None, "metrics": None, "foreign": 0, "matched": 0, "present": handle is not None}
        if handle is None:
            return out
        with handle:
            size = os.fstat(handle.fileno()).st_size
            for _offset, line in _iter_lines(handle, 0, min(size, MAX_EVENTS_HEAD_BYTES)):
                raw = _load_line(line)
                is_init = raw and raw.get("type") == "system" and raw.get("subtype") == "init"
                if is_init and valid_session_id(raw.get("session_id")):
                    out["initSessionIds"].add(raw["session_id"])
                    if raw["session_id"] == session_id and isinstance(raw.get("model"), str):
                        out["model"] = raw["model"][:120]
            start = max(0, size - MAX_EVENTS_TAIL_BYTES)
            lines = _iter_lines(handle, start, size - start)
            if start > 0:
                next(lines, None)  # první řádek po skoku může být useknutý
            for offset, line in lines:
                raw = _load_line(line)
                if raw is None:
                    continue
                if raw.get("session_id") != session_id:
                    out["foreign"] += 1
                    continue
                out["matched"] += 1
                produced = _claude_events(raw, offset)
                out["events"].extend(produced)
                at = parse_time(raw.get("_observedAt"))
                if produced and at is not None and (out["lastAt"] is None or at > out["lastAt"]):
                    out["lastAt"] = at
                if raw.get("type") == "system" and raw.get("subtype") == "init" and isinstance(raw.get("model"), str):
                    out["model"] = raw["model"][:120]
                if raw.get("type") == "result":
                    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
                    out["metrics"] = {
                        "inputTokens": _number(usage.get("input_tokens")),
                        "outputTokens": _number(usage.get("output_tokens")),
                        "costUsd": _number(raw.get("total_cost_usd")),
                    }
        return out

    def _identity(self, state, scan, session_id):
        state_id = state.get("sessionId") if state else None
        claims = {value for value in (state_id,) if value is not None} | scan["initSessionIds"]
        if claims - {session_id}:
            raise SourceError("Identita session v lane nesouhlasí s vazbou.")
        if session_id not in claims:
            raise SourceError("Lane nepotvrzuje tuto session (chybí state.sessionId i init událost).")

    def verify(self, lane, session_id):
        if not valid_session_id(session_id):
            raise SourceError("Neplatný identifikátor session.")
        lane_dir = self._lane_dir(lane)
        state = self._state(lane_dir)
        scan = self._scan(lane_dir, session_id)
        self._identity(state, scan, session_id)
        model = scan["model"] or (state.get("modelAlias") if state and isinstance(state.get("modelAlias"), str) else None)
        return {"model": model[:120] if model else None, "baselineCursor": 0}

    def _process_verified(self, state):
        pid, created = state.get("pid"), state.get("pidCreatedAt")
        if type(pid) is not int or isinstance(created, bool) or not isinstance(created, (int, float)):
            return False
        actual = self._process_create_time(pid)
        return actual is not None and abs(actual - created) <= PID_TIME_TOLERANCE_SECONDS

    def observe(self, lane, session_id, *, now, **_baseline):
        lane_dir = self._lane_dir(lane)
        state = self._state(lane_dir)
        scan = self._scan(lane_dir, session_id)
        self._identity(state, scan, session_id)
        model = scan["model"] or (state.get("modelAlias") if state and isinstance(state.get("modelAlias"), str) else None)
        result = {
            "sourceAvailable": True,
            "model": model[:120] if model else None,
            "metrics": scan["metrics"] or {"inputTokens": None, "outputTokens": None, "costUsd": None},
            "events": list(scan["events"]),
            "lastActivityAt": iso(scan["lastAt"]),
        }
        if state is None:
            return {**result, "status": "unknown", "statusReason": "Claude: state.json chybí; stav procesu nelze ověřit."}
        if state.get("running") is True:
            if self._process_verified(state):
                return {**result, "status": "running",
                        "statusReason": "Claude: ověřený běžící proces (PID a čas vytvoření souhlasí)."}
            return {**result, "status": "unknown",
                    "statusReason": "Claude: state.json uvádí běh, ale proces s tímto PID a časem vytvoření neběží."}
        finished = parse_time(state.get("finishedAt")) is not None
        if finished and state.get("success") is True and state.get("localTreeInactive") is True:
            return {**result, "status": "completed",
                    "statusReason": "Claude: modelový běh skončil úspěšně; neověřuje hotový produkt."}
        if finished and state.get("success") is False:
            return {**result, "status": "failed", "statusReason": "Claude: modelový běh skončil neúspěchem."}
        status, reason = activity_status(scan["lastAt"], now, "Claude")
        return {**result, "status": status, "statusReason": reason}
