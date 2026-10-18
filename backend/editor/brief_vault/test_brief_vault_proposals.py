"""Návrhy bran a jejich zamítnutí přes API (docs/schranka-neurony.md §9 bod 9, §11): `op: reject-proposal` je
append-only bez nové revize, zamítnutý návrh se pro potvrzení nikdy nepoužije, `/next` pak čeká na návrh, autor
smí vlastní návrh stáhnout; detail fragmentu nese `proposals` se stavem pending | rejected | used; odmítnutý plán
je 409 se strukturovaným výčtem fragmentů."""
import pytest

from backend.editor.brief_vault.test_brief_vault_discipline import HEADERS, SCOPE, post
from backend.editor.brief_vault.test_brief_vault_gates import (
    SYNTH,
    WEIGHED,
    gate,
    root,
    stored,
    vault_client,
    walk,
)

OTHER = {**HEADERS, "X-Opora-Actor": "agent; name=hermes"}


@pytest.fixture
def client(tmp_path):
    with vault_client(tmp_path) as client:
        yield client


def propose(client, fragment, name, payload, headers=OTHER, expect=200):
    return post(client, expect=expect, headers=headers, op="propose", fragmentId=fragment["id"],
                expectedRevision=fragment["revision"], gate=name, payload=payload, note=f"návrh {name}")


def reject(client, fragment, name, expect=200, headers=HEADERS, **extra):
    body = {"op": "reject-proposal", "fragmentId": fragment["id"], "expectedRevision": fragment["revision"], "gate": name,
            "note": "Riziko je podceněné.", **extra}
    return post(client, expect=expect, headers=headers, **body)


def proposals(client, fragment_id):
    response = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment_id})
    assert response.status_code == 200, response.text
    return response.json()["proposals"]


def next_of(client):
    return client.get("/api/brief-vault/next", params=SCOPE).json()


def test_reject_is_append_only_and_blocks_confirmation(client):
    fragment = walk(client, root(client), "scoped")
    first = propose(client, fragment, "weighed", WEIGHED)["proposal"]
    assert next_of(client)["needs"] == "confirm"
    reject(client, {**fragment, "revision": 1}, "weighed", expect=409)  # CAS: stará revize
    done = reject(client, fragment, "weighed")
    assert done["ok"] is True and done["op"] == "reject-proposal"
    rejected = done["rejected"]
    assert rejected["id"] == first["id"] and rejected["status"] == "rejected" and rejected["payload"] == WEIGHED
    assert rejected["rejection"]["note"] == "Riziko je podceněné." and rejected["rejection"]["actor"] == "human"
    assert stored(client, fragment["id"])[-1][0] == fragment["revision"]  # revize nepřibývá
    found = next_of(client)
    assert found["gate"] == "weighed" and found["needs"] == "proposal" and "proposal" not in found
    assert "chybí návrh" in gate(client, fragment, "weighed", expect=400)["error"]  # zamítnutý se nepoužije
    reject(client, fragment, "weighed", expect=409)  # není čekající návrh (starší se neoživí)
    db = client.app_state.service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM brief_gate_proposal_rejections").fetchone()[0] == 1
    again = propose(client, fragment, "weighed", WEIGHED)["proposal"]
    assert next_of(client)["proposal"]["id"] == again["id"]
    assert gate(client, fragment, "weighed")["gateStep"] == 2


def test_author_may_withdraw_and_invalid_rejections(client):
    fragment = walk(client, root(client), "scoped")
    reject(client, fragment, "scoped", expect=400)  # brána bez payloadu návrh nemá
    reject(client, fragment, "nope", expect=400)
    reject(client, fragment, "weighed", expect=409)  # žádný návrh
    propose(client, fragment, "weighed", WEIGHED)
    post(client, expect=409, headers=OTHER, op="reject-proposal", fragmentId=fragment["id"],
         expectedRevision=fragment["revision"], gate="weighed", note="")  # note povinná
    withdrawn = reject(client, fragment, "weighed", headers=OTHER)["rejected"]
    assert withdrawn["by"] == "hermes" and withdrawn["rejection"]["by"] == "hermes"
    propose(client, fragment, "weighed", WEIGHED)
    on = gate(client, fragment, "weighed")["fragment"]
    reject(client, on, "weighed", expect=409)  # zapnutá brána: nesouhlas = vypnout


def test_detail_proposals_pending_rejected_used(client):
    fragment = walk(client, root(client), "scoped")
    assert proposals(client, fragment["id"]) == {}
    propose(client, fragment, "weighed", WEIGHED)
    found = proposals(client, fragment["id"])
    assert set(found) == {"weighed"} and found["weighed"]["status"] == "pending" and found["weighed"]["rejection"] is None
    assert found["weighed"]["by"] == "hermes" and found["weighed"]["actor"] == "agent"
    fragment = gate(client, fragment, "weighed")["fragment"]
    assert proposals(client, fragment["id"])["weighed"]["status"] == "used"
    propose(client, fragment, "synthesized", SYNTH)
    reject(client, fragment, "synthesized")
    found = proposals(client, fragment["id"])["synthesized"]
    assert found["status"] == "rejected" and found["rejection"]["actor"] == "human"
    fragment = gate(client, fragment, "weighed", value=False)["fragment"]
    assert proposals(client, fragment["id"])["weighed"]["status"] == "used"  # použitý zůstává použitý


def test_gate_off_after_proposal_reads_as_rejected(client):
    fragment = walk(client, root(client), "weighed")
    propose(client, fragment, "synthesized", SYNTH)
    fragment = gate(client, fragment, "weighed", value=False)["fragment"]
    found = proposals(client, fragment["id"])["synthesized"]
    assert found["status"] == "rejected" and found["rejection"]["gateOff"] is True


def test_decided_other_marks_proposal_used(client):
    fragment = walk(client, root(client), "synthesized")
    propose(client, fragment, "decided", {"verdict": "other", "reason": "Menší krok."})
    gate(client, fragment, "decided")
    assert proposals(client, fragment["id"])["decided"]["status"] == "used"


def test_plan_409_lists_fragments_structurally(client):
    fragment = post(client, op="create", scopeNodeId="s1", discipline="be", title="Bez mikrokroku", text="b")["fragment"]
    response = client.post("/api/brief-vault/plan", headers=HEADERS, json={**SCOPE, "fragmentIds": [fragment["id"]]})
    assert response.status_code == 409
    body = response.json()
    assert "chybí platná brána synthesized" in body["error"]
    assert body["fragments"] == [{"id": fragment["id"], "title": "Bez mikrokroku", "reason": "no-synthesized"}]
