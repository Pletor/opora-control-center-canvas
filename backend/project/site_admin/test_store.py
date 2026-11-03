import base64
import threading
from types import SimpleNamespace

import pytest

from backend.canvas.canvas_service import ProjectNotFound
from backend.canvas.project_folder import ProjectFolder
from backend.project.site_admin import store
from backend.project.site_admin.fixture import ember
from backend.project.site_admin.store import SiteAdminConflict, SiteFileMissing
from backend.project.site_admin.tokens import SiteAdminInvalid

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
SVG = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect/></svg>'
WOFF2 = b"wOF2" + b"\x00" * 16


def b64(data):
    return base64.b64encode(data).decode()


def make_service(root):
    lock = threading.RLock()
    return SimpleNamespace(project_exists=lambda pid: pid == "p1", folder=lambda pid: ProjectFolder(root, pid),
                           lock_for=lambda pid: lock)


def test_read_is_empty_until_written_and_write_bumps_revision(tmp_path):
    service = make_service(tmp_path)
    assert store.read(service, "p1")["revision"] == 0
    saved, notes = store.write(service, "p1", 0, ember(), note="první verze")
    assert saved["revision"] == 1 and notes == []
    assert saved["lastChange"]["via"] == "page" and saved["lastChange"]["note"] == "první verze"
    path = tmp_path / "projects" / "p1" / "site" / "design-system.json"
    assert path.is_file()
    assert store.read(service, "p1") == saved
    with pytest.raises(SiteAdminConflict, match="revize 1"):
        store.write(service, "p1", 0, ember())
    assert store.write(service, "p1", 1, {**ember(), "revision": 99})[0]["revision"] == 2  # revize z těla se ignoruje


def test_unknown_project_and_corrupt_file(tmp_path):
    service = make_service(tmp_path)
    with pytest.raises(ProjectNotFound):
        store.read(service, "nikdo")
    path = tmp_path / "projects" / "p1" / "site" / "design-system.json"
    path.parent.mkdir(parents=True)
    path.write_text("{nope", "utf-8")
    assert store.read(service, "p1")["revision"] == 0


def test_assets_are_sniffed_limited_and_stored_by_group(tmp_path):
    service = make_service(tmp_path)
    record = store.put_asset(service, "p1", "Logos", "mark.svg", b64(SVG))
    assert record == {"name": "mark.svg", "blob": "assets/Logos/mark.svg", "size": len(SVG), "type": "image/svg+xml"}
    assert store.put_asset(service, "p1", "Logos", "hero.png", "data:image/png;base64," + b64(PNG))["size"] == len(PNG)
    assert (tmp_path / "projects" / "p1" / "site" / "assets" / "Logos" / "mark.svg").read_bytes() == SVG
    assert store.asset_path(service, "p1", "Logos", "hero.png")[1] == "image/png"
    for group, name, data, message in (
            ("Logos", "fake.png", SVG, "neodpovídá"),
            ("Logos", "x.svg", SVG.replace(b"<rect/>", b'<rect onload="alert(1)"/>'), "skripty"),
            ("Logos", "x.exe", PNG, "neodpovídá"),
            ("..", "x.png", PNG, "Skupina"),
            ("Logos", "../x.png", PNG, "Soubor"),
            ("Logos", "con.png", PNG, "Soubor"),
            ("Logos", "big.svg", SVG + b" " * store.SVG_LIMIT, "limit")):
        with pytest.raises(SiteAdminInvalid, match=message):
            store.put_asset(service, "p1", group, name, b64(data))
    with pytest.raises(SiteAdminInvalid, match="base64"):
        store.put_asset(service, "p1", "Logos", "a.png", "!!")
    store.delete_asset(service, "p1", "Logos", "mark.svg")
    store.delete_asset(service, "p1", "Logos", "hero.png")
    assert not (tmp_path / "projects" / "p1" / "site" / "assets" / "Logos").exists()
    with pytest.raises(SiteFileMissing):
        store.asset_path(service, "p1", "Logos", "hero.png")


def test_fonts_go_to_their_own_folder(tmp_path):
    service = make_service(tmp_path)
    assert store.put_font(service, "p1", "inter.woff2", b64(WOFF2)) == {"file": "fonts/inter.woff2", "size": 20,
                                                                        "type": "font/woff2"}
    assert store.font_path(service, "p1", "inter.woff2")[0] == tmp_path / "projects" / "p1" / "site" / "fonts" / "inter.woff2"
    with pytest.raises(SiteAdminInvalid):
        store.put_font(service, "p1", "inter.ttf", b64(WOFF2))
    store.delete_font(service, "p1", "inter.woff2")
    with pytest.raises(SiteFileMissing):
        store.delete_font(service, "p1", "inter.woff2")
