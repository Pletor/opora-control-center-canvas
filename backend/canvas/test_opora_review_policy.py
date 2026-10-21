"""Policy authority uses scoped server identities, real human authors and atomic CAS."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from backend.canvas.opora_review_evidence import OporaReviewEvidence
from backend.canvas.opora_review_policy import OporaReviewPolicy
from backend.canvas.test_opora_review_fixtures import AGENT, HUMAN, Reader, configure
from backend.canvas.test_opora_review_fixtures import evidence_project as evidence_fixture
from database.repositories.opora_review_policy import Policies
from database.repositories.test_opora_review_policy import RULES
from database.schema.opora_review_policy_schema import SCHEMA

__all__ = ["evidence_fixture"]


@pytest.fixture
def policy_project(evidence_project):
    service, payload = evidence_project
    service.db_for(payload["project"]).executescript(SCHEMA)
    reader = Reader(payload)
    reader.result["pr"].update(baseSha="f" * 40, state="open", draft=False)
    reader.result["repository"]["fullName"] = "Owner/Repo"
    evidence = OporaReviewEvidence(service, reader).observe(payload, AGENT)["snapshot"]
    scope = {key: payload[key] for key in ("project", "workspace")}
    return service, scope, {**scope, "expectedPolicyHead": None, "identityEvidenceId": evidence["id"], "rules": deepcopy(RULES)}


def test_configure_canonical_pin_replay_disable_and_history(policy_project):
    service, scope, payload = policy_project
    domain = OporaReviewPolicy(service)
    before = domain.context(**scope, actor="human")
    assert before["canConfigure"] and before["policy"] is None
    assert not domain.context(**scope, actor="agent")["canConfigure"]
    first = domain.configure(payload, HUMAN)
    assert first["policy"]["repository"] == {"id": 10, "fullName": "owner/repo", "baseBranch": "main"}
    assert domain.configure(payload, HUMAN) == first
    assert domain.context(**scope, actor="human")["acceptedHead"] == before["acceptedHead"]
    disabled = domain.disable({**scope, "expectedPolicyHead": first["policyHead"]}, HUMAN)
    assert disabled["policy"]["enabled"] is False
    assert disabled["policy"]["rules"] == first["policy"]["rules"]
    assert domain.history(**scope)["items"] == [disabled["policy"], first["policy"]]
    with pytest.raises(ValueError, match="head changed"):
        domain.configure(payload, HUMAN)


@pytest.mark.parametrize("extra", [{"repository": {"id": 99}}, {"by": HUMAN}, {"enabled": True}, {"policyVerified": True}])
def test_client_cannot_supply_authority_fields(policy_project, extra):
    service, _, payload = policy_project
    with pytest.raises(ValueError):
        OporaReviewPolicy(service).configure({**payload, **extra}, HUMAN)


def test_agent_cannot_configure_or_disable(policy_project):
    service, scope, payload = policy_project
    domain = OporaReviewPolicy(service)
    with pytest.raises(ValueError):
        domain.configure(payload, AGENT)
    first = domain.configure(payload, HUMAN)
    with pytest.raises(ValueError):
        domain.disable({**scope, "expectedPolicyHead": first["policyHead"]}, AGENT)


def test_configuration_changed_foreign_evidence_and_readonly_reject(policy_project, monkeypatch):
    service, scope, payload = policy_project
    domain = OporaReviewPolicy(service)
    configure(service, scope["project"], branch="other")
    with pytest.raises(ValueError, match="current repository"):
        domain.configure(payload, HUMAN)
    configure(service, scope["project"])
    with pytest.raises(ValueError):
        domain.configure({**payload, "workspace": "main"}, HUMAN)
    original = service.view
    monkeypatch.setattr(service, "view", lambda *args: {**original(*args), "readOnly": True})
    with pytest.raises(ValueError):
        domain.configure(payload, HUMAN)
    assert domain.repository(**scope).head() is None


def test_failure_after_activation_rolls_back_entire_policy(policy_project, monkeypatch):
    service, scope, payload = policy_project
    domain = OporaReviewPolicy(service)
    original = Policies.activate
    def fail(repo, *args):
        original(repo, *args)
        raise RuntimeError("injected policy transaction failure")
    monkeypatch.setattr(Policies, "activate", fail)
    with pytest.raises(RuntimeError, match="injected"):
        domain.configure(payload, HUMAN)
    assert domain.history(**scope) == {"policyHead": None, "items": []}


def test_stale_different_rules_cannot_overwrite_new_policy(policy_project):
    service, scope, payload = policy_project
    domain = OporaReviewPolicy(service)
    first = domain.configure(payload, HUMAN)
    with pytest.raises(ValueError, match="head changed"):
        domain.configure({**payload, "rules": {**RULES, "maxObservationAgeSeconds": 120}}, HUMAN)
    assert domain.repository(**scope).head() == first["policyHead"]


def test_concurrent_different_policy_activations_have_one_winner(policy_project):
    service, scope, payload = policy_project
    domain = OporaReviewPolicy(service)
    def activate(age):
        try:
            return domain.configure({**payload, "rules": {**RULES, "maxObservationAgeSeconds": age}}, HUMAN)
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(activate, (60, 120)))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1 and domain.repository(**scope).head() == winners[0]["policyHead"]
    assert len(domain.history(**scope)["items"]) == 1
