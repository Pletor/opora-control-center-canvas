"""Zrcadlo u bran cyklu (docs/zrcadlo.md, schranka-neurony.md §9 bod 11): predict po `synthesized`, observe po `verified`
jen s předpovědí stejného cyklu, idempotence podle ID události, výpadek nezablokuje bránu a nezmění její výsledek,
projekt mimo `[mirror] projects` nic nevolá, `GET /api/brief-vault/mirror` agreguje po disciplínách."""
import json

import pytest

from backend.editor.brief_vault import brief_vault_mirror
from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.brief_vault.test_brief_vault_gates import (
    PAYLOADS,
    gate,
    root,
    vault_client,
    walk,
)
from backend.editor.node.test_removals import SCOPE
from backend.integrations.mirror_client import MirrorClient
from backend.integrations.test_mirror_client import OBSERVATION, PREDICTION, fake_service

ACTUAL = {"tests": "pass", "criticRounds": 1, "unexpected": False}


class FakeMirror:
    """Falešný klient: zaznamená volání, vrací připravené odpovědi (None = výpadek)."""

    def __init__(self, prediction=PREDICTION, observation=OBSERVATION, error=None):
        self.prediction, self.observation, self.error, self.calls = prediction, observation, error, []

    def _answer(self, name, kwargs, value):
        self.calls.append((name, kwargs))
        if self.error:
            raise self.error
        return value

    def predict(self, **kwargs):
        return self._answer("predict", kwargs, self.prediction)

    def observe(self, **kwargs):
        return self._answer("observe", kwargs, self.observation)

    def health(self):
        return {"ok": True, "model": "fake", "events": len(self.calls)}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("OPORA_MIRROR_URL", raising=False)
    monkeypatch.delenv("OPORA_MIRROR_PROJECTS", raising=False)
    with vault_client(tmp_path) as client:
        yield client


def vault_with(client, mirror):
    return BriefVault(client.app_state.service, mirror=lambda project: mirror if project == "draft" else None)


def gate_in(vault, fragment, name, payload=None):
    body = {**SCOPE, "op": "gate", "fragmentId": fragment["id"], "expectedRevision": fragment["revision"], "gate": name,
            "value": True, "note": f"{name}: true"}
    if payload is not None:
        body["payload"] = payload
    return vault.apply(body, actor="agent", agent="discipline-1")


def events(client):
    db = client.app_state.service.db_for("draft")
    return [dict(row) for row in db.execute("SELECT * FROM brief_mirror_events ORDER BY created_at")]


def synthesized(client, vault):
    fragment = walk(client, root(client), "weighed")
    return gate_in(vault, fragment, "synthesized", PAYLOADS["synthesized"])


def placed_after(client, fragment):
    for name in ("decided", "planned", "placed"):
        fragment = gate(client, fragment, name, **({"payload": PAYLOADS[name]} if name in PAYLOADS else {}))["fragment"]
    return fragment


def test_predict_after_synthesized_once_per_cycle(client):
    fake = FakeMirror()
    vault = vault_with(client, fake)
    done = synthesized(client, vault)
    assert done["ok"] and done["gates"]["synthesized"] is True
    assert [name for name, _ in fake.calls] == ["predict"]
    sent = fake.calls[0][1]
    assert sent["discipline"] == "be" and sent["title"] == "Import" and sent["text"] == "Importuj CSV."
    assert sent["microstep"] == "SCHEMA: Tabulka existuje a test projde."
    [event] = events(client)
    assert event["kind"] == "predict" and event["cycle"] == done["fragment"]["revision"] == event["revision"]
    assert event["event_id"] == brief_vault_mirror.event_id("draft", "draft", done["fragment"]["id"], event["cycle"], "predict")
    assert json.loads(event["result"])["predictionId"] == "p1"
    assert "text" not in json.loads(event["request"])
    # Opakování téhož cyklu nevolá službu ani nepíše druhou událost.
    payload = {**SCOPE, "op": "gate", "gate": "synthesized", "value": True}
    assert brief_vault_mirror.after_gate(client.app_state.service, payload, done, lambda project: fake) is None
    assert len(fake.calls) == 1 and len(events(client)) == 1


