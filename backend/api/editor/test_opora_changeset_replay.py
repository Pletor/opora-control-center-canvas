"""Exact accepted-proposal replay preserves attribution, scope and policy history."""
import pytest

from backend.api.editor.test_opora_changeset_routes import (
    AGENT,
    BASE,
    baseline_payload,
    context,
    proposal_payload,
)
from backend.api.editor.test_opora_changeset_routes import (
    client as client,  # noqa: PLC0414
)
from backend.canvas.test_canvas_plan import HEADERS, SCOPE

REVIEW = BASE + "/proposal-reviews"


@pytest.mark.parametrize("mode", ["absent", "disabled", "active"])
def test_exact_spec_replay_keeps_one_native_write_and_original_receipt(client, monkeypatch, mode):
    baseline = client.post(BASE + "/baselines", headers=HEADERS, json=baseline_payload(client))
    assert baseline.status_code == 200, baseline.text
    item = client.post(BASE + "/changesets", headers=AGENT, json=proposal_payload(client)).json()
    policy_head = None
    if mode != "absent":
        configured = client.post(REVIEW + "/policy", headers=HEADERS, json={**SCOPE,
            "expectedPolicyHead": None, "enabled": mode == "active",
            "rules": {"requireAcknowledgementFrom": "none", "blockOpenFindings": True}})
        assert configured.status_code == 200, configured.text
        policy_head = configured.json()["id"]
    specs = client.app.state.service.specs
    save = specs.save_in_transaction
    writes = []

    def counted(*args, **kwargs):
        writes.append(args)
        return save(*args, **kwargs)

    monkeypatch.setattr(specs, "save_in_transaction", counted)
    endpoint = BASE + "/changesets/" + item["id"] + "/accept"
    payload = {**SCOPE, "expectedAcceptedHead": baseline.json()["id"]}
    accepted = client.post(endpoint, headers=HEADERS, json=payload)
    assert accepted.status_code == 200, accepted.text
    assert len(writes) == 1
    revision = accepted.json()["id"]
    receipt_path = REVIEW + "/receipts/" + revision
    receipt = client.get(receipt_path, params=SCOPE, headers=HEADERS).json()["receipt"]
    assert (receipt is not None) == (mode == "active")
    before = context(client)["documents"]
    db = client.app.state.service.db_for(SCOPE["project"])
    revisions = db.execute("SELECT id FROM opora_spec_revisions ORDER BY id").fetchall()
    # Historical replay must not rerun today's policy or issue a replacement receipt.
    changed = client.post(REVIEW + "/policy", headers=HEADERS, json={**SCOPE,
        "expectedPolicyHead": policy_head, "enabled": True,
        "rules": {"requireAcknowledgementFrom": "standard", "blockOpenFindings": True}})
    assert changed.status_code == 200, changed.text
    for _ in range(2):
        replay = client.post(endpoint, headers=HEADERS, json=payload)
        assert replay.status_code == 200 and replay.json() == accepted.json()
    assert len(writes) == 1
    assert db.execute("SELECT id FROM opora_spec_revisions ORDER BY id").fetchall() == revisions
    assert context(client)["documents"] == before
    assert context(client)["acceptedHead"] == revision
    assert client.get(receipt_path, params=SCOPE, headers=HEADERS).json()["receipt"] == receipt
    assert client.post(endpoint, headers=AGENT, json=payload).status_code == 403
    assert client.post(endpoint, headers=HEADERS,
                       json={**payload, "workspace": "other"}).status_code == 409
    client.cookies.clear()
    assert client.post(endpoint, headers=HEADERS, json=payload).status_code == 428
