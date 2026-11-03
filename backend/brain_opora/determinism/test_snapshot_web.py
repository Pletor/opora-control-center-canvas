from backend.brain_opora.determinism.snapshot_web import lines
from backend.canvas.site_settings import empty


def test_web_section_carries_only_filled_fields_and_page_overrides():
    site = empty()
    site["seo"]["titleTemplate"] = "%s · Zahrada"
    site["design"]["typography"]["h1"] = "Fraunces 48"
    site["email"]["from"] = "info@zahrada.cz"
    pages = [{"id": "home", "path": "/"},
             {"id": "pribeh", "path": "/pribeh",
              "overrides": {"seo": {"titleTemplate": "Příběh"}, "design": {"header": "bez menu"}}}]
    assert lines(site, pages) == [
        "WEB:",
        "- seo · titleTemplate: %s · Zahrada",
        "- email · from: info@zahrada.cz",
        "- design · typography.h1: Fraunces 48",
        "- stránka /pribeh přebíjí · seo.titleTemplate: Příběh · design.header: bez menu",
    ]


def test_web_section_is_omitted_when_nothing_is_filled_and_caps_pages():
    assert lines(empty(), [{"id": "home", "path": "/"}]) == []
    assert lines(None, []) == []
    pages = [{"id": f"p{index}", "path": f"/p{index}", "overrides": {"seo": {"description": "x" * 200}}}
             for index in range(7)]
    rows = lines(empty(), pages)
    assert len(rows) == 7 and rows[-1] == "- … a další stránky s přebitím (2)"
    assert rows[1].endswith("…") and len(rows[1]) < 140
