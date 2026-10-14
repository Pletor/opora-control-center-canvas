"""Stav webu domén projektu (docs/domeny-a-worktree.md §8).

Hosty se berou výhradně z grafu projektu (uzly `site.kind == "application"` a jejich prostředí);
požadavek nikdy nenese URL ani host. Kontrola běží na dotaz, výsledek se drží v paměti 60 s na host,
ruční obnovení je možné nejdřív po 30 s od poslední kontroly. Žádná historie, nic se nepíše na disk.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from backend.integrations.web_probe_client import probe_host

CACHE_TTL_SECONDS = 60.0
REFRESH_MIN_SECONDS = 30.0
MAX_CONCURRENT_PROBES = 4
MAX_HOSTS_PER_PROJECT = 20


def _normalize_host(value):
    return str(value).strip().lower().rstrip(".")


def collect_hosts(graph, domain=None):
    """Seznam {domainId, environment, host, healthPath} z aplikačních uzlů grafu."""
    hosts = []
    for node in graph.get("nodes", []):
        site = node.get("site")
        if not isinstance(site, dict) or site.get("kind") != "application":
            continue
        if domain is not None and node.get("id") != domain:
            continue
        health_path = site.get("healthPath")
        for environment in site.get("environments") or []:
            host = _normalize_host(environment.get("host", ""))
            if host:
                hosts.append({"domainId": node["id"], "environment": environment.get("name"), "host": host,
                              "healthPath": health_path if isinstance(health_path, str) and health_path.startswith("/") else None})
    return hosts


class WebStatusService:
    def __init__(self, service, probe=probe_host, clock=time.monotonic, wall_clock=None):
        self.service = service
        self.probe = probe
        self.clock = clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self.cache = {}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PROBES, thread_name_prefix="web-probe")

    def _graph(self, project):
        info = self.service.project_hub.settings(project)["project"]
        wid = "main" if info["sourceKind"] == "git" else "draft"
        return self.service.view(project, wid)["graph"]

    def _cached(self, key, refresh):
        entry = self.cache.get(key)
        if entry is None:
            return None
        age = self.clock() - entry["at"]
        if age < (REFRESH_MIN_SECONDS if refresh else CACHE_TTL_SECONDS):
            return entry
        return None

    def _probe(self, item):
        result = self.probe(item["host"], item["healthPath"])
        entry = {"at": self.clock(), "checkedAt": self.wall_clock(), "result": result}
        with self.lock:
            self.cache[(item["host"], item["healthPath"])] = entry
        return entry

    def status(self, project, domain=None, refresh=False):
        items = collect_hosts(self._graph(project), domain)
        accepted, skipped = items[:MAX_HOSTS_PER_PROJECT], items[MAX_HOSTS_PER_PROJECT:]
        entries = {}
        pending = []
        for item in accepted:
            key = (item["host"], item["healthPath"])
            if key in entries:
                continue
            with self.lock:
                entry = self._cached(key, refresh)
            if entry is not None:
                entries[key] = entry
            else:
                pending.append((key, item))
        for (key, _), entry in zip(pending, self.pool.map(lambda pair: self._probe(pair[1]), pending)):
            entries[key] = entry
        rows = [self._row(item, entries[(item["host"], item["healthPath"])]) for item in accepted]
        rows += [{"domainId": item["domainId"], "environment": item["environment"], "host": item["host"],
                  "state": "unchecked", "httpStatus": None, "health": None, "latencyMs": None,
                  "checkedAt": None, "detail": f"nad limit {MAX_HOSTS_PER_PROJECT} hostů na projekt"} for item in skipped]
        return {"hosts": rows}

    @staticmethod
    def _row(item, entry):
        result = entry["result"]
        return {"domainId": item["domainId"], "environment": item["environment"], "host": item["host"],
                "state": result["state"], "httpStatus": result.get("httpStatus"), "health": result.get("health"),
                "latencyMs": result.get("latencyMs"), "checkedAt": entry["checkedAt"], "detail": result.get("detail")}
