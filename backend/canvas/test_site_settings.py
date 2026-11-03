import pytest

from backend.canvas.site_settings import empty, site_problem


def filled():
    site = empty()
    site["seo"]["titleTemplate"] = "%s · Zahrada"
    site["email"]["from"] = "Zahrada <info@zahrada.cz>"
    site["design"]["typography"]["h1"] = "Fraunces 48/56 tučně"
    return site


def test_empty_and_filled_project_site_are_valid():
    assert site_problem(empty()) is None
    assert site_problem(filled()) is None
    assert set(empty()) == {"seo", "legal", "email", "design"}
    assert set(empty()["design"]["typography"]) == {"h1", "h2", "h3", "h4", "h5", "body", "fonts"}


@pytest.mark.parametrize("change, field", [
    (lambda s: s["email"].update(smtpPassword="tajne"), "email.smtpPassword"),
    (lambda s: s.update(apiKey="x"), "apiKey"),
    (lambda s: s["design"]["typography"].pop("h5"), "design.typography"),
    (lambda s: s["seo"].update(extra=""), "seo"),
    (lambda s: s["seo"].update(description="x" * 301), "seo.description"),
    (lambda s: s["legal"].update(cookies="a\nb"), "legal.cookies"),
    (lambda s: s["email"].update(replyTo="bez zavinace"), "email.replyTo"),
    (lambda s: s.update(design="hlavička"), "design"),
])
def test_project_site_rejects_secrets_and_bad_shape(change, field):
    site = filled()
    change(site)
    assert site_problem(site)[0] == field


def test_secret_message_says_why():
    site = filled()
    site["email"]["password"] = "x"
    assert "tajemství" in site_problem(site)[1]


def test_page_override_is_partial_and_limited_to_seo_and_header_footer():
    assert site_problem({"seo": {"titleTemplate": "Příběh"}}, partial=True) is None
    assert site_problem({"design": {"header": "bez menu", "footer": "jen kontakt"}}, partial=True) is None
    assert site_problem({"design": {"buttons": "zelená"}}, partial=True)[0] == "design"
    assert site_problem({"legal": {"cookies": "x"}}, partial=True)[0] == "site"
    assert site_problem({"seo": {}}, partial=True)[0] == "seo"
    assert site_problem({"seo": {"description": "  "}}, partial=True)[0] == "seo.description"
    assert site_problem({"seo": {"token": "x"}}, partial=True)[0] == "seo.token"
