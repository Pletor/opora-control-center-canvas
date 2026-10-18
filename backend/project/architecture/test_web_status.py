from types import SimpleNamespace

from backend.project.architecture import web_status as module
from backend.project.architecture.web_status import WebStatusService


def app_node(identifier, hosts, health=None):
    site = {"kind": "application", "environments": [{"name": f"env{i}", "host": h} for i, h in enumerate(hosts)]}
    if health:
        site["healthPath"] = health
    return {"id": identifier, "site": site}


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


def build(nodes, source_kind="git"):
    calls = []
    views = []

    def probe(host, health):
        calls.append((host, health))
        return {"state": "up", "httpStatus": 200, "health": None, "latencyMs": 5, "detail": "HTTP 200"}

    def view(pid, wid):
        views.append(wid)
        return {"graph": {"nodes": nodes, "edges": []}}

    service = SimpleNamespace(view=view, project_hub=SimpleNamespace(settings=lambda p: {"project": {"sourceKind": source_kind}}))
    clock = Clock()
    return WebStatusService(service, probe=probe, clock=clock, wall_clock=lambda: "T"), calls, views, clock


def test_hosts_only_from_application_nodes_and_default_workspace():
    nodes = [app_node("a", ["WWW.Example.cz.", "app.example.cz"], "/health"),
             {"id": "page", "site": {"kind": "page", "path": "/"}}, {"id": "plain"}]
    svc, calls, views, _ = build(nodes)
    rows = svc.status("p")["hosts"]
    assert [r["host"] for r in rows] == ["www.example.cz", "app.example.cz"]
    assert {r["domainId"] for r in rows} == {"a"} and rows[0]["checkedAt"] == "T" and rows[0]["state"] == "up"
    assert sorted(calls) == [("app.example.cz", "/health"), ("www.example.cz", "/health")]
    assert views == ["main"]


def test_draft_for_non_git_project():
    svc, _, views, _ = build([app_node("a", ["a.example.cz"])], "local")
    svc.status("p")
    assert views == ["draft"]


def test_domain_filter_and_request_cannot_inject_host():
    svc, calls, _, _ = build([app_node("a", ["a.example.cz"]), app_node("b", ["b.example.cz"])])
    assert [r["host"] for r in svc.status("p", "b")["hosts"]] == ["b.example.cz"]
    assert svc.status("p", "evil.example.com")["hosts"] == []
    assert all(host.endswith("example.cz") for host, _ in calls)


def test_cache_ttl_and_refresh_rate_limit():
    svc, calls, _, clock = build([app_node("a", ["a.example.cz"])])
    svc.status("p")
    clock.now += 59
    svc.status("p")
    assert len(calls) == 1
    clock.now += 2
    svc.status("p")
    assert len(calls) == 2
    clock.now += 10
    svc.status("p", refresh=True)
    assert len(calls) == 2
    clock.now += 21
    svc.status("p", refresh=True)
    assert len(calls) == 3


def test_twenty_host_cap_marks_rest_unchecked():
    hosts = [f"h{i}.example.cz" for i in range(23)]
    svc, calls, _, _ = build([app_node("a", hosts)])
    rows = svc.status("p")["hosts"]
    assert len(rows) == 23 and len(calls) == module.MAX_HOSTS_PER_PROJECT
    assert [r["state"] for r in rows[20:]] == ["unchecked"] * 3
