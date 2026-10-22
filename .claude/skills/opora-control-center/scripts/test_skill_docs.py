"""Dokumentace skillu = kód: reference pokrývají všechny cesty a příkazy a příklady JSON projdou backendem.

Příklad je blok ```json hned za značkou `<!-- example: /api/… -->`. Zástupné hodnoty (DIGEST, NODE_ID,
CONTEXT_VERSION, …) test doplní z běžící aplikace a příklady pošle ve stejném pořadí, v jakém je dělá agent:
dávka plánu → převzetí → prostor agenta → blok → pipeline → výstup.
"""

import json
import re
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import opora_write  # noqa: E402

EXAMPLE = re.compile(r"<!-- example: (?P<route>/api/[a-z0-9/-]+) -->\s*```json\n(?P<body>.*?)```", re.S)
ORIGIN = "http://127.0.0.1:8740"
SCOPE = {"project": "draft", "workspace": "draft"}


def examples():
    found = {}
    for path in sorted((SKILL / "references").glob("*.md")):
        for match in EXAMPLE.finditer(path.read_text("utf-8")):
            found[match["route"]] = match["body"]
    return found


def read_commands():
    source = (SKILL / "scripts" / "opora_read.py").read_text("utf-8")
    block = re.search(r"'command', choices=\[(.*?)\]\)", source, re.S).group(1)
    return re.findall(r"'([a-z-]+)'", block)


def test_api_reference_covers_every_write_route_and_read_command():
    api = (SKILL / "references" / "api.md").read_text("utf-8")
    assert [route for route in sorted(opora_write.WRITE_ROUTES) if f"`{route}`" not in api] == []
    commands = read_commands()
    assert len(commands) > 20
    assert [name for name in commands if f"`{name}`" not in api] == []


def test_skill_md_is_a_short_router_linking_every_reference():
    skill = (SKILL / "SKILL.md").read_text("utf-8")
    assert len(skill.splitlines()) <= 200
    assert "allowed-tools: Read, Grep, Glob, Bash" in skill and "router" not in skill.split("---")[1]
    linked = set(re.findall(r"\]\((references/[a-z-]+\.md|assets/[a-z-]+\.md)\)", skill))
    assert all((SKILL / link).is_file() for link in linked)
    references = {f"references/{p.name}" for p in (SKILL / "references").glob("*.md")} - {"references/source-map.md"}
    assert references - linked == set()
    for path in (SKILL / "references").glob("*.md"):
        if path.name not in ("source-map.md", "navigation.md", "rlm.md", "graphify.md", "archify.md",
                             "map-refresh.md", "external-agent.md"):
            assert "Kdy mě číst" in path.read_text("utf-8"), path.name


def test_examples_pass_the_real_backend_in_agent_order(tmp_path):
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    found = examples()
    assert {"/api/canvas-plan", "/api/desktop-v3/lease", "/api/desktop-v3/agent-workspace", "/api/desktop-v3/block",
            "/api/desktop-v3/pipeline", "/api/desktop-v3/agent-output"} <= set(found)
    agent = {"origin": ORIGIN, "X-Opora-Actor": "agent; name=worker-7f3a"}

    def body(route, **values):
        text = found[route]
        for key, value in values.items():
            text = text.replace(f'"{key}"', json.dumps(value))
        for key, value in values.items():
            text = text.replace(key, str(value))
        return {**SCOPE, **json.loads(text)}

    def post(route, payload, headers=agent):
        response = client.post(route, headers=headers, json=payload)
        assert response.status_code == 200, (route, response.text)
        return response.json()

    def revision():
        return client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]

    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        planned = post("/api/canvas-plan", body("/api/canvas-plan", DIGEST=digest))
        node = planned["refs"]["ingest"]
        lease = post("/api/desktop-v3/lease", body("/api/desktop-v3/lease", NODE_ID=node))
        leased = {**agent, "X-Opora-Lease": lease["token"]}
        post("/api/desktop-v3/agent-workspace", body("/api/desktop-v3/agent-workspace", NODE_ID=node))
        post("/api/desktop-v3/block", {**body("/api/desktop-v3/block", NODE_ID=node), "expectedRevision": revision()}, leased)
        post("/api/desktop-v3/pipeline", {**body("/api/desktop-v3/pipeline", NODE_ID=node), "expectedRevision": revision()})
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": node}).json()
        request = brief["outputContract"]["request"]
        output = body("/api/desktop-v3/agent-output", NODE_ID=node, CONTEXT_VERSION=request["contextVersion"],
                      BLOCK_ID=planned["blocks"]["ingest/formaty"], EDGE_ID=brief["graph"]["outgoing"][0]["edgeId"],
                      STAGE_ID=brief["pipeline"]["current"]["id"])
        saved = post("/api/desktop-v3/agent-output", {**output, "expectedRevision": request["expectedRevision"]}, leased)
        stages = saved["state"]["nodes"][node]["stages"]["items"]
        assert stages[0]["status"] == "passed" and stages[0]["doneBy"] == "worker-7f3a"


