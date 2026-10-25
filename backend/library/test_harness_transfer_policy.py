"""Fail-closed parsing of reviewed, sanitized Harness transfer metadata."""
import json

import pytest

from backend.library import harness_transfer_policy as policy


def source(project="project-a", workspace="workspace-a", verification_id="verify_1"):
    return {"project": project, "workspace": workspace, "verificationId": verification_id}


def publication(identifier="pub-1", sources=None):
    return {"id": identifier, "problem": "problem/1", "candidate": {"id": "candidate-1", "digest": "a" * 64},
            "sources": [source()] if sources is None else sources}


def document(*publications):
    return {"schema": "harness.transfer-policy/1", "publications": list(publications)}


def test_disabled_invalid_and_oversized_configuration_fail_closed(monkeypatch):
    monkeypatch.delenv("OPORA_HARNESS_TRANSFER", raising=False)
    with pytest.raises(ValueError):
        policy.publication("pub-1")
    for raw in ('{', '{"schema":"harness.transfer-policy/1","schema":"harness.transfer-policy/1","publications":[]}'):
        monkeypatch.setenv("OPORA_HARNESS_TRANSFER", raw)
        with pytest.raises(ValueError):
            policy.publication("pub-1")
    with pytest.raises(ValueError, match="64 KiB"):
        policy._parse(json.dumps(document(publication())) + " " * (64 * 1024))


def test_valid_publication_returns_all_sanitized_metadata(monkeypatch):
    expected = publication(sources=[source(), source("project-b", "workspace-b", "verify_2")])
    monkeypatch.setenv("OPORA_HARNESS_TRANSFER", json.dumps(document(expected)))
    assert policy.publication("pub-1") == expected


def test_publication_and_source_count_bounds():
    with pytest.raises(ValueError):
        policy._parse(json.dumps(document()))
    with pytest.raises(ValueError):
        policy._parse(json.dumps(document(*(publication(f"pub-{i}") for i in range(17)))))
    with pytest.raises(ValueError):
        policy._parse(json.dumps(document(publication(sources=[]))))
    with pytest.raises(ValueError):
        policy._parse(json.dumps(document(publication(sources=[source(str(i), "workspace", f"verify_{i}") for i in range(9)]))))


def test_duplicate_ids_sources_and_invalid_neighbor_are_rejected(monkeypatch):
    first = publication()
    duplicate_source = publication("pub-2", [source(), source()])
    duplicate_id = publication()
    for entries in ([first, duplicate_id], [duplicate_source]):
        with pytest.raises(ValueError):
            policy._parse(json.dumps(document(*entries)))

    invalid_neighbor = publication("pub-2")
    invalid_neighbor["candidate"]["digest"] = "A" * 64
    monkeypatch.setenv("OPORA_HARNESS_TRANSFER", json.dumps(document(first, invalid_neighbor)))
    with pytest.raises(ValueError):
        policy.publication("pub-1")


@pytest.mark.parametrize("mutate", [
    lambda item: item.update(extra=True),
    lambda item: item.update(id="-bad"),
    lambda item: item.update(problem=""),
    lambda item: item.update(candidate={"id": "bad id", "digest": "a" * 64}),
    lambda item: item.update(candidate={"id": "candidate-1", "digest": "A" * 64}),
    lambda item: item.update(sources=[{"project": "bad id", "workspace": "workspace", "verificationId": "verify_1"}]),
    lambda item: item.update(sources=[{"project": "project", "workspace": "workspace", "verificationId": "bad id"}]),
])
def test_invalid_fields_are_rejected(mutate):
    item = publication()
    mutate(item)
    with pytest.raises(ValueError):
        policy._parse(json.dumps(document(item)))


def test_unknown_publication_is_rejected_after_full_validation(monkeypatch):
    monkeypatch.setenv("OPORA_HARNESS_TRANSFER", json.dumps(document(publication())))
    with pytest.raises(ValueError):
        policy.publication("missing")
