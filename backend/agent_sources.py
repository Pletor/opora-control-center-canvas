"""Read-only adaptéry na skutečné zdroje běhů agentů.

Žádný z adaptérů nespouští ani nezastavuje proces; jen čte HTTP/soubory a
vrací poctivě neúplný stav, když je zdroj nedostupný nebo tvar dat neznámý.
"""

import ctypes
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, deque
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

MAX_FILE_BYTES = 5_000_000
MAX_HTTP_BYTES = 2_000_000
PREVIEW_EVENTS = 8
TEXT_LIMIT = 400
TOOL_INPUT_LIMIT = 200
ALLOWED_LANE_FILES = ("state.json", "events.jsonl", "result.json")
_LANE_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

# Princip a klíčová slova převzaty z OporaCC src/oporacc/security.py (jen ke čtení, bez
# importu cizího repozitáře za běhu; funkční reimplementace, ne byte-for-byte kopie).
# Výjimka z maskování tokenů platí pouze pro známé číselné metriky, ne pro řetězce
# ani ostatní klíče. CamelCase, prefixy i množné číslo mohou obsahovat credentials.
_TOKEN_COUNT_KEYS = {
    "inputtokens", "outputtokens", "totaltokens", "cachereadinputtokens",
    "cachecreationinputtokens", "prompttokens", "completiontokens",
}
_SECRET_KEY_EXACT = {"token", "access_token", "refresh_token", "bearer"}
_SECRET_KEY_SUBSTR = ("secret", "password", "authorization", "api_key", "apikey")
_SECRET_TEXT = re.compile(
    r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|(?:ghp_|github_pat_)[A-Za-z0-9_-]{16,}"
    r"|sk-[A-Za-z0-9_-]{16,}"
    r"|(?:token|api_key|secret|password)\s*[:=]\s*[^\s,;]{4,}",
    re.IGNORECASE,
)
_MASK = "[REDACTED]"


def _secret_key(key, value=None):
    lowered = str(key).lower()
    canonical = re.sub(r"[^a-z0-9]", "", lowered)
    if canonical in _TOKEN_COUNT_KEYS and type(value) in (int, float):
        return False
    return "token" in lowered or lowered in _SECRET_KEY_EXACT or any(part in lowered for part in _SECRET_KEY_SUBSTR)


def redact(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            out[key] = _MASK if _secret_key(key, item) else redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET_TEXT.sub(_MASK, value)
    return value


def clip(value, limit=TEXT_LIMIT):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def now_iso():
    return datetime.now(UTC).isoformat()


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Server-side loopback zdroj se nesmí nechat přesměrovat mimo svůj origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PlatnoSource:
    """Klient na existující status API vt-cc-platno (aktuálně 127.0.0.1:8738).

    Přestože jde o server-side konfigurovaný zdroj (ne uživatelský vstup), hranice
    zůstává loopback jen s HTTP/host validací, bez přihlašovacích údajů v URL, bez
    následování přesměrování a s omezenou velikostí odpovědi.
    """

    def __init__(self, base_url="http://127.0.0.1:8738", *, fetch=None, timeout=3.0):
        self.source_id = "oporacc-platno"
        self.base_url = self._validated_base_url(base_url)
        self._timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirectHandler)
        self._fetch = fetch or self._http_fetch

    @staticmethod
    def _validated_base_url(base_url):
        parts = urlsplit(base_url)
        if parts.scheme != "http":
            raise ValueError("platno_source_url_must_be_http")
        if (parts.hostname or "").lower() not in _LOOPBACK_HOSTS:
            raise ValueError("platno_source_url_must_be_loopback")
        if parts.username or parts.password:
            raise ValueError("platno_source_url_must_not_embed_credentials")
        return base_url.rstrip("/")

    def _http_fetch(self, path):
        try:
            request = urllib.request.Request(self.base_url + path, method="GET")
            with self._opener.open(request, timeout=self._timeout) as resp:
                raw = resp.read(MAX_HTTP_BYTES + 1)
                if len(raw) > MAX_HTTP_BYTES:
                    return None, None
                return resp.status, json.loads(raw)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None, None

    def health(self):
        status, body = self._fetch("/health")
        if status != 200 or not isinstance(body, dict):
            return {"available": False, "status": "unavailable", "error": "source_unreachable"}
        return {"available": True, "status": body.get("status", "unknown"), "bridge": redact(body.get("bridge")) if isinstance(body.get("bridge"), dict) else None}

    def status(self):
        status, body = self._fetch("/api/status")
        if status != 200 or not isinstance(body, dict):
            return {
                "available": False,
                "error": "source_unreachable",
                "bridgeOk": False,
                "bridgeError": "source_unreachable",
                "running": [],
                "waiting": [],
                "cost": None,
                "sourceTimestamp": None,
            }
        bridge = body.get("bridge") if isinstance(body.get("bridge"), dict) else {}
        bridge_ok = bridge.get("ok") is True
        cost = body.get("cost") if isinstance(body.get("cost"), dict) else None
        # "running"/"waiting" mohou v reálné odpovědi chybět nebo být null (ne jen []);
        # nedůvěřovat tvaru, jinak by iterace nad None shodila celý zdroj.
        raw_running = body.get("running")
        raw_waiting = body.get("waiting")
        return {
            "available": True,
            "bridgeOk": bridge_ok,
            "bridgeError": None if bridge_ok else str(bridge.get("error") or "bridge_unavailable"),
            "running": [redact(r) for r in raw_running if isinstance(r, dict)] if isinstance(raw_running, list) else [],
            "waiting": [redact(r) for r in raw_waiting if isinstance(r, dict)] if isinstance(raw_waiting, list) else [],
            "cost": (
                {
                    "todayUsd": cost.get("today_usd") if bridge_ok else None,
                    "limitUsd": cost.get("limit_usd"),
                    "reliable": bridge_ok,
                    "note": None if bridge_ok else "cost_unreliable_source_bridge_unavailable",
                }
                if cost is not None
                else None
            ),
            "sourceTimestamp": body.get("at") if isinstance(body.get("at"), str) else None,
        }

    def projects(self):
        status, body = self._fetch("/api/platno/projekty")
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("projekty"), list):
            return []
        out = []
        for item in body["projekty"]:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                out.append({"id": item["id"], "name": item.get("nazev"), "repoPath": item.get("repo_cesta")})
        return out