@pytest.mark.parametrize("route", ["/api/desktop-v3/rule"])
def test_inline_rule_example_has_the_validated_shape(route):
    api = (SKILL / "references" / "api.md").read_text("utf-8")
    block = re.search(r'```json\n(\{"id": "r1".*?)```', api, re.S).group(1)
    payload = json.loads(block)
    from backend.editor.agent_memory.memory_items import KEYS
    assert set(payload) | {"project", "workspace"} == KEYS and route in opora_write.WRITE_ROUTES


def test_brief_vault_example_creates_a_verbatim_root(tmp_path):
    """Příklad schránky zadání z api.md projde backendem a text se uloží doslova (B4)."""
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    payload = {**SCOPE, **json.loads(examples()["/api/brief-vault"])}
    assert "/api/brief-vault" in opora_write.WRITE_ROUTES
    agent = {"origin": ORIGIN, "X-Opora-Actor": "agent; name=worker-7f3a"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        created = client.post("/api/brief-vault", headers=agent, json=payload)
        assert created.status_code == 200, created.text
        fragment = created.json()["fragment"]
        detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment["id"]}).json()
        assert detail["fragment"]["text"] == payload["text"] and fragment["by"] == "worker-7f3a"
        split = client.post("/api/brief-vault", headers=agent, json={**SCOPE, "op": "split", "fragmentId": fragment["id"],
                                                                     "expectedRevision": 1, "parts": [
            {"title": "1", "text": payload["text"].split("\n\n")[0]}, {"title": "2", "text": payload["text"].split("\n\n")[1]}]})
        assert split.status_code == 200, split.text


