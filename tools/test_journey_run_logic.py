import json

import pytest

from tools import journey_run_logic as logic

PLAN = {
    "schema": "opora.journey-plan/1", "applicationId": "web", "journeyId": "kampan", "name": "Kampaň",
    "baseUrl": "http://localhost:3000", "digest": "sha256:" + "a" * 64,
    "segments": [
        {"from": "s1", "to": "s2", "open": "/", "scope": "[data-opora-section=\"form\"]",
         "do": "submit", "text": "Chci video zdarma", "expectPath": "/novinky"},
        {"from": "s2", "to": "s3", "open": "/novinky", "scope": "body", "do": "click", "expectPath": "/pribeh"},
    ],
}


@pytest.mark.parametrize("url, path", [
    ("http://x/novinky/", "/novinky"),
    ("http://x/novinky?a=1#b", "/novinky"),
    ("http://x/", "/"),
    ("http://x", "/"),
    ("/a/b//", "/a/b"),
    ("https://x/pribeh#top", "/pribeh"),
])
def test_normalize_path(url, path):
    assert logic.normalize_path(url) == path


def test_page_url_joins_from_root():
    assert logic.page_url("http://localhost:3000/", "/novinky") == "http://localhost:3000/novinky"
    assert logic.page_url("http://localhost:3000", "novinky") == "http://localhost:3000/novinky"


@pytest.mark.parametrize("href, ok", [
    ("/pribeh", True), ("/pribeh/?utm=1", True), ("pribeh", True), ("http://localhost:3000/pribeh#x", True),
    ("/novinky", False), ("#pribeh", False), ("mailto:a@b", False), (None, False), ("", False),
])
def test_href_matches(href, ok):
    assert logic.href_matches(href, "http://localhost:3000/novinky", "/pribeh") is ok


def test_element_strategy():
    submit, click = PLAN["segments"]
    assert logic.element_strategy(submit) == {"kind": "role", "roles": ["button"], "name": "Chci video zdarma"}
    assert logic.element_strategy(click) == {"kind": "href", "expectPath": "/pribeh"}
    assert logic.element_strategy({**click, "text": "Dál"})["roles"] == ["link", "button"]
    assert logic.element_strategy({**submit, "text": None})["kind"] == "submit-button"
    assert logic.element_strategy({"expectPath": "/x"})["kind"] == "href"  # bez `do` je click


def test_fixtures(tmp_path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps({"kampan/s2": {"E-mail": "a@b.cz", "#souhlas": True}}), encoding="utf-8")
    fixtures = logic.load_fixtures(path)
    assert logic.form_data(fixtures, "kampan", "s2") == {"E-mail": "a@b.cz", "#souhlas": "True"}
    assert logic.form_data(fixtures, "kampan", "s3") is None
    assert logic.form_data({"kampan/s2": {}}, "kampan", "s2") is None
    assert logic.load_fixtures(None) == {}
    path.write_text("[1]", encoding="utf-8")
    with pytest.raises(TypeError):
        logic.load_fixtures(path)
    path.write_text('{"kampan/s2": "x"}', encoding="utf-8")
    with pytest.raises(TypeError):
        logic.load_fixtures(path)


@pytest.mark.parametrize("key, target", [
    ("E-mail", ("label", "E-mail")), ("Jméno a příjmení", ("label", "Jméno a příjmení")),
    ("#email", ("selector", "#email")), ("input[name=email]", ("selector", "input[name=email]")),
    (".pole", ("selector", ".pole")), ("form #email", ("selector", "form #email")),
])
def test_field_target(key, target):
    assert logic.field_target(key) == target


def test_short_reason():
    assert logic.short_reason("\n  Timeout 15000ms\n call log: …") == "Timeout 15000ms"
    assert len(logic.short_reason("x" * 400)) == 300
    assert logic.short_reason("") == "neznámá chyba"


def test_build_run_and_passed():
    results = [{"from": "s1", "to": "s2", "ok": True, "reason": None},
               {"from": "s2", "to": "s3", "ok": False, "reason": "URL /novinky, čekáno /pribeh"}]
    run = logic.build_run(PLAN, "python tools/journey_run.py --journey kampan", "2026-10-27T21:40:00Z", results)
    assert run == {
        "schema": "opora.journey-run/1", "applicationId": "web", "journeyId": "kampan",
        "planDigest": PLAN["digest"], "command": "python tools/journey_run.py --journey kampan",
        "at": "2026-10-27T21:40:00Z",
        "segments": [{"from": "s1", "to": "s2", "ok": True},
                     {"from": "s2", "to": "s3", "ok": False, "reason": "URL /novinky, čekáno /pribeh"}],
    }
    assert "passed" not in run and "logUrl" not in run
    assert logic.run_passed(PLAN, run) is False
    results[1]["ok"] = True
    assert logic.run_passed(PLAN, logic.build_run(PLAN, "c", "t", results)) is True
    assert logic.run_passed(PLAN, logic.build_run(PLAN, "c", "t", results[:1])) is False  # neúplný doklad
    assert logic.build_run(PLAN, "c", "t", results, "file:///C:/log.txt")["logUrl"] == "file:///C:/log.txt"


def test_command_line_and_time():
    line = logic.command_line(["tools\\journey_run.py", "--project", "draft", "--base-url", "http://a b"])
    assert line == "python tools/journey_run.py --project draft --base-url 'http://a b'"
    assert len(logic.command_line(["x.py", "y" * 600])) == 500
    assert logic.utc_now().endswith("Z")


def test_check_plan():
    assert logic.check_plan(PLAN) is PLAN
    with pytest.raises(ValueError):
        logic.check_plan({"schema": "jine"})
    with pytest.raises(ValueError):
        logic.check_plan({**PLAN, "segments": []})
    with pytest.raises(TypeError):
        logic.check_plan({**PLAN, "segments": [{"from": "a", "to": "b"}]})
