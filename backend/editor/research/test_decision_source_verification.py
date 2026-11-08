"""Per-source verification cannot be overridden by an optimistic card status."""
import pytest

from backend.canvas.test_opora_changesets import service
from backend.editor.research import decisions, model, service as research
from backend.editor.research.test_decision_tasks import setup


def revise_sources(service, sources):
    item = research.detail(service, "draft", "draft", "rc_fact")["card"]
    operation = {"op": "card", "id": item["id"], "expectedRevision": item["revision"],
                 **{key: item[key] for key in model.CARD}, "sources": sources}
    research.apply(service, {"project": "draft", "workspace": "draft",
                            "key": "sources-" + str(item["revision"]), "operations": [operation]}, "human")


@pytest.mark.parametrize("status", ["false", "unreachable", "unverified", "conflict", "inference"])
def test_explicit_nonproof_source_cannot_support_review(service, status):
    payload = setup(service)
    source = research.detail(service, "draft", "draft", "rc_fact")["card"]["sources"][0]
    source["verification"] = {"status": status, "method": "Independent source check", "at": "2026-11-08"}
    revise_sources(service, [source])
    payload["evidence"][0]["revision"] = 2
    with pytest.raises(model.GateError, match="concrete verified or observed"):
        decisions.review(service, "draft", "draft", payload, "human")
    assert decisions.listing(service, "draft", "draft", "rc_decision")["reviews"] == []


@pytest.mark.parametrize("status", [None, "verified", "observed"])
def test_positive_or_legacy_proof_preserves_negative_sources(service, status):
    payload = setup(service)
    source = research.detail(service, "draft", "draft", "rc_fact")["card"]["sources"][0]
    if status:
        source["verification"] = {"status": status, "method": "Independent source check", "at": "2026-11-08"}
    negative = {**source, "ref": "https://example.org/contradiction", "quote": "",
                "verification": {"status": "unreachable", "method": "Source offline", "at": "2026-11-08"}}
    revise_sources(service, [source, negative])
    payload["evidence"][0]["revision"] = 2
    result = decisions.review(service, "draft", "draft", payload, "human")
    assert result["evidence"][0]["sources"] == [source, negative]
    assert research.detail(service, "draft", "draft", "rc_fact", 1)["card"]["sources"][0]["quote"] == source["quote"]


def test_positive_status_without_concrete_passage_is_not_proof(service):
    payload = setup(service)
    source = research.detail(service, "draft", "draft", "rc_fact")["card"]["sources"][0]
    source.update(quote=" ", verification={"status": "verified", "method": "Checked", "at": "2026-11-08"})
    revise_sources(service, [source])
    payload["evidence"][0]["revision"] = 2
    with pytest.raises(model.GateError, match="concrete verified or observed"):
        decisions.review(service, "draft", "draft", payload, "human")