def test_drawing_sketch_example_passes_backend_and_marks_stale(tmp_path):
    """Příklad skici momentu z api.md projde backendem; zápis nastaví imageStale (docs/storyboard-karty.md)."""
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    assert "/api/drawing" in opora_write.WRITE_ROUTES
    agent = {"origin": ORIGIN, "X-Opora-Actor": "agent; name=worker-7f3a"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        card = {"id": "karta", "parentId": None, "kind": "node", "name": "Karta", "purpose": "", "x": 0, "y": 0}
        assert client.post("/api/graph", headers=agent, json={**SCOPE, "graph": {"nodes": [card], "edges": []},
                                                                "digest": digest}).status_code == 200
        png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        assert client.post("/api/drawing-file", headers=agent, json={**SCOPE, "file": {"id": "a1", "mimeType": "image/png", "dataURL": png}}).status_code == 200
        board = {"animation": "kulicka", "duration": 12, "moments": [{"t": 1, "id": "m-3f9a1c2e",
                 "sketch": {"layer": "sb/karta/m-3f9a1c2e", "fileId": "a1"}}]}
        saved = client.post("/api/storyboard", headers=agent, json={**SCOPE, "nodeId": "karta", "expected_revision": 0,
                                                                   "storyboard": board})
        assert saved.status_code == 200, saved.text
        payload = {**SCOPE, **json.loads(examples()["/api/drawing"].replace("NODE_ID", "karta"))}
        response = client.post("/api/drawing", headers=agent, json=payload)
        assert response.status_code == 200, response.text
        stored = client.get("/api/storyboard", params={**SCOPE, "nodeId": "karta"}).json()
        assert stored["storyboard"]["moments"][0]["sketch"]["imageStale"] is True and stored["revision"] == 2


# Cesty, které skill popisuje dopředu podle kontraktu noční směny; po nasazení PR z pending zmizí.
PENDING_ROUTES = {
    "/api/oporahub/events": "od PR card-dag-events",
    "/api/oporahub/events/stream": "od PR card-dag-events",
}
# Zmíněné záměrně jako neexistující (provoz.md: „Cesta /api/status neexistuje“).
NOT_ROUTES = {"/api/status"}
MENTION = re.compile(r"/api/[A-Za-z0-9_./{}<>-]*[A-Za-z0-9}>]")
PLACEHOLDER = re.compile(r"^(\{[^}]*\}|<[^>]*>|[A-Z][A-Z0-9_]*)$")


def _segments(path):
    return ["{}" if PLACEHOLDER.match(part) else part for part in path.rstrip("/").split("/")]


@pytest.fixture(scope="module")
def backend_routes(tmp_path_factory):
    """(metoda, segmenty) každé cesty skutečné aplikace, včetně cest mimo schéma."""
    from backend.app.factory import create_app

    app = create_app(tmp_path_factory.mktemp("routes") / "data")
    routes = set()
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            routes.add((method.upper(), tuple(_segments(path))))
    return routes


def _exists(segments, routes, method=None):
    for verb, known in routes:
        if method and verb != method:
            continue
        if len(known) >= len(segments) and all(
                want == got or want == "{}" or (got == "{}" and want != "{}")
                for want, got in zip(known, segments)):
            if len(known) == len(segments) or method is None:
                return True
    return False


def test_every_endpoint_in_the_skill_exists_in_the_backend(backend_routes):
    """Každá cesta v SKILL.md a references/ je v tabulce cest backendu, nebo výslovně pending."""
    files = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
    missing = {}
    for path in files:
        for mention in set(MENTION.findall(path.read_text("utf-8"))):
            route = mention.rstrip(".")
            if route in PENDING_ROUTES or route in NOT_ROUTES:
                continue
            if not _exists(_segments(route), backend_routes):
                missing.setdefault(route, []).append(path.name)
    assert missing == {}


def test_pending_routes_are_marked_in_the_docs_and_still_missing(backend_routes):
    hub_api = (SKILL / "references" / "hub-api.md").read_text("utf-8")
    for route, source in PENDING_ROUTES.items():
        assert f"`GET {route}` | read | **pending** ({source})" in hub_api
        # Až PR přistane, přesuň cestu z PENDING_ROUTES do běžné tabulky.
        assert not _exists(_segments(route), backend_routes, "GET"), route


def test_hub_write_templates_are_documented_and_exist_as_post(backend_routes):
    hub_api = (SKILL / "references" / "hub-api.md").read_text("utf-8")
    templates = opora_write.HUB_AGENT_ROUTES + opora_write.HUB_HUMAN_ROUTES + opora_write.HUB_TOKEN_ROUTES
    assert len(set(templates)) == len(templates)
    for template in templates:
        assert _exists(_segments(template), backend_routes, "POST"), template
        assert template in hub_api, template
    for template in opora_write.HUB_HUMAN_ROUTES:
        row = next(line for line in hub_api.splitlines() if template in line)
        assert "člověk" in row, template
