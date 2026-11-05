"""Velín V3: rozhovor a monitoring pro `GET /api/pletor/messages` a `/monitoring`. Jen čte; padlý zdroj = `{error}`."""
import json

from backend.agi_pletor import store
from backend.agi_pletor.dashboard.heart_view import safe
from backend.agi_pletor.monitoring.monitor import monitor_settings
from backend.brain_opora.determinism import brain_files
from backend.flow.run_log import read_canvas

EVENTS = 50


def messages_view(folder, project, workspace, limit=50, q=""):
    """`{messages, total}`: zprávy rozhovoru s podřetězcem `q` (bez ohledu na velikost), posledních `limit`."""
    found = store.messages(folder, project, workspace, last=10**9)
    needle = q.strip().lower()
    if needle:
        found = [message for message in found if needle in str(message["text"] or "").lower()]
    return {"messages": found[-limit:], "total": len(found)}


def _hosts(service, project):
    path = brain_files.brain_dir(service, project) / "monitor_state.json"
    if not path.exists():
        return []
    state = json.loads(path.read_text(encoding="utf-8"))
    return [{"host": host, **item} for host, item in state.items()]


def _events(service, project):
    with service.registry_lock:
        return read_canvas(service.db, 4, project, EVENTS)


def monitoring_view(service, project):
    return {"hosts": safe(lambda: _hosts(service, project)), "events": safe(lambda: _events(service, project)),
            "enabled": safe(lambda: monitor_settings(service, project).get("enabled") is True)}
