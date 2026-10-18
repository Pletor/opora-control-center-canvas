"""Registr session asistenta: `<datový kořen>/assistant/sessions.json` (docs/asistent.md §4).

Zápis je atomický (`.tmp` + `os.replace`) a pod zámkem. Historie zpráv tu není; čte se
z přepisu Claude Code. Po startu aplikace žádný proces neběží, proto `running` → `idle`.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

STATES = ("idle", "running", "waiting_approval", "closed", "error")
DEFAULT_TITLE = "Nový úkol"
# Výchozí názvy, které první zpráva nahradí; „Nová session“ zůstává z fáze 1 v existujících registrech.
PLACEHOLDER_TITLES = frozenset({DEFAULT_TITLE, "Nová session"})
TITLE_LIMIT = 60
FIELDS = ("id", "projectId", "workspace", "title", "model", "claudeSessionId",
          "createdAt", "updatedAt", "state", "nodeId", "sectorId", "metrics")


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def title_from(text):
    clean = " ".join(str(text or "").split())
    return clean[:TITLE_LIMIT] if clean else DEFAULT_TITLE


class SessionRegistry:
    def __init__(self, data_root):
        self.path = Path(data_root) / "assistant" / "sessions.json"
        self._lock = threading.RLock()
        self._sessions = self._load()
        changed = False
        for record in self._sessions.values():
            if record.get("state") in ("running", "waiting_approval"):
                record["state"] = "idle"
                changed = True
        if changed:
            self._save()

    def _load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, UnicodeError):
            return {}
        items = raw.get("sessions") if isinstance(raw, dict) else None
        sessions = {}
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("state") in STATES:
                sessions[item["id"]] = {key: item.get(key) for key in FIELDS}
        return sessions

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        data = {"sessions": list(self._sessions.values())}
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def create(self, project, workspace, model, title=None, node_id=None, sector_id=None):
        stamp = now_iso()
        record = {
            "id": uuid.uuid4().hex,
            "projectId": project,
            "workspace": workspace,
            "title": title.strip() if isinstance(title, str) and title.strip() else DEFAULT_TITLE,
            "model": model,
            "claudeSessionId": None,
            "createdAt": stamp,
            "updatedAt": stamp,
            "state": "idle",
            "nodeId": node_id,
            "sectorId": sector_id,
        }
        with self._lock:
            self._sessions[record["id"]] = record
            self._save()
            return dict(record)

    def get(self, session_id):
        with self._lock:
            record = self._sessions.get(session_id)
            return dict(record) if record else None

    def list(self, project=None, include_closed=False):
        with self._lock:
            items = [dict(item) for item in self._sessions.values()
                     if (project is None or item["projectId"] == project)
                     and (include_closed or item["state"] != "closed")]
        return sorted(items, key=lambda item: item["createdAt"])

    def update(self, session_id, **changes):
        unknown = set(changes) - set(FIELDS[3:])
        if unknown:
            raise ValueError("Neznámé pole session.")
        if "state" in changes and changes["state"] not in STATES:
            raise ValueError("Neplatný stav session.")
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            if all(record.get(key) == value for key, value in changes.items()):
                return dict(record)
            record.update(changes)
            record["updatedAt"] = now_iso()
            self._save()
            return dict(record)
