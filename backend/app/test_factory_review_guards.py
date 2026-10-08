"""RED->GREEN regrese na konkrétní nálezy backendového review WU-DESKTOP-V2.

Každý test cílí na jeden prokázaný nález (viz API-FIX-HANDOFF.md):
1) redaktor kontextových paketů propouštěl holé fine-grained tokeny github_pat_,
2) dokumentace uložené cesty se stala nečitelnou (503), když zdrojový soubor zmizel.
"""

from fastapi.testclient import TestClient
from backend.project.workspace.test_workspace_sources import ORIGIN, attach

from backend.app.factory import create_app
from backend.editor.agent_packet.redact import redact_text

# Syntetický token ve tvaru fine-grained GitHub PAT; není to skutečný přístupový údaj.
FIXTURE_PAT = "github_pat_11FAKE0000fakefakefakefake0123456789abcdefghijklmnop"

DOC_FIELDS = {
    "purpose": "Smysl souboru", "goal": "Cíl", "architecture": "Vrstvy",
    "technologies": "Python", "notes": "Poznámky", "requirements": "Požadavek není důkaz.",
}


# ---------------------------------------------------------------------------
# 1) Kontextový paket nesmí propustit holý github_pat_ token do žádné vrstvy.
# ---------------------------------------------------------------------------


def test_packet_redactor_masks_bare_fine_grained_github_token(tmp_path):
    for text in (f"Uzel {FIXTURE_PAT}", f"Účel {FIXTURE_PAT}", f"Deník s tokenem {FIXTURE_PAT}"):
        redacted = redact_text(text)
        assert FIXTURE_PAT not in redacted
        assert "[REDACTED]" in redacted
    assert redact_text("") == "" and redact_text(None) is None
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view").json()
        nodes = [
            {"id": "sector", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
            {"id": "focus", "parentId": "sector", "kind": "node",
             "name": f"Uzel {FIXTURE_PAT}", "purpose": f"Účel {FIXTURE_PAT}", "x": 0, "y": 0},
        ]
        assert client.post("/api/graph", headers={"origin": ORIGIN}, json={
            "project": "draft", "workspace": "draft", "digest": view["digest"], "graph": {"nodes": nodes, "edges": []},
        }).status_code == 200
        preview = client.post("/api/desktop-v3/packet/preview", headers={"origin": ORIGIN}, json={
            "project": "draft", "workspace": "draft", "nodeId": "focus", "path": "", "sessionId": "",
            "references": [], "note": f"Poznámka {FIXTURE_PAT}",
        })
        assert preview.status_code == 200, preview.text
        assert FIXTURE_PAT not in preview.text
        assert "[REDACTED]" in preview.text


# ---------------------------------------------------------------------------
# 2) Dokumentace zůstává čitelná i bez zdrojového souboru; nová cesta je 409.
# ---------------------------------------------------------------------------


def test_saved_documentation_survives_deletion_of_its_source_file(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    code = source / "hello.py"
    code.write_text("print('hi')", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft", "path": "hello.py"}
        saved = client.post("/api/workspace/document", headers={"origin": ORIGIN},
                            json={**scope, "expectedRevision": 0, "fields": DOC_FIELDS, "nodeId": None})
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        code.unlink()
        response = client.get("/api/workspace/document", params=scope)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "source_missing"
        assert body["changeDetection"] == "source_missing"
        assert body["revision"] == 1 and body["fields"] == DOC_FIELDS
        assert set(body) == set(saved.json())


def test_documentation_for_never_existing_path_is_rejected_as_conflict(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "hello.py").write_text("print('hi')", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft", "path": "nikdy-neexistoval.py"}
        assert client.get("/api/workspace/document", params=scope).status_code == 409
        created = client.post("/api/workspace/document", headers={"origin": ORIGIN},
                              json={**scope, "expectedRevision": 0, "fields": DOC_FIELDS, "nodeId": None})
        assert created.status_code == 409
        escape = {"project": pid, "workspace": "draft", "path": "../mimo.py"}
        assert client.get("/api/workspace/document", params=escape).status_code == 409


def test_documentation_stays_readable_when_whole_source_root_disappears(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    code = source / "hello.py"
    code.write_text("print('hi')", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft", "path": "hello.py"}
        assert client.post("/api/workspace/document", headers={"origin": ORIGIN},
                           json={**scope, "expectedRevision": 0, "fields": DOC_FIELDS,
                                 "nodeId": None}).status_code == 200
        code.unlink()
        source.rmdir()
        response = client.get("/api/workspace/document", params=scope)
        assert response.status_code == 200
        assert response.json()["status"] == "source_missing"
        assert response.json()["fields"] == DOC_FIELDS
