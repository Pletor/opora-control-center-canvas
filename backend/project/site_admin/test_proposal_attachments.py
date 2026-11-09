"""Native Site bundles: staging, reviewed CAS, exact replay and interrupted acceptance recovery."""
import base64
import json

import pytest

from backend.project.site_admin import proposal_apply, proposals, store
from backend.project.site_admin import proposal_attachments as files
from backend.project.site_admin.test_store import make_service
from backend.project.site_admin.tokens import SiteAdminInvalid

PNG = b"\x89PNG\r\n\x1a\nimage"
FONT = b"wOF2font"


def put(name="logo.png", data=PNG, kind="asset"):
    return {"kind": kind, "op": "put", "name": name, **({"group": "logos"} if kind == "asset" else {}),
            "data": base64.b64encode(data).decode()}


def bundle(service):
    return proposals.propose(service, "p1", {"title": "Reviewed bundle"}, attachments=[put(), put("body.woff2", FONT, "font")])


def test_bundle_is_staged_until_human_accept_and_retry_is_exact(tmp_path):
    service = make_service(tmp_path)
    proposed = bundle(service)
    assert proposed["status"] == "pending-attachments" and proposed["schemaVersion"] == 2  # old accept rejects unknown status
    assert files.read(service, "p1", "assets/logos/logo.png") is None
    assert store.read(service, "p1")["revision"] == 0
    assert proposed["attachments"][0]["sha256"] == files.digest(PNG)
    assert "data" not in str(proposed["attachments"])
    result = proposals.accept(service, "p1", proposed["id"], 0)
    assert files.read(service, "p1", "assets/logos/logo.png") == PNG
    assert files.read(service, "p1", "fonts/body.woff2") == FONT
    assert store.read(service, "p1")["revision"] == 1
    assert proposals.accept(service, "p1", proposed["id"], 0) == result
    assert len(list((store.site_dir(service, "p1") / "proposals").glob("apply-*.json"))) == 1
    assert proposals.pending(service, "p1") == []
    delete = proposals.propose(service, "p1", {}, attachments=[{"kind": "font", "op": "delete", "name": "body.woff2"}])
    proposals.accept(service, "p1", delete["id"], 1)
    assert files.read(service, "p1", "fonts/body.woff2") is None


@pytest.mark.parametrize("failure_path", ["fonts/body.woff2", "proposals/status", "proposals/complete"])
def test_restart_recovers_after_first_file_or_document_or_status_without_duplicate_revision(tmp_path, monkeypatch, failure_path):
    service = make_service(tmp_path)
    proposal = bundle(service)
    original = files.write
    def crash(service, project, path, raw):
        if path == failure_path or (failure_path == "proposals/status" and path == "proposals/" + proposal["id"] + ".json"):
            raise OSError("Injected interrupted file write")
        if failure_path == "proposals/complete" and path.startswith("proposals/apply-") and json.loads(raw)["state"] == "complete":
            raise OSError("Injected completion interruption")
        return original(service, project, path, raw)
    monkeypatch.setattr(files, "write", crash)
    with pytest.raises(proposal_apply.RecoveryNeeded) as failed:
        proposals.accept(service, "p1", proposal["id"], 0)
    assert failed.value.detail["code"] == "site_recovery_needed"
    assert files.read(service, "p1", "assets/logos/logo.png") == PNG
    assert proposals.pending(service, "p1")[0]["recoveryNeeded"]
    with pytest.raises(proposal_apply.RecoveryNeeded):
        store.put_font(service, "p1", "other.woff2", base64.b64encode(FONT).decode())
    with pytest.raises(proposal_apply.RecoveryNeeded):
        proposals.reject(service, "p1", proposal["id"])
    monkeypatch.setattr(files, "write", original)
    restarted = make_service(tmp_path)
    result = proposals.accept(restarted, "p1", proposal["id"], 0)
    assert result[0]["revision"] == 1
    assert proposals.accept(restarted, "p1", proposal["id"], 0) == result
    assert files.read(restarted, "p1", "fonts/body.woff2") == FONT


