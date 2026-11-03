"""Správa webu přes skutečnou aplikaci: čte kdokoli, zapisuje jen člověk, revize a soubory."""
import base64

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.project.site_admin.fixture import ember

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
URL = "/api/site-admin"
DRAFT = {"project": "draft"}
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect/></svg>'
WOFF2 = b"wOF2" + b"\x00" * 16


def test_document_round_trip_with_revision_and_human_only(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        first = client.get(URL, params=DRAFT, headers=AGENT).json()
        assert first["revision"] == 0 and first["document"]["design"]["tokens"]["color"]["tokens"] == []
        body = {"expectedRevision": 0, "document": ember()}
        assert client.put(URL, params=DRAFT, headers=AGENT, json=body).status_code == 403
        saved = client.put(URL, params=DRAFT, headers=HEADERS, json={**body, "note": "první"})
        assert saved.status_code == 200, saved.text
        assert saved.json()["revision"] == 1 and saved.json()["notes"] == []
        assert client.get(URL, params=DRAFT).json()["document"] == saved.json()["document"]
        stale = client.put(URL, params=DRAFT, headers=HEADERS, json=body)
        assert stale.status_code == 409 and "revize 1" in stale.json()["detail"]
        dropped = ember()
        dropped["design"]["tokens"]["color"]["tokens"].append({"name": "bad", "value": "red"})
        again = client.put(URL, params=DRAFT, headers=HEADERS, json={"expectedRevision": 1, "document": dropped})
        assert again.json()["revision"] == 2 and "bad" in again.json()["notes"][0]
        secret = ember()
        secret["settings"]["email"]["password"] = "hunter2"
        refused = client.put(URL, params=DRAFT, headers=HEADERS, json={"expectedRevision": 2, "document": secret})
        assert refused.status_code == 422 and "tajemství" in refused.json()["detail"]
        assert client.put(URL, params=DRAFT, headers=HEADERS, json={"document": {}}).status_code == 422
        assert client.get(URL, params={"project": "neni"}).status_code == 404


def test_generated_files(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        client.put(URL, params=DRAFT, headers=HEADERS, json={"expectedRevision": 0, "document": ember()})
        css = client.get(f"{URL}/tokens.css", params=DRAFT)
        assert css.headers["content-type"].startswith("text/css") and "--link: var(--ember);" in css.text
        assert client.get(f"{URL}/tokens.json", params=DRAFT).json()["version"] == 1
        readme = client.get(f"{URL}/README.md", params=DRAFT)
        assert readme.headers["content-type"].startswith("text/markdown") and "## Jak systém použít" in readme.text
        components = client.get(f"{URL}/components.css", params=DRAFT)
        assert components.headers["content-type"].startswith("text/css") and ".ds-btn--primary {" in components.text
        assert "@keyframes ds-btn-primary-glow" in components.text


def test_appearance_view_survives_a_stale_save_and_bad_css_is_422_with_a_line(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        document = ember()
        document["settings"]["appearance"] = {"colors": {"linkHover": "#004488"}, "layout": {"contentSize": "1140px"}}
        first = client.put(URL, params=DRAFT, headers=HEADERS, json={"expectedRevision": 0, "document": document})
        stored = first.json()["document"]
        assert stored["settings"]["appearance"]["layout"]["contentSize"] == "1140px"
        colors = stored["design"]["tokens"]["color"]["tokens"]
        next(t for t in colors if t["name"] == "link-hover")["value"] = "#112233"  # úprava v Colors, Vzhled starý
        second = client.put(URL, params=DRAFT, headers=HEADERS, json={"expectedRevision": 1, "document": stored})
        assert second.json()["document"]["settings"]["appearance"]["colors"]["linkHover"] == "#112233"
        bad = second.json()["document"]
        bad["settings"]["customCss"]["button"]["primary"] = ":scope { color: red }\n@import url(x.css);"
        refused = client.put(URL, params=DRAFT, headers=HEADERS, json={"expectedRevision": 2, "document": bad})
        assert refused.status_code == 422
        assert refused.json()["detail"] == {
            "message": "settings.customCss.button.primary, řádek 2: @import není povolené (jen @keyframes, @media, "
                       "@supports, @container).",
            "path": "settings.customCss.button.primary", "line": 2,
            "reason": "@import není povolené (jen @keyframes, @media, @supports, @container)."}


def test_assets_and_fonts_upload_read_and_delete(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        asset = {**DRAFT, "group": "Logos", "name": "mark.svg", "data": base64.b64encode(SVG).decode()}
        assert client.post(f"{URL}/assets", headers=AGENT, json=asset).status_code == 403
        record = client.post(f"{URL}/assets", headers=HEADERS, json=asset)
        assert record.json() == {"name": "mark.svg", "blob": "assets/Logos/mark.svg", "size": len(SVG),
                                 "type": "image/svg+xml"}
        served = client.get(f"{URL}/assets/Logos/mark.svg", params=DRAFT)
        assert served.content == SVG and "sandbox" in served.headers["content-security-policy"]
        fake = client.post(f"{URL}/assets", headers=HEADERS, json={**asset, "name": "mark.png"})
        assert fake.status_code == 422
        assert (tmp_path / "projects" / "draft" / "site" / "assets" / "Logos" / "mark.svg").is_file()
        assert client.request("DELETE", f"{URL}/assets", params={**DRAFT, "group": "Logos", "name": "mark.svg"},
                              headers={**HEADERS, "content-type": "application/json"}).status_code == 200
        assert client.get(f"{URL}/assets/Logos/mark.svg", params=DRAFT).status_code == 404

        font = {**DRAFT, "name": "inter.woff2", "data": base64.b64encode(WOFF2).decode()}
        assert client.post(f"{URL}/fonts", headers=HEADERS, json=font).json()["file"] == "fonts/inter.woff2"
        assert client.get(f"{URL}/fonts/inter.woff2", params=DRAFT).headers["content-type"] == "font/woff2"
        assert client.request("DELETE", f"{URL}/fonts", params={**DRAFT, "name": "inter.woff2"},
                              headers={**AGENT, "content-type": "application/json"}).status_code == 403
        assert client.request("DELETE", f"{URL}/fonts", params={**DRAFT, "name": "inter.woff2"},
                              headers={**HEADERS, "content-type": "application/json"}).status_code == 200
