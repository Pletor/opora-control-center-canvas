"""Shrnutí design systému, webová doména, `machine.design` ticketu a export `design/`."""
import base64
import io
import zipfile

from backend.project.site_admin import store
from backend.project.site_admin.export import export_zip
from backend.project.site_admin.fixture import ember
from backend.project.site_admin.summary import design_ref, has_design, is_web_domain, read_summary
from backend.project.site_admin.test_store import WOFF2, make_service


def app(host="", name="web", platform=None):
    site = {"kind": "application", "environments": [{"name": "prod", "host": host}] if host else []}
    return {"id": name, "name": name, "parentId": None, "site": {**site, **({"platform": platform} if platform else {})}}


def test_summary_has_counts_and_only_the_state_of_settings(tmp_path):
    service = make_service(tmp_path)
    assert read_summary(service, "p1") is None and not has_design(store.read(service, "p1"))
    store.write(service, "p1", 0, ember())
    found = read_summary(service, "p1")
    assert found == {"revision": 1, "title": "Ember", "themes": ["light", "dark"],
                     "tokens": {"color": 4, "type": 3, "spacing": 2, "radius": 1, "shadow": 1, "size": 1},
                     "styles": ["display", "body", "code"], "components": ["Button", "Card"],
                     "settings": {"seo": True, "gdpr": True, "email": True}}
    assert has_design(store.read(service, "p1"))


def test_web_domain_follows_the_frontend_rule():
    assert is_web_domain(app("www.ember.cz")) and is_web_domain(app())
    assert not is_web_domain(app("app.ember.cz")) and not is_web_domain(app("admin2.ember.cz"))
    assert not is_web_domain(app(platform="ios")) and not is_web_domain({"id": "x", "name": "x"})


def test_design_ref_only_under_a_web_domain_with_a_design_system(tmp_path):
    service = make_service(tmp_path)
    graph = {"nodes": [app("www.ember.cz"), {"id": "page", "parentId": "web"}, {"id": "card", "parentId": "page"},
                       app("app.ember.cz", "panel"), {"id": "inner", "parentId": "panel"}]}
    assert design_ref(service, "p1", graph, "card") is None  # bez design systému
    store.write(service, "p1", 0, ember())
    assert design_ref(service, "p1", graph, "card") == {"revision": 1, "export": "/api/site-admin/export?project=p1"}
    assert design_ref(service, "p1", graph, "inner") is None and design_ref(service, "p1", graph, "missing") is None


def test_export_zips_the_design_folder(tmp_path):
    service = make_service(tmp_path)
    store.write(service, "p1", 0, ember())
    store.put_font(service, "p1", "inter.woff2", base64.b64encode(WOFF2).decode())
    revision, data = export_zip(service, "p1")
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert revision == 1 and names == ["design/tokens.css", "design/tokens.json", "design/components.css",
                                       "design/README.md", "design/fonts/inter.woff2"]
