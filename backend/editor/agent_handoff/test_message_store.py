"""Adresované zprávy mezi otevřenými kartami: první vertikální řezy API → SQLite → readback."""

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
GRAPH = {
    "nodes": [
        {"id": "sektor", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
        {"id": "a", "parentId": "sektor", "kind": "node", "name": "Agent A", "purpose": "", "x": 0, "y": 0},
        {"id": "b", "parentId": "sektor", "kind": "node", "name": "Agent B", "purpose": "", "x": 400, "y": 0},
    ],
    "edges": [],
}


def seed_graph(client):
    view = client.get("/api/view", params=SCOPE).json()
    saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": GRAPH, "digest": view["digest"]})
    assert saved.status_code == 200, saved.text


def message_payload(**overrides):
    payload = {
        **SCOPE,
        "sourceNodeId": "a",
        "targetNodeId": "b",
        "kind": "handoff",
        "body": "Ověř prosím tento řez.",
        "replyToMessageId": None,
        "idempotencyKey": "handoff-001",
        "senderLabel": "Agent A",
    }
    return {**payload, **overrides}


def test_posted_message_reads_back_to_its_target_with_immutable_digest(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)

        created = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload())

        assert created.status_code == 200, created.text
        message = created.json()["message"]
        assert message["sourceNodeId"] == "a"
        assert message["targetNodeId"] == "b"
        assert message["identityVerified"] is False
        assert message["receipt"] is None
        assert len(message["digest"]) == 64
        incoming = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "b", "direction": "incoming"})
        assert incoming.status_code == 200, incoming.text
        assert incoming.json() == {
            "messages": [message],
            "readOnly": False,
            # Každá existující karta v grafu je lokální adresát, kromě právě čtené karty.
            "targets": [{"id": "sektor", "name": "Sektor"}, {"id": "a", "name": "Agent A"}],
            "hasMore": False,
            "nextBefore": None,
        }


def test_retry_returns_same_message_but_changed_payload_conflicts(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        first = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload())
        retry = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload())
        conflict = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload(body="Jiný obsah."))

        assert retry.status_code == 200 and retry.json() == first.json()
        assert conflict.status_code == 409
        listed = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "b", "direction": "incoming"})
        assert len(listed.json()["messages"]) == 1


def test_recipient_acknowledges_exact_digest_once_and_sender_reads_receipt(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        message = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload()).json()["message"]
        receipt = {
            **SCOPE, "nodeId": "b", "messageId": message["id"], "digest": message["digest"],
            "disposition": "accepted", "note": "", "recipientLabel": "Agent B",
        }
        accepted = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt)
        retry = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt)
        wrong_target = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json={**receipt, "nodeId": "a"})
        wrong_digest = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json={**receipt, "digest": "0" * 64})
        conflict = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json={**receipt, "recipientLabel": "Jiný příjemce"})

        assert accepted.status_code == 200, accepted.text
        assert retry.json() == accepted.json()
        assert wrong_target.status_code == wrong_digest.status_code == conflict.status_code == 409
        outgoing = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "a", "direction": "outgoing"})
        assert outgoing.json()["messages"] == [accepted.json()["message"]]


def test_reply_is_limited_to_same_scope_and_pair(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        first = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload()).json()["message"]
        answer = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload(
            sourceNodeId="b", targetNodeId="a", kind="answer", body="Hotovo.", idempotencyKey="answer-001", senderLabel="Agent B", replyToMessageId=first["id"],
        ))
        foreign = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload(
            sourceNodeId="b", targetNodeId="sektor", kind="answer", body="Neplatný thread.", idempotencyKey="answer-002", senderLabel="Agent B", replyToMessageId=first["id"],
        ))

        assert answer.status_code == 200, answer.text
        assert answer.json()["message"]["replyToMessageId"] == first["id"]
        assert foreign.status_code == 409


def test_pagination_and_invalid_text_or_types_do_not_create_messages(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        for index in range(31):
            created = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload(
                body=f"Zpráva {index}", idempotencyKey=f"page-{index}",
            ))
            assert created.status_code == 200, created.text
        page = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "b", "direction": "incoming"})
        older = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "b", "direction": "incoming", "before": page.json()["nextBefore"]})
        nul = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload(body="x\u0000y", idempotencyKey="nul"))
        bad_kind = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload(kind=True, idempotencyKey="bad-kind"))

        assert len(page.json()["messages"]) == 30 and page.json()["hasMore"] is True
        assert len(older.json()["messages"]) == 1 and older.json()["hasMore"] is False
        assert nul.status_code == bad_kind.status_code == 409


