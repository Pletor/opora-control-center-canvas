"""Strojové specifikace případů (cases.md → `grade.SPECS`): sekce, kritéria záměru, stavy, cesty, termíny testů.

Každý případ:
- `template`: výchozí repo (`templates/<T>`),
- `sections`: URL → id sekcí v očekávaném pořadí v DOM (Q1/Q2, staticky i za běhu),
- `criteria`: URL → fn(page, ok) – kritéria, která zadání výslovně žádá (Q1/Q2), jména `crit:*`,
- `states`: fn(page, ok, base) – chybové, prázdné a průběžné stavy vyvolané v prohlížeči (Q3), jména `state:*`,
- `journeys`: [(id cesty, fixtures, routes)] – plán ze skryté zlaté mapy `seeds/<případ>.json`; `routes` stubují
  síť (`page.route`) během přehrání,
- `test_terms`: co by testy agenta měly zmínit (Q8: id sekcí a texty kritérií),
- `info`: informativní metriky mimo `checks_pass` (např. `separate_components` = členění na komponenty).
Kritéria, která zadání nežádá, sem nepatří (metriky.md Q1).
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

ALERTS = '[role="alert"], [aria-live]:not([aria-live="off"])'


def path_of(page):
    p = urlsplit(page.url).path or "/"
    return p.rstrip("/") or "/"


def visible_alerts(scope):
    loc = scope.locator(ALERTS)
    n = 0
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if el.is_visible() and el.inner_text().strip():
                n += 1
        except Exception:  # noqa: BLE001 - odpojený prvek se nepočítá
            pass
    # Zadání chce „u pole ukáže chybu“: platí i viditelný text, na který odkazuje pole s aria-invalid.
    n += scope.evaluate(r"""s => [...s.querySelectorAll('[aria-invalid="true"][aria-describedby]')]
        .flatMap(f => f.getAttribute('aria-describedby').split(/\s+/))
        .map(id => document.getElementById(id))
        .filter(e => e && !e.matches('[role="alert"], [aria-live]:not([aria-live="off"])')
                     && e.offsetParent !== null && e.textContent.trim()).length""")
    return n


def field(scope, label):
    loc = scope.get_by_label(label)
    return loc.first if loc.count() else None


def fill(scope, values: dict):
    """Vyplní pole podle popisku; vrací seznam chybějících popisků."""
    missing = []
    for label, value in values.items():
        f = field(scope, label)
        if f is None:
            missing.append(label)
        else:
            f.fill(value)
    return missing


def guarded(ok, names, fn):
    """Spustí kontrolu stavu; výjimka (chybí prvek, timeout) = všechny její kontroly `names`, které ještě
    nezapsala, neprošly s důvodem (jmenovatel Q3 je pro každý výstup stejný)."""
    written = set()

    def track(name, value, note=""):
        written.add(name)
        ok(name, value, note)
    try:
        fn(track)
    except Exception as e:  # noqa: BLE001
        for name in names:
            if name not in written:
                ok(name, False, f"výjimka: {str(e).splitlines()[0][:200]}")


def section(page, sid):
    return page.locator(f'[data-opora-section="{sid}"]').first


# --- C01 Příběh -----------------------------------------------------------------------------------

def c01_criteria(page, ok):
    cta = page.locator('[data-opora-section="cta"]')
    link = cta.get_by_role("link", name="Chci začít pěstovat")
    ok("crit:cta_link_home", link.count() >= 1 and link.first.get_attribute("href") == "/",
       f"odkazů s názvem: {link.count()}")
    quotes = page.locator('[data-opora-section="dukaz"]').locator("blockquote, figure").count()
    ok("crit:dukaz_3_quotes", quotes >= 3, f"blockquote/figure: {quotes}")


# --- C02 Kontakt s validací -----------------------------------------------------------------------

C02_VALID = {"Jméno": "Jana Testovací", "E-mail": "jana@example.test", "Popis": "Chci upravit zahradu za domem."}


def c02_criteria(page, ok):
    form = section(page, "form")
    missing = [lab for lab in C02_VALID if field(form, lab) is None]
    ok("crit:labels", not missing, "chybí popisek: " + ", ".join(missing) if missing else "Jméno, E-mail, Popis")
    btn = form.get_by_role("button", name="Odeslat poptávku")
    ok("crit:submit_button", btn.count() >= 1, f"tlačítek: {btn.count()}")


def c02_states(page, ok, base):
    def empty(ok):
        page.goto(base + "/kontakt")
        form = section(page, "form")
        form.get_by_role("button", name="Odeslat poptávku").first.click()
        page.wait_for_timeout(400)
        alerts = visible_alerts(form)
        ok("state:empty_blocked", path_of(page) == "/kontakt" and alerts > 0,
           f"URL {path_of(page)}, viditelných alert/aria-live: {alerts}")
        flags = {lab: (field(form, lab).get_attribute("aria-invalid") if field(form, lab) else None) for lab in C02_VALID}
        ok("state:empty_aria_invalid", all(v == "true" for v in flags.values()), json.dumps(flags, ensure_ascii=False))

    def bad_email(ok):
        page.goto(base + "/kontakt")
        form = section(page, "form")
        values = {**C02_VALID, "E-mail": "neplatny"}
        missing = fill(form, values)
        form.get_by_role("button", name="Odeslat poptávku").first.click()
        page.wait_for_timeout(400)
        flags = {lab: (field(form, lab).get_attribute("aria-invalid") if field(form, lab) else None) for lab in values}
        only = flags["E-mail"] == "true" and flags["Jméno"] != "true" and flags["Popis"] != "true"
        ok("state:email_error_only", not missing and path_of(page) == "/kontakt" and only and visible_alerts(form) > 0,
           f"URL {path_of(page)}, aria-invalid {json.dumps(flags, ensure_ascii=False)}")
        kept = {lab: field(form, lab).input_value() if field(form, lab) else None for lab in values}
        ok("state:values_kept", kept == values, json.dumps(kept, ensure_ascii=False)[:200])

    guarded(ok, ["state:empty_blocked", "state:empty_aria_invalid"], empty)
    guarded(ok, ["state:email_error_only", "state:values_kept"], bad_email)


# --- C03 Kampaň Pěstování -------------------------------------------------------------------------

def c03_nav(page, ok):
    nav = page.locator("nav").first
    names = ["Domů", "Novinky", "Příběh"]
    have = [n for n in names if page.locator("nav").count() and nav.get_by_role("link", name=n, exact=True).count()]
    ok(f"crit:nav:{path_of(page)}", have == names, f"odkazy v nav: {have}")


def c03_states(page, ok, base):
    def bad_email(ok):
        page.goto(base + "/")
        form = section(page, "form")
        f = field(form, "E-mail")
        if f is None:
            f = form.locator("input").first
        f.fill("neplatny")
        form.get_by_role("button", name="Chci video zdarma").first.click()
        page.wait_for_timeout(500)
        ok("state:invalid_email_blocked", path_of(page) == "/", f"URL {path_of(page)}")

    guarded(ok, ["state:invalid_email_blocked"], bad_email)


# --- C06 Prodej kurzu -----------------------------------------------------------------------------

def c06_video(page, ok):
    extra = page.evaluate("""() => {
      const s = document.querySelector('[data-opora-section="form"]'); if (!s) return '';
      const c = s.cloneNode(true);
      c.querySelectorAll('label,button,input,textarea,select,[role=button]').forEach(e => e.remove());
      return (c.textContent || '').replace(/\\s+/g, ' ').trim(); }""")
    ok("crit:form_reassures", len(extra) >= 15, f"text mimo label/tlačítko: {extra[:120]!r}")


# --- C07 Poptávka zahrady -------------------------------------------------------------------------

C07_VALID = {"Jméno": "Petr Zkušební", "E-mail": "zahrada@example.test", "Velikost": "400",
             "Popis": "Zanedbaná zahrada za domem, chci návrh a cenu."}
C07_API = "**/api/poptavka"


def c07_gallery(page, ok):
    # Zadání chce „aspoň 6 realizací“, ne obrázky: položka = li/figure/article nebo img s alt (víc z nich).
    n = page.locator('[data-opora-section="galerie"]').first.evaluate("""s => Math.max(
        s.querySelectorAll('li, figure, article').length,
        [...s.querySelectorAll('img')].filter(e => (e.getAttribute('alt') || '').trim()).length)""")
    ok("crit:gallery_6", n >= 6, f"položek galerie: {n}")


def c07_states(page, ok, base):
    def submit_with(status, hold=False):
        pending, seen = [], []

        def handler(route):
            seen.append(route.request)
            if hold:
                pending.append(route)
            else:
                route.fulfill(status=status, content_type="application/json", body=json.dumps({"ok": status < 400}))
        page.unroute(C07_API)  # stub z předchozího (i spadlého) stavu pryč
        page.route(C07_API, handler)
        page.goto(base + "/kontakt")
        form = section(page, "form")
        missing = fill(form, C07_VALID)
        form.get_by_role("button", name="Odeslat poptávku").first.click()
        return form, missing, pending, seen

    def sending(ok):
        form, missing, pending, _ = submit_with(201, hold=True)
        page.wait_for_timeout(400)
        btn = form.locator("button").filter(has_text=re.compile("Odesílám"))
        busy = btn.count() >= 1 and btn.first.is_disabled()
        ok("state:sending", not missing and bool(pending) and busy,
           f"požadavků: {len(pending)}, tlačítko „Odesílám…“: {btn.count()}, disabled: {busy}")
        for r in pending:
            r.fulfill(status=201, content_type="application/json", body="{}")
        page.unroute(C07_API)

    def server_error(ok):
        form, missing, _, seen = submit_with(500)
        try:
            form.locator(ALERTS).filter(has_text=re.compile(r"\S")).first.wait_for(state="visible", timeout=4000)
        except Exception:  # noqa: BLE001, S110 - kontrola níže selže s důvodem
            pass
        kept = {lab: field(form, lab).input_value() if field(form, lab) else None for lab in C07_VALID}
        alerts = visible_alerts(form)
        ok("state:server_error", not missing and seen and path_of(page) == "/kontakt" and alerts > 0,
           f"URL {path_of(page)}, požadavků {len(seen)}, alert {alerts}")
        ok("state:error_values_kept", kept == C07_VALID, json.dumps(kept, ensure_ascii=False)[:200])
        page.unroute(C07_API)

    def success(ok):
        form, missing, _, seen = submit_with(201)
        try:
            page.wait_for_url(re.compile(r"/dekujeme/?$"), timeout=5000)
        except Exception:  # noqa: BLE001, S110
            pass
        body, ctype = None, ""
        if seen:
            ctype = seen[0].headers.get("content-type", "")
            try:
                body = seen[0].post_data_json
            except Exception:  # noqa: BLE001
                body = None
        keys = len(body) if isinstance(body, dict) else 0
        ok("state:success", not missing and path_of(page) == "/dekujeme", f"URL {path_of(page)}")
        ok("crit:json_body", "application/json" in ctype and keys >= 4, f"content-type {ctype!r}, klíčů {keys}")
        page.unroute(C07_API)

    guarded(ok, ["state:sending"], sending)
    guarded(ok, ["state:server_error", "state:error_values_kept"], server_error)
    guarded(ok, ["state:success", "crit:json_body"], success)


SPECS = {
    "C01": {"template": "T0", "sections": {"/pribeh": ["hero", "pribeh", "dukaz", "cta"]},
            "criteria": {"/pribeh": c01_criteria}, "journeys": [],
            "test_terms": ["hero", "pribeh", "dukaz", "cta", "Chci začít pěstovat"],
            "info": {"separate_components": True}},
    "C02": {"template": "T0", "sections": {"/kontakt": ["hero", "form"], "/dekujeme": ["hero"]},
            "criteria": {"/kontakt": c02_criteria}, "states": c02_states,
            "journeys": [("poptavka", {"poptavka/s2": C02_VALID}, {})],
            "test_terms": ["Odeslat poptávku", "aria-invalid", "/dekujeme", "E-mail", "Popis"]},
    "C03": {"template": "T0",
            "sections": {"/": ["form", "cta"], "/novinky": ["hero", "clanky"], "/pribeh": ["hero", "pribeh"]},
            "criteria": {"/": c03_nav, "/novinky": c03_nav, "/pribeh": c03_nav}, "states": c03_states,
            "journeys": [("kampan", {"kampan/s2": {"E-mail": "pestitel@example.test"}}, {})],
            "test_terms": ["Domů", "Novinky", "Příběh", "Chci video zdarma", "/novinky", "/pribeh"]},
    "C06": {"template": "T0",
            "sections": {"/": ["hero"], "/video": ["hero", "video", "form"], "/nabidka": ["hero", "cenik", "cta"],
                         "/upsell": ["hero"], "/miniupsell": ["hero"]},
            "criteria": {"/video": c06_video},
            "journeys": [("kurz", {"kurz/prodej": {"E-mail": "zahradkar@example.test"}}, {})],
            "test_terms": ["Chci video zdarma", "Pošlete mi nabídku", "/nabidka", "/upsell", "/miniupsell"]},
    "C07": {"template": "T0",
            "sections": {"/realizace": ["hero", "galerie", "cta"], "/kontakt": ["hero", "form"], "/dekujeme": ["hero"]},
            "criteria": {"/realizace": c07_gallery}, "states": c07_states,
            "journeys": [("poptavka", {"poptavka/dik": C07_VALID}, {C07_API: 201})],
            "test_terms": ["Odeslat poptávku", "Odesílám", "/api/poptavka", "Chci podobnou zahradu", "/dekujeme"]},
}