def test_observe_after_verified_with_prediction_of_same_cycle(client):
    fake = FakeMirror()
    vault = vault_with(client, fake)
    fragment = placed_after(client, synthesized(client, vault)["fragment"])
    done = gate_in(vault, fragment, "verified", {"actual": ACTUAL})
    assert done["gates"]["verified"] is True and done["gates"]["predictionError"] == 0.0
    assert fake.calls[-1] == ("observe", {"prediction_id": "p1", "actual": ACTUAL})
    predict, observe = events(client)
    assert observe["kind"] == "observe" and observe["cycle"] == predict["cycle"]
    assert json.loads(observe["result"]) == OBSERVATION
    # Do revize fragmentu se nic dodatečně nezapisuje.
    stored = client.app_state.service.db_for("draft").execute(
        "SELECT gates FROM brief_fragment_revisions WHERE fragment_id=? ORDER BY revision DESC", (fragment["id"],)).fetchone()
    assert "predictionId" not in stored["gates"] and "hormones" not in stored["gates"]


def test_observe_without_prediction_of_this_cycle_is_skipped(client):
    fake = FakeMirror()
    vault = vault_with(client, fake)
    fragment = walk(client, root(client), "placed")  # synthesized bez Zrcadla: žádná předpověď
    done = gate_in(vault, fragment, "verified", {"actual": ACTUAL})
    assert done["gates"]["verified"] is True
    assert fake.calls == [] and events(client) == []


@pytest.mark.parametrize("mirror", [FakeMirror(error=RuntimeError("výpadek")), FakeMirror(prediction=None),
                                    MirrorClient("http://127.0.0.1:1", timeout=0.3)])
def test_outage_never_blocks_gate_and_result_is_the_same(client, mirror):
    plain = vault_with(client, None)
    first = walk(client, root(client), "weighed")
    expected = gate_in(plain, first, "synthesized", PAYLOADS["synthesized"])
    second = walk(client, root(client), "weighed")
    found = gate_in(vault_with(client, mirror), second, "synthesized", PAYLOADS["synthesized"])
    strip = ("id", "at")
    assert {k: v for k, v in found["fragment"].items() if k not in strip} == \
        {k: v for k, v in expected["fragment"].items() if k not in strip}
    assert {k: v for k, v in found.items() if k != "fragment"} == {k: v for k, v in expected.items() if k != "fragment"}
    assert events(client) == []


def test_client_factory_failure_does_not_change_gate(client):
    def broken(project):
        raise RuntimeError("konfigurace")

    done = synthesized(client, BriefVault(client.app_state.service, mirror=broken))
    assert done["ok"] and done["gateStep"] == 3 and events(client) == []


def test_project_outside_mirror_projects_makes_no_call(client, monkeypatch):
    routes = {("POST", "/predict"): (200, PREDICTION, {})}
    with fake_service(routes) as (url, received):
        monkeypatch.setenv("OPORA_MIRROR_URL", url)
        monkeypatch.setenv("OPORA_MIRROR_PROJECTS", "jiny-projekt")
        walk(client, root(client), "synthesized")  # přes API, výchozí klient z prostředí
        assert received == [] and events(client) == []
        monkeypatch.setenv("OPORA_MIRROR_PROJECTS", "jiny-projekt,draft")
        walk(client, root(client), "synthesized")
        assert [item["path"] for item in received] == ["/predict"]
        assert [event["kind"] for event in events(client)] == ["predict"]


def test_mirror_overview_aggregates_by_discipline(client):
    fake = FakeMirror()
    vault = vault_with(client, fake)
    fragment = placed_after(client, synthesized(client, vault)["fragment"])
    gate_in(vault, fragment, "verified", {"actual": ACTUAL})
    bad = FakeMirror(prediction={**PREDICTION, "predictionId": "p2"}, observation={**OBSERVATION, "predictionError": 0.8})
    other = vault_with(client, bad)
    second = walk(client, root(client, discipline="ux"), "weighed")
    second = placed_after(client, gate_in(other, second, "synthesized", PAYLOADS["synthesized"])["fragment"])
    gate_in(other, second, "verified", {"actual": ACTUAL})
    walk_only = walk(client, root(client), "weighed")
    gate_in(vault, walk_only, "synthesized", PAYLOADS["synthesized"])

    off = client.get("/api/brief-vault/mirror", params=SCOPE)
    assert off.status_code == 200, off.text
    body = off.json()
    assert body["enabled"] is False and "health" not in body
    assert body["byDiscipline"] == {
        "be": {"predictions": 2, "observed": 1, "accuracy": 1.0, "lastError": 0.15},
        "ux": {"predictions": 1, "observed": 1, "accuracy": 0.0, "lastError": 0.8}}
    assert set(body["hormones"]) == {"dopamin", "serotonin", "kortizol", "oxytocin"}

    on = vault.mirror_overview("draft", "draft")
    assert on["enabled"] is True and on["health"]["model"] == "fake"
    assert vault.mirror_overview("draft", "jiny")["byDiscipline"] == {}
