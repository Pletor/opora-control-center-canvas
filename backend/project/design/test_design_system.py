"""DESIGN.md z commitnuté revize: pracovní strom se neukáže, otisk přes celé bajty, strop 64 KiB, chybějící = available false."""
import hashlib
import subprocess
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.project.design_system_routes import create_design_system_router
from backend.project.design import design_system

URL = "/api/oporahub/design-system"
AGENT = {"x-actor": "agent", "x-agent": "office"}


def run(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@example.com", "-c", "user.name=t",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)


def repository(tmp_path, content=None):
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    run(root, "init", "-q")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    if content is not None:
        (root / "DESIGN.md").write_bytes(content)
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", "init")
    return root


def service_for(root):
    return SimpleNamespace(project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourcePath": str(root)}}))


def client_for(service):
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.actor, request.state.agent = (request.headers.get("x-actor") or None), request.headers.get("x-agent")
        return await call_next(request)

    app.include_router(create_design_system_router(service))
    return TestClient(app)


def test_design_md_comes_from_the_committed_revision_not_the_working_tree(tmp_path):
    content = "# Design\n\nBarvy: **#0b1f3a**, písmo Inter.\n".encode()
    root = repository(tmp_path, content)
    (root / "DESIGN.md").write_text("# Rozepsané, necommitnuté\n", encoding="utf-8")
    value = design_system.read(service_for(root), "p")
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    assert value["available"] is True and value["revision"] == head and value["truncated"] is False
    assert value["sha256"] == hashlib.sha256(content).hexdigest() and value["bytes"] == len(content)
    assert value["markdown"] == content.decode()
    assert "markdown" not in design_system.reference(service_for(root), "p")


def test_large_design_md_is_truncated_and_missing_one_is_not_an_error(tmp_path):
    big = b"# D\n" + b"x" * (70 * 1024)
    value = design_system.read(service_for(repository(tmp_path, big)), "p")
    assert value["truncated"] is True and len(value["markdown"].encode()) == design_system.MAX_BYTES
    assert value["bytes"] == len(big) and value["sha256"] == hashlib.sha256(big).hexdigest()
    other = tmp_path / "other"
    other.mkdir()
    missing = design_system.read(service_for(repository(other)), "p")
    assert missing["available"] is False and len(missing["revision"]) == 40
    assert design_system.read(SimpleNamespace(project_hub=SimpleNamespace(
        settings=lambda project: {"project": {"sourcePath": None}})), "p")["available"] is False


def test_route_needs_identity_and_answers_304_for_the_same_revision(tmp_path):
    root = repository(tmp_path, b"# Design\n")
    client = client_for(service_for(root))
    assert client.get(URL, params={"project": "p"}).status_code == 428
    first = client.get(URL, headers=AGENT, params={"project": "p"})
    assert first.status_code == 200 and first.json()["markdown"] == "# Design\n"
    tag = first.headers["etag"]
    assert client.get(URL, headers={**AGENT, "if-none-match": tag}, params={"project": "p"}).status_code == 304
    (root / "DESIGN.md").write_text("# Design v2\n", encoding="utf-8")
    assert client.get(URL, headers={**AGENT, "if-none-match": tag}, params={"project": "p"}).status_code == 304
    run(root, "commit", "-q", "-am", "v2")
    changed = client.get(URL, headers={**AGENT, "if-none-match": tag}, params={"project": "p"})
    assert changed.status_code == 200 and changed.json()["markdown"] == "# Design v2\n"