def _default_pid_probe(pid):
    if not isinstance(pid, int):
        return "unknown"
    if sys.platform == "win32":
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return "not_running"
            ctypes.windll.kernel32.CloseHandle(handle)
            return "process_exists_identity_unconfirmed"
        except Exception:  # noqa: BLE001 - probe nesmí shodit čtení zdroje, jen honestně vrátit "unknown".
            return "unknown"
    try:
        os.kill(pid, 0)
        return "process_exists_identity_unconfirmed"
    except ProcessLookupError:
        return "not_running"
    except PermissionError:
        return "process_exists_identity_unconfirmed"
    except Exception:  # noqa: BLE001 - probe nesmí shodit čtení zdroje, jen honestně vrátit "unknown".
        return "unknown"


def _strip_content_block(block):
    if not isinstance(block, dict):
        return None
    kind = block.get("type")
    if kind == "thinking":
        return None
    if kind == "text":
        return {"type": "text", "text": clip(redact(block.get("text", "")))}
    if kind == "tool_use":
        name = block.get("name")
        return {
            "type": "tool_use",
            "name": clip(redact(name), 120) if name is not None else None,
            "input": clip(redact(block.get("input")), TOOL_INPUT_LIMIT),
        }
    if kind == "tool_result":
        content = block.get("content")
        return {"type": "tool_result", "content": clip(redact(content))}
    return {"type": kind}


def _clipped_subtype(raw):
    subtype = raw.get("subtype")
    return clip(redact(subtype), 80) if subtype is not None else None


def _summarize_event(raw):
    kind = raw.get("type")
    if kind == "assistant":
        blocks = raw.get("message", {}).get("content", []) if isinstance(raw.get("message"), dict) else []
        content = [b for b in (_strip_content_block(c) for c in blocks if isinstance(c, dict)) if b is not None]
        if not content:
            return None
        return {"kind": "assistant", "content": content}
    if kind == "user":
        blocks = raw.get("message", {}).get("content", []) if isinstance(raw.get("message"), dict) else []
        content = [b for b in (_strip_content_block(c) for c in blocks if isinstance(c, dict)) if b is not None]
        if not content:
            return None
        return {"kind": "user", "content": content}
    if kind == "result":
        return {"kind": "result", "subtype": _clipped_subtype(raw), "summary": clip(redact(raw.get("result")))}
    if kind == "system":
        return {"kind": "system", "subtype": _clipped_subtype(raw)}
    return None


