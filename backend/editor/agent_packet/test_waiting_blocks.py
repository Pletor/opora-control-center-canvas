"""Blocked work remains unfinished and carries the agent's request to the human."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import ORIGIN, SCOPE, output, payload, prepared, send


def test_agent_block_note_reaches_brief_without_changing_specification(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        params = {**SCOPE, 'nodeId': 'focus'}
        before = client.get('/api/desktop-v3/node-brief', params=params).json()
        result = send(client, payload(output=output(
            blocks=[{'blockId': 'b1', 'status': 'blocked', 'note': 'Supply the project URL'},
                    {'blockId': 'b2', 'status': 'unmet', 'note': 'Tests fail'}],
            done={'proposed': False, 'note': ''},
        )))
        assert result.status_code == 200, result.text
        after = client.get('/api/desktop-v3/node-brief', params=params).json()
        assert after['contextVersion'] == before['contextVersion']
        assert after['loop']['openBlocks'] == 2
        assert after['loop']['waitingOnHuman'] == [{'blockId': 'b1', 'ask': 'Supply the project URL'}]
        result = send(client, payload(result.json()['revision'], output=output(
            blocks=[{'blockId': 'b1', 'status': 'met', 'note': 'URL supplied'}],
            done={'proposed': False, 'note': ''},
        )))
        assert result.status_code == 200, result.text
        after = client.get('/api/desktop-v3/node-brief', params=params).json()
        assert after['loop']['waitingOnHuman'] == []
        assert after['loop']['openBlocks'] == 1
