import pytest

from backend.project.site_admin.design_system import SiteAdminInvalid, empty, normalize
from backend.project.site_admin.fixture import ember


def settings(**parts):
    document, notes = normalize({**ember(), "settings": {**ember()["settings"], **parts}})
    return document["settings"], notes


def test_empty_document_has_full_settings_with_defaults():
    parts = empty()["settings"]
    assert parts["seo"]["titleTemplate"] == "%s" and parts["seo"]["robots"]["index"] is True
    assert parts["seo"]["sitemap"] is True and parts["seo"]["twitterCard"] == "summary_large_image"
    assert parts["affiliate"] == {"enabled": False, "param": "ref", "cookieDays": 30, "attribution": "last",
                                  "disclosure": "", "programs": []}
    assert parts["email"]["port"] == 587 and parts["email"]["security"] == "starttls" and parts["email"]["secretRef"] == ""
    bar = parts["gdpr"]["cookieBar"]
    assert bar["enabled"] is False and bar["categories"] == ["necessary"] and bar["consentDays"] == 180
    assert bar["rejectLabel"] == "Odmítnout vše" and bar["reopen"] is True
    assert parts["header"]["nav"] == "source:pages" and parts["footer"]["cookieLink"] is True


def test_legacy_secure_flag_becomes_security_mode():
    parts, notes = settings(email={"host": "smtp.example.cz", "port": 465, "secure": True, "from": "a@example.cz"})
    assert parts["email"]["security"] == "tls" and "secure" not in parts["email"] and notes == []
    parts, _ = settings(email={"host": "smtp.example.cz", "port": 587, "secure": True, "from": "a@example.cz"})
    assert parts["email"]["security"] == "starttls"


def test_smtp_port_and_security_mismatch_is_a_note():
    _, notes = settings(email={"host": "smtp.example.cz", "port": 465, "security": "starttls", "from": "a@example.cz"})
    assert any("RFC 8314" in note for note in notes)
    _, notes = settings(email={"host": "smtp.example.cz", "security": "none"})
    assert any("bez šifrování" in note for note in notes) and any("from" in note for note in notes)


def test_cookie_bar_always_keeps_necessary_first_and_dedupes():
    parts, _ = settings(gdpr={"cookieBar": {"categories": ["marketing", "analytics", "marketing"],
                                            "categoryInfo": {"analytics": {"label": "Měření"}}}})
    bar = parts["gdpr"]["cookieBar"]
    assert bar["categories"] == ["necessary", "analytics", "marketing"]
    assert bar["categoryInfo"] == {"analytics": {"label": "Měření", "description": ""}}


def test_cookie_bar_advice_notes():
    _, notes = settings(gdpr={"cookieBar": {"enabled": True, "consentDays": 700}, "contact": "Ember"})
    assert any("zásady" in note for note in notes) and any("13 měsících" in note for note in notes)
    assert any("ePrivacy" in note for note in notes) and any("kontakt správce" in note for note in notes)


def test_seo_notes_and_assets():
    parts, notes = settings(seo={"description": "x" * 200, "robots": {"index": False},
                                 "ogImage": "assets/Logos/mark.svg", "structuredData": '{"@context": "https://schema.org"}'})
    assert parts["seo"]["ogImage"] == "assets/Logos/mark.svg" and parts["seo"]["robots"]["follow"] is True
    assert any("200 znaků" in note for note in notes) and any("noindex" in note for note in notes)
    parts, notes = settings(seo={"ogImage": "assets/Logos/gone.png"})
    assert parts["seo"]["ogImage"] == "" and any("gone.png" in note for note in notes)


def test_affiliate_wants_marketing_category_and_disclosure():
    _, notes = settings(affiliate={"enabled": True, "programs": [{"name": "Heureka", "url": "https://heureka.cz"}]})
    assert any("marketing" in note for note in notes) and any("provizní" in note for note in notes)


@pytest.mark.parametrize("parts, message", [
    ({"email": {"heslo": "x"}}, "tajemství"),
    ({"email": {"apiKey": "x"}}, "tajemství"),
    ({"email": {"port": 0}}, "settings.email.port"),
    ({"email": {"host": "smtp example"}}, "host"),
    ({"email": {"from": "not-an-email"}}, "e-mail"),
    ({"email": {"security": "ssl"}}, "starttls"),
    ({"seo": {"titleTemplate": "Bez místa"}}, "%s"),
    ({"seo": {"description": "x" * 501}}, "500"),
    ({"seo": {"robots": "noindex"}}, "settings.seo.robots"),
    ({"seo": {"ogImage": "javascript:alert(1)"}}, "asset projektu"),
    ({"seo": {"structuredData": "{oops"}}, "řádek 1"),
    ({"seo": {"structuredData": '{"a": "</script>"}'}}, "</"),
    ({"seo": {"twitterSite": "ember"}}, "@jmeno"),
    ({"affiliate": {"param": "Ref Code"}}, "parametr"),
    ({"affiliate": {"cookieDays": 1000}}, "cookieDays"),
    ({"affiliate": {"programs": [{"url": "http://x.cz"}]}}, "https"),
    ({"gdpr": {"cookieBar": {"position": "left"}}}, "position"),
    ({"gdpr": {"cookieBar": {"consentDays": 0}}}, "consentDays"),
    ({"gdpr": {"cookieBar": {"categoryInfo": {"tracking": {}}}}}, "categoryInfo"),
    ({"gdpr": {"cookieBar": {"policyUrl": "javascript:alert(1)"}}}, "odkaz"),
    ({"gdpr": {"contact": {"email": "x"}}}, "e-mail"),
])
def test_invalid_settings_are_422(parts, message):
    with pytest.raises(SiteAdminInvalid, match=message):
        settings(**parts)
