from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.project.project_web_status_routes import create_project_web_status_router


class FakeStatus:
    def __init__(self):
        self.calls = []

    def status(self, project, domain, refresh):
        self.calls.append((project, domain, refresh))
        return {"hosts": []}


def client_for(fake):
    app = FastAPI()
    app.include_router(create_project_web_status_router(fake))
    return TestClient(app)


def test_route_passes_only_project_domain_and_refresh():
    fake = FakeStatus()
    client = client_for(fake)
    assert client.get("/api/project-architecture/web-status", params={"project": "p"}).json() == {"hosts": []}
    client.get("/api/project-architecture/web-status", params={"project": "p", "domain": "d", "refresh": "true", "host": "evil.com", "url": "http://x"})
    assert fake.calls == [("p", None, False), ("p", "d", True)]


def test_route_requires_project():
    assert client_for(FakeStatus()).get("/api/project-architecture/web-status").status_code == 422
