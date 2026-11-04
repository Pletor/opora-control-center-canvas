"""Návrhy srdce: rozdíl, jeden čekající, přijetí nad revizí (zastaralý = 409), zamítnutí."""
import pytest

from backend.project.site_admin import proposals, store
from backend.project.site_admin.fixture import ember
from backend.project.site_admin.store import SiteAdminConflict, SiteFileMissing
from backend.project.site_admin.test_store import make_service
from backend.project.site_admin.tokens import SiteAdminInvalid

INK = {"design": {"tokens": {**ember()["design"]["tokens"], "color": {
    "themes": [{"id": "light", "name": "Light"}], "tokens": [{"name": "ink", "value": "#111111"}]}}}}


def test_propose_keeps_the_document_and_reports_a_leaf_diff(tmp_path):
    service = make_service(tmp_path)
    store.write(service, "p1", 0, ember())
    found = proposals.propose(service, "p1", {"title": "Ember 2", "settings": {"seo": {"description": "Káva."}}},
                              note="kratší titulek")
    assert found["status"] == "pending" and found["baseRevision"] == 1 and found["by"] == "heart"
    paths = {item["path"]: (item["before"], item["after"]) for item in found["diff"]}
    assert paths["title"] == ("Ember", "Ember 2") and paths["settings.seo.description"] == ("", "Káva.")
    assert paths["settings.seo.titleTemplate"] == ("%s · Ember", "%s")  # část settings nahradí celá
    assert store.read(service, "p1")["revision"] == 1 and store.read(service, "p1")["title"] == "Ember"
    assert [item["id"] for item in proposals.pending(service, "p1")] == [found["id"]]
    with pytest.raises(SiteAdminInvalid, match="nic nemění"):
        proposals.propose(service, "p1", {"title": "Ember"})
    with pytest.raises(SiteAdminInvalid, match="changes"):
        proposals.propose(service, "p1", {"revision": 5})
    with pytest.raises(SiteAdminInvalid, match="tajemství"):
        proposals.propose(service, "p1", {"settings": {"email": {"password": "x"}}})


def test_newer_proposal_supersedes_and_accept_writes_over_the_base_revision(tmp_path):
    service = make_service(tmp_path)
    store.write(service, "p1", 0, ember())
    first = proposals.propose(service, "p1", {"title": "A"})
    second = proposals.propose(service, "p1", INK)
    assert [item["id"] for item in proposals.pending(service, "p1")] == [second["id"]]
    with pytest.raises(SiteAdminConflict, match="superseded"):
        proposals.accept(service, "p1", first["id"], 1)
    saved, _, accepted = proposals.accept(service, "p1", second["id"], 1)
    assert saved["revision"] == 2 and accepted["status"] == "accepted"
    assert [token["name"] for token in saved["design"]["tokens"]["color"]["tokens"]] == ["ink"]
    assert saved["lastChange"]["note"] == f"Přijatý návrh heart {second['id']}" and proposals.pending(service, "p1") == []


def test_stale_proposal_is_409_and_reject_only_changes_the_state(tmp_path):
    service = make_service(tmp_path)
    store.write(service, "p1", 0, ember())
    found = proposals.propose(service, "p1", {"title": "B"})
    store.write(service, "p1", 1, {**ember(), "title": "Člověk"})
    with pytest.raises(SiteAdminConflict, match="navrhnout znovu"):
        proposals.accept(service, "p1", found["id"], 2)
    assert proposals.reject(service, "p1", found["id"])["status"] == "rejected"
    assert store.read(service, "p1")["title"] == "Člověk" and proposals.pending(service, "p1") == []
    with pytest.raises(SiteFileMissing):
        proposals.reject(service, "p1", "../design-system")