def test_external_mixed_conflict_is_reported_without_overwriting_or_finishing(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    proposal = bundle(service)
    original = files.write
    def crash(service, project, path, raw):
        if path == "fonts/body.woff2":
            raise OSError("stop")
        return original(service, project, path, raw)
    monkeypatch.setattr(files, "write", crash)
    with pytest.raises(proposal_apply.RecoveryNeeded):
        proposals.accept(service, "p1", proposal["id"], 0)
    monkeypatch.setattr(files, "write", original)
    original(service, "p1", "assets/logos/logo.png", PNG + b"external edit")
    with pytest.raises(proposal_apply.RecoveryNeeded) as failed:
        proposals.accept(make_service(tmp_path), "p1", proposal["id"], 0)
    assert failed.value.detail["targets"][0]["state"] == "conflict"
    assert files.read(service, "p1", "assets/logos/logo.png") == PNG + b"external edit"
    assert files.read(service, "p1", "fonts/body.woff2") is None
    assert store.read(service, "p1")["revision"] == 0


def test_stale_digest_reject_supersede_and_limits_do_not_write_live(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    first = bundle(service)
    proposals.reject(service, "p1", first["id"])
    with pytest.raises(store.SiteAdminConflict):
        proposals.accept(service, "p1", first["id"], 0)
    old = bundle(service)
    current = bundle(service)
    with pytest.raises(store.SiteAdminConflict):
        proposals.accept(service, "p1", old["id"], 0)
    files.write(service, "p1", "fonts/body.woff2", FONT + b"other")
    with pytest.raises(store.SiteAdminConflict, match="changed since review"):
        proposals.accept(service, "p1", current["id"], 0)
    assert files.read(service, "p1", "assets/logos/logo.png") is None
    assert proposal_apply.load(service, "p1", current["id"]) is None
    for attachment in (put("../escape.png"), put(data=b"<html>"), put("logo.svg", b'<svg onload="alert(1)"/>')):
        with pytest.raises(SiteAdminInvalid):
            proposals.propose(service, "p1", {}, attachments=[attachment])
    monkeypatch.setattr(files, "STAGED_BYTES", 1)
    with pytest.raises(SiteAdminInvalid, match="quota"):
        proposals.propose(service, "p1", {}, attachments=[put("new.png", PNG + b"new")])


def test_document_and_binary_pending_share_supersession_and_document_cas(tmp_path):
    service = make_service(tmp_path)
    legacy = proposals.propose(service, "p1", {"title": "Legacy"})
    binary = bundle(service)
    with pytest.raises(store.SiteAdminConflict, match="superseded"):
        proposals.accept(service, "p1", legacy["id"], 0)
    latest = proposals.propose(service, "p1", {"title": "Human document"})
    with pytest.raises(store.SiteAdminConflict, match="superseded"):
        proposals.accept(service, "p1", binary["id"], 0)
    assert [item["id"] for item in proposals.pending(service, "p1")] == [latest["id"]]
    proposed = bundle(service)
    store.write(service, "p1", 0, {**store.read(service, "p1"), "title": "External new revision"})
    with pytest.raises(store.SiteAdminConflict, match="base revision"):
        proposals.accept(service, "p1", proposed["id"], 1)
    assert files.read(service, "p1", "assets/logos/logo.png") is None


def test_symlink_target_is_not_followed(tmp_path):
    service = make_service(tmp_path)
    external = tmp_path / "external.png"
    external.write_bytes(PNG)
    target = store.site_dir(service, "p1") / "assets" / "logos" / "logo.png"
    target.parent.mkdir(parents=True)
    try:
        target.symlink_to(external)
    except OSError as error:
        pytest.skip(f"Host cannot create test symlink: {error}")
    with pytest.raises(SiteAdminInvalid, match="symbolic"):
        proposals.propose(service, "p1", {}, attachments=[put(data=PNG + b"new")])
    assert external.read_bytes() == PNG


def test_windows_junction_directory_is_not_followed(tmp_path):
    winapi = pytest.importorskip("_winapi")
    service = make_service(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "logo.png").write_bytes(PNG)
    parent = store.site_dir(service, "p1") / "assets"
    parent.mkdir(parents=True)
    winapi.CreateJunction(str(external), str(parent / "logos"))
    with pytest.raises(SiteAdminInvalid, match="junction"):
        proposals.propose(service, "p1", {}, attachments=[put(data=PNG + b"new")])
    assert (external / "logo.png").read_bytes() == PNG
