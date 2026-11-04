"""Tik monitoringu (plátno 4, M1): změří hosty projektu a do logu pláten zapíše jen přechod stavu.

Hosty bere stejný zdroj jako stav webu (`collect_hosts` nad přijatým grafem). Stav po hostu (`state` + poslední
měření) leží v `<data>/projects/<id>/brain/monitor_state.json`. Přechod do `down` píše `outage.failed`, do `slow`
`slow.failed` (obojí přes `log_canvas` budí srdce), návrat do `ok` píše `outage.recovered`. Stejný stav se znovu
nezapisuje. Zapíná se v nastavení projektu `settings.monitor.enabled` (project.json), výchozí vypnuto.
"""

import json
import logging
import os
import threading

from backend.flow.canvas_log import log_canvas
from backend.monitoring.detector import SLOW_MS, STREAK, detect
from backend.monitoring.probes import probe as probe_host
from backend.project.architecture.web_status import MAX_HOSTS_PER_PROJECT, collect_hosts
from backend.project.architecture.work_status import architecture_graph

LOGGER = logging.getLogger(__name__)
TICK_SECONDS = 60.0
KINDS = {"down": "outage.failed", "slow": "slow.failed", "ok": "outage.recovered"}


def project_hosts(service, project):
    # shortcut: hosty se měří po sobě (20 × 5 s timeout > tik), paralelně až při desítkách hostů
    return collect_hosts(architecture_graph(service, project))[:MAX_HOSTS_PER_PROJECT]


def monitor_settings(service, project):
    """`settings.monitor` z project.json; chybějící nebo poškozené = vypnuto."""
    try:
        value = service.folder(project).read().get("settings", {}).get("monitor")
    except (ValueError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


class Monitor:
    def __init__(self, service, *, probe=probe_host, log=log_canvas, hosts=project_hosts, tick=TICK_SECONDS):
        self.service, self.probe, self.log, self.hosts, self.tick = service, probe, log, hosts, tick
        self.stop, self.thread = threading.Event(), None

    def start(self):
        if self.thread or self.stop.is_set():
            return
        self.thread = threading.Thread(target=self._loop, name="opora-monitor", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _loop(self):
        while not self.stop.wait(self.tick):
            for project in self.service.project_ids():
                if self.stop.is_set():
                    return
                try:
                    self.run(project)
                except Exception:
                    LOGGER.exception("Monitoring: tik projektu %s selhal; smyčka běží dál.", project)

    def _state_file(self, project):
        # shortcut: stav v JSON vedle srdce, ne v DB projektu; do DB až ho bude číst plátno (M3)
        return self.service.folder(project).path / "brain" / "monitor_state.json"

    def run(self, project):
        """Tik projektu se zapnutým monitoringem; vrací zapsané přechody `[{host, kind, ...}]`."""
        settings = monitor_settings(self.service, project)
        if project == "draft" or settings.get("enabled") is not True:
            return []
        slow_ms = settings.get("slowMs") if isinstance(settings.get("slowMs"), int) else SLOW_MS
        return self.tick_project(project, slow_ms)

    def tick_project(self, project, slow_ms=SLOW_MS):
        path = self._state_file(project)
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = {}
        state, written = {}, []
        for item in self.hosts(self.service, project):
            key = item["host"] + (item["healthPath"] or "")
            if key in state:
                continue
            previous = stored.get(key, {})
            result = self.probe(item["host"], item["healthPath"])
            history = [*previous.get("history", []), result][-STREAK:]
            before, now = previous.get("state", "ok"), detect(history, slow_ms)
            state[key] = {"state": now, "history": history}
            if now != before:
                payload = {"host": item["host"], "environment": item["environment"], "domainId": item["domainId"],
                           "state": now, "previous": before, "probe": result}
                self.log(self.service, project, 4, KINDS[now], payload, author="monitor")
                written.append({"host": item["host"], "kind": KINDS[now], "state": now, "previous": before})
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        return written
