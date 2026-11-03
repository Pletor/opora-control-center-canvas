import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opora_save

from backend.app.factory import create_app
from backend.editor.canvas_versions.test_canvas_versions import ORIGIN, graph, install_graph, versions


def test_save_script_uses_scope_token_and_agent_identity_and_skips_clean_canvas(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph('a'))
        calls = []

        def transport(request, timeout):
            url = urlsplit(request.full_url)
            calls.append(request.get_method())
            response = client.request(request.get_method(), url.path + ('?' + url.query if url.query else ''),
                                      headers=dict(request.header_items()), content=request.data)
            assert response.status_code == 200, response.text
            if request.data:
                assert json.loads(request.data)['expectedToken']
            return response.json()

        monkeypatch.setattr(opora_save, '_read', transport)
        first = opora_save.save(ORIGIN, 'draft', 'draft', 'Test agent', True)
        assert first['saved'] is True and first['version']['actor'] == 'agent'
        assert first['version']['changedCardCount'] == 1
        assert calls == ['GET', 'GET', 'POST']
        assert versions(client)['dirty'] is False
        calls.clear()
        assert opora_save.save(ORIGIN, 'draft', 'draft', 'Test agent', True)['saved'] is False
        assert calls == ['GET']