def test_oversized_before_cursor_is_rejected_without_storage_error_or_write(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        response = client.get("/api/desktop-v3/agent-messages", params={
            **SCOPE, "nodeId": "b", "direction": "incoming", "before": "9223372036854775808",
        })

        assert response.status_code == 409
        assert client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "b", "direction": "incoming"}).json()["messages"] == []


def test_closed_card_is_read_only_for_new_messages(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        state = {
            "settings": [], "rules": [], "decisions": [], "tickets": [], "edges": {},
            "nodes": {"b": {"phase": "discover", "criteria": [], "steps": [],
                            "done": {"confirmed": True, "at": "2026-09-16T09:00:00+00:00", "by": "human", "note": "Hotovo."}}},
        }
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": 0, "state": state}).status_code == 200
        inbox = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "b", "direction": "incoming"})
        post = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload())

        assert inbox.status_code == 200 and inbox.json()["readOnly"] is True
        assert post.status_code == 409


def close_card(client, node_id="b"):
    state = {
        "settings": [], "rules": [], "decisions": [], "tickets": [], "edges": {},
        "nodes": {node_id: {"phase": "discover", "criteria": [], "steps": [],
                           "done": {"confirmed": True, "at": "2026-09-16T09:00:00+00:00", "by": "human", "note": "Hotovo."}}},
    }
    response = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": 0, "state": state})
    assert response.status_code == 200, response.text


def receipt_payload(message, **overrides):
    return {
        **SCOPE, "nodeId": "b", "messageId": message["id"], "digest": message["digest"],
        "disposition": "accepted", "note": "", "recipientLabel": "Agent B", **overrides,
    }


def test_closed_recipient_replays_the_same_immutable_receipt_without_a_new_write(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        message = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload()).json()["message"]
        accepted = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt_payload(message))
        close_card(client)

        replay = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt_payload(message))

        assert accepted.status_code == replay.status_code == 200
        assert replay.json() == accepted.json()


def test_closed_recipient_refuses_changed_receipt_replay_without_mutating_receipt(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        message = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload()).json()["message"]
        accepted = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt_payload(message))
        close_card(client)

        changed = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt_payload(message, note="Jiná neměnná poznámka."))
        listed = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "a", "direction": "outgoing"})

        assert changed.status_code == 409
        assert listed.json()["messages"] == [accepted.json()["message"]]


def test_closed_recipient_refuses_a_new_receipt_without_creating_one(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        message = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload()).json()["message"]
        close_card(client)

        refused = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt_payload(message))
        listed = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "a", "direction": "outgoing"})

        assert refused.status_code == 409
        assert listed.json()["messages"] == [{**message, "receipt": None}]


def test_receipt_post_insert_failure_rolls_back_its_new_receipt(tmp_path, monkeypatch):
    from backend.editor.agent_handoff.message_store import MessageStore

    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN, raise_server_exceptions=False) as client:
        seed_graph(client)
        message = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload()).json()["message"]
        original_message = MessageStore._message

        def fail_after_insert(store, row):
            if row["id"] == message["id"]:
                raise RuntimeError("isolated receipt readback failure")
            return original_message(store, row)

        monkeypatch.setattr(MessageStore, "_message", fail_after_insert)
        failed = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json=receipt_payload(message))
        monkeypatch.setattr(MessageStore, "_message", original_message)
        listed = client.get("/api/desktop-v3/agent-messages", params={**SCOPE, "nodeId": "a", "direction": "outgoing"})

        assert failed.status_code == 500
        assert listed.json()["messages"] == [{**message, "receipt": None}]


def git_app(tmp_path):
    import json
    import subprocess

    repo = tmp_path / "git"
    repo.mkdir()
    (repo / "opora-canvas.json").write_text(json.dumps(GRAPH), encoding="utf-8")
    for args in (("init", "-b", "main"), ("add", "."), ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    app = create_app(tmp_path / "data")
    app.state.service.register_repository("p", "P", repo, "https://github.com/example/p", "main")
    return app


def test_main_reads_empty_message_stream_without_draft_memory_and_refuses_post(tmp_path):
    scope = {"project": "p", "workspace": "main"}
    with TestClient(git_app(tmp_path), base_url=ORIGIN) as client:
        listed = client.get("/api/desktop-v3/agent-messages", params={**scope, "nodeId": "a", "direction": "incoming"})
        post = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json=message_payload(**scope))

        assert listed.status_code == 200 and listed.json()["messages"] == [] and listed.json()["readOnly"] is True
        assert post.status_code == 409
