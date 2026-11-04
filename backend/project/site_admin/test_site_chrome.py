import pytest

from backend.project.site_admin.compile import components_css, readme
from backend.project.site_admin.design_system import SiteAdminInvalid, normalize
from backend.project.site_admin.fixture import ember

HEADER = {"logoAsset": "assets/Logos/mark.svg", "logoAlt": "Ember", "nav": "manual", "sticky": True,
          "items": [{"label": "Menu", "pageId": "menu"}, {"label": "Kontakt", "url": "/kontakt"}],
          "cta": {"label": "Rezervace", "pageId": "rezervace", "variant": "primary"}, "variant": "centered"}
FOOTER = {"columns": [{"title": "Kavárna", "links": [{"label": "O nás", "pageId": "o-nas"}]}],
          "social": [{"name": "instagram", "url": "https://instagram.com/ember"}], "legal": "© Ember s.r.o., IČO 1"}


def document(**parts):
    return normalize({**ember(), "settings": {**ember()["settings"], **parts}})


def test_header_and_footer_round_trip_without_notes():
    saved, notes = document(header=HEADER, footer=FOOTER)
    assert notes == []
    assert saved["settings"]["header"]["items"][1] == {"label": "Kontakt", "pageId": "", "url": "/kontakt"}
    assert saved["settings"]["header"]["cta"]["variant"] == "primary"
    assert saved["settings"]["footer"]["variant"] == "columns"
    assert normalize(saved) == (saved, [])


def test_missing_logo_and_unknown_cta_variant_drop_with_notes():
    saved, notes = document(header={**HEADER, "logoAsset": "assets/Logos/old.png",
                                    "cta": {"label": "Rezervace", "url": "https://ember.cz/r", "variant": "ghost"}})
    assert saved["settings"]["header"]["logoAsset"] == "" and saved["settings"]["header"]["cta"]["variant"] == ""
    assert any("old.png" in note for note in notes) and any("ghost" in note for note in notes)
    _, notes = document(footer={"columns": FOOTER["columns"]})
    assert any("právní řádek" in note for note in notes)


@pytest.mark.parametrize("parts, message", [
    ({"header": {"items": [{"label": "X", "url": "javascript:alert(1)"}]}}, "odkaz"),
    ({"header": {"items": [{"label": "X", "url": "//evil.example"}]}}, "odkaz"),
    ({"header": {"items": [{"label": "X"}]}}, "buď na stránku"),
    ({"header": {"items": [{"url": "/a"}]}}, "popisek"),
    ({"header": {"items": [{"label": "X", "url": "/a"}] * 13}}, "12"),
    ({"header": {"nav": "auto"}}, "settings.header.nav"),
    ({"header": {"variant": "huge"}}, "settings.header.variant"),
    ({"header": {"cta": {"label": "Koupit"}}}, "cíl"),
    ({"footer": {"social": [{"name": "myspace", "url": "https://x.cz"}]}}, "name"),
    ({"footer": {"social": [{"name": "x", "url": "http://x.cz"}]}}, "https"),
    ({"footer": {"columns": [{"title": "a"}] * 7}}, "6"),
    ({"footer": {"legal": "x" * 2001}}, "2000"),
])
def test_invalid_chrome_is_422(parts, message):
    with pytest.raises(SiteAdminInvalid, match=message):
        document(**parts)


def test_components_css_has_header_footer_and_cookie_bar_with_motion_and_contrast():
    css = components_css(document()[0])
    layer = css.split("@layer components {")[1]
    for block in (".ds-header {", ".ds-header--sticky {", ".ds-footer__legal {", ".ds-cookie-bar {",
                  ".ds-cookie-bar--bottom-right {", ".ds-cookie-reopen {"):
        assert f"  {block}" in layer
    assert "@media (prefers-reduced-motion: no-preference) {" in layer and "@keyframes ds-cookie-bar-in" in layer
    assert "@media (prefers-contrast: more), (forced-colors: active) {" in layer
    assert "  .ds-cookie-bar__choice--settings {" in layer  # odmítnout a přijmout sdílí .ds-cookie-bar__choice


def test_readme_has_site_settings_section():
    saved, _ = document(header=HEADER, footer=FOOTER)
    text = readme(saved).split("### Nastavení webu")[1]
    assert "šablona `%s · Ember`" in text and "`sitemap.xml`" in text
    assert "`ds-header--centered`, `ds-header--sticky`; menu: ruční menu (Menu → stránka `menu`" in text
    assert "CTA „Rezervace“ → stránka `rezervace` jako `ds-btn ds-btn--primary`" in text
    assert "Sloupec „Kavárna“: O nás → stránka `o-nas`" in text
    assert "„Přijmout vše“ a „Odmítnout vše“" in text and "stránka `zasady-cookies`" in text
    assert "`env:SMTP_PASSWORD`" in text and "hunter" not in text