class LocalOrchestratorSource:
    """Čte pouze fixní artefakty pod jedním nakonfigurovaným kořenem (Hermes handoff lanes)."""

    def __init__(self, root, *, pid_probe=None):
        self.source_id = "hermes-orchestrator"
        self.root = Path(root).resolve()
        self._pid_probe = pid_probe or _default_pid_probe

    def is_available(self):
        return self.root.is_dir()

    def list_lanes(self):
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def _lane_dir(self, lane):
        if not isinstance(lane, str) or not _LANE_RE.fullmatch(lane):
            raise ValueError("invalid_lane_id")
        candidate = (self.root / lane).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("path_escape")
        return candidate

    def _safe_file(self, directory, filename):
        """Ověří obsažení AŽ výsledné (symlink/junction rozřešené) cesty konkrétního
        souboru pod kořenem, ne jen adresářového řetězce. Čtení pak jde přes tuto už
        rozřešenou cestu (ne znovu přes `directory / filename`), což zužuje TOCTOU
        okno na výměnu cíle přímo pod rozřešenou cestou — úplnou ochranu bez OS
        primitiv (O_NOFOLLOW na Windows chybí) nelze v čistém Pythonu zaručit.
        """
        candidate = directory / filename
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            return None
        try:
            resolved.relative_to(self.root)
        except ValueError:
            return None
        return resolved

    def read_lane(self, lane):
        directory = self._lane_dir(lane)
        if not directory.is_dir():
            return {"available": False, "lane": lane, "status": "unknown", "error": "source_missing"}
        state = self._read_state(directory)
        events = self._read_events(directory)
        result = self._read_json(directory, "result.json")
        return {
            "available": True,
            "lane": lane,
            "sourceRef": str(directory),
            "state": state,
            "liveness": self._liveness(state),
            "lastEventSeq": events["count"],
            "eventCounts": events["counts"],
            "truncated": events["truncated"],
            "preview": events["preview"],
            "result": redact(result) if result is not None else None,
        }

    def _read_json(self, directory, filename):
        path = self._safe_file(directory, filename)
        if path is None or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _read_state(self, directory):
        data = self._read_json(directory, "state.json")
        if data is None:
            return {"available": False}
        return {"available": True, "data": redact(data)}

    def _read_events(self, directory):
        path = self._safe_file(directory, "events.jsonl")
        if path is None:
            return {"count": 0, "counts": {}, "truncated": False, "preview": []}
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return {"count": 0, "counts": {}, "truncated": path.is_file(), "preview": []}
        # Skutečná hranice je velikost souboru (MAX_FILE_BYTES výše), ne umělý počet
        # řádků: dřívější tvrdý strop na 500 řádků způsoboval, že náhled i čítač
        # ukazovaly vždy jen prvních 500 událostí a nikdy se nedostaly k novějším —
        # v reálně běžícím logu tak "realtime" pohled zůstal navždy zaseknutý na
        # stejném místě. Paměť zůstává ohraničená (Counter + deque s pevnou délkou),
        # čas čtení je ohraničený velikostí souboru, ne libovolně zvětšenou konstantou.
        counts = Counter()
        window = deque(maxlen=PREVIEW_EVENTS)
        total = 0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(raw, dict):
                    continue
                total += 1
                counts[str(raw.get("type"))] += 1
                summary = _summarize_event(raw)
                if summary is not None:
                    window.append(summary)
        return {"count": total, "counts": dict(counts), "truncated": False, "preview": list(window)}

    def _liveness(self, state):
        if not state.get("available"):
            return {"status": "unknown", "reason": "state_missing_or_unreadable"}
        data = state["data"]
        if not isinstance(data, dict) or data.get("running") is not True:
            return {"status": "reported_stopped", "reportedRunning": False}
        pid = data.get("pid")
        probe = self._pid_probe(pid) if isinstance(pid, int) else "unknown"
        if probe == "not_running":
            return {
                "status": "stale_not_running",
                "reportedRunning": True,
                "note": "state.json tvrdí running, proces s tímto PID neběží",
            }
        return {
            "status": "last_reported_running_liveness_unverified",
            "reportedRunning": True,
            "note": "chybí čas vytvoření procesu v state.json; identitu PID nelze potvrdit",
        }
