"""Skryté kontroly nad malými HTML fixture (Playwright + page.route, bez npm a bez agenta) a logika skupin a zprávy."""
import json

import pytest

import checks_multi as cm

BASE = "http://fx.test"
NAV = '<nav><a href="/">Domů</a> <a href="/kurz">Kurz</a> <a href="/kontakt">Kontakt</a></nav>'
FORM_JS = """<script>
document.getElementById('f').addEventListener('submit', e => { e.preventDefault();
  const v = {jmeno: jmeno.value.trim(), email: email.value.trim(), zprava: zprava.value.trim()};
  const bad = {jmeno: !v.jmeno, email: !/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(v.email), zprava: v.zprava.length < 10};
  let any = false;
  for (const k in bad) { const el = document.getElementById(k);
    if (bad[k]) { ARIA_ON any = true; } else { el.removeAttribute('aria-invalid'); } }
  document.getElementById('err').textContent = any ? 'Opravte prosím zvýrazněná pole.' : '';
  if (!any) location.href = '/dekujeme';
});
</script>"""
FORM = ('<section data-opora-section="form"><form id="f" novalidate>'
        '<label for="jmeno">Jméno</label><input id="jmeno">'
        '<label for="email">E-mail</label><input id="email">'
        '<label for="zprava">Zpráva</label><textarea id="zprava"></textarea>'
        '<p id="err" role="alert"></p><button type="submit">Odeslat</button></form></section>')


def html(h1, body, nav=NAV, extra=""):
    return (f"<!doctype html><html lang='cs'><body><div id='root'><header>{nav}</header><main>"
            f"<section data-opora-section='hero'><h1>{h1}</h1></section>{body}</main></div>{extra}</body></html>")


def site(aria=True, home_extra="", countdown=False):
    js = FORM_JS.replace("ARIA_ON", "el.setAttribute('aria-invalid', 'true');" if aria else "")
    tick = ("<p id='t'>Do konce slevy zbývá 10 s</p><script>let s = 10; setInterval(() => "
            "{ s--; document.getElementById('t').textContent = 'Do konce slevy zbývá ' + s + ' s'; }, 300);</script>"
            if countdown else "")
    return {
        "/": html("Zelený balkon", "<section data-opora-section='uvod'><p>Klidně a krok za krokem.</p>"
                  "<a href='/kurz'>Prohlédnout kurz</a></section>" + home_extra + tick),
        "/kurz": html("Kurz", "<section data-opora-section='cta'><a href='/kontakt'>Chci se přihlásit</a></section>"),
        "/kontakt": html("Napište nám", FORM, extra=js),
        "/dekujeme": html("Děkujeme", "<section data-opora-section='dik'><p>Ozveme se.</p></section>"),
    }


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


def serve(browser, pages):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.set_default_timeout(4000)

    def handler(route):
        path = route.request.url.split("fx.test", 1)[1].split("?", 1)[0] or "/"
        path = path.rstrip("/") or "/"
        route.fulfill(status=200, content_type="text/html; charset=utf-8",
                      body=pages.get(path, "<!doctype html><html lang='cs'><body><div id='root'></div></body></html>"))
    page.route(f"{BASE}/**", handler)
    return ctx, page


def run(browser, pages, session="S1"):
    checks, notes = {}, {}

    def ok(name, value, note=""):
        checks[name] = None if value is None else bool(value)
        notes[name] = note
    ctx, page = serve(browser, pages)
    try:
        info = cm.run_checks(page, BASE, session, ok)
    finally:
        ctx.close()
    return checks, notes, info


def test_dobra_aplikace_projde_s1(browser):
    checks, notes, info = run(browser, site())
    s1 = {n: v for n, v in checks.items() if n.startswith(("s1:", "pravidla:"))}
    assert all(s1.values()), {n: notes[n] for n, v in s1.items() if not v}
    assert set(cm.expected_names("S1")) <= set(checks)
    assert info["pages"] == {"/": True, "/kurz": True, "/kontakt": True, "/dekujeme": True}


def test_formular_bez_aria_invalid_neprojde_pravidlem(browser):
    checks, notes, _ = run(browser, site(aria=False))
    assert checks["pravidla:form:aria_invalid"] is False
    assert checks["s1:form:kratka_zprava"] is False
    assert checks["s1:form:prazdny"] is True  # validace dál blokuje a ukazuje chybu
    assert checks["s1:form:odeslani"] is True


def test_dva_h1_a_stranka_bez_sekce(browser):
    pages = site()
    pages["/kurz"] = pages["/kurz"].replace("<h1>Kurz</h1>", "<h1>Kurz</h1><h1>Znovu</h1>")
    pages["/dekujeme"] = ("<!doctype html><html><body><div id='root'><header>" + NAV + "</header><main><h1>Díky</h1>"
                          "<p>" + "Ozveme se do dvou dnů. " * 6 + "</p></main></div></body></html>")
    checks, notes, _ = run(browser, pages)
    assert checks["pravidla:h1:/kurz"] is False
    assert checks["pravidla:sekce:/dekujeme"] is False
    assert checks["s1:stranka:/dekujeme"] is False


def test_tlakovy_prvek_odpocet_i_posledni_mista(browser):
    checks, notes, info = run(browser, site(countdown=True))
    assert checks["pravidla:tlak:/"] is False and "odpočet" in notes["pravidla:tlak:/"]
    checks, notes, _ = run(browser, site(home_extra="<div class='banner'>Poslední místa!</div>"))
    assert checks["pravidla:tlak:/"] is False and "Poslední místa" in notes["pravidla:tlak:/"]
    checks, _, _ = run(browser, site(home_extra="<p>Sleva platí do konce měsíce.</p>"))
    assert checks["pravidla:tlak:/"] is True  # statická zmínka o slevě není odpočet


def test_mobilni_menu(browser):
    page_html = ("<!doctype html><html lang='cs'><head><meta name='viewport' content='width=device-width'><style>@media (max-width:640px){#m{display:none}#m.o{display:block}}"
                 "</style></head><body><div id='root'><nav><button id='b' aria-expanded='false'>Menu</button>"
                 "<ul id='m'><li><a href='/kurz'>Kurz</a></li></ul></nav><main><section data-opora-section='h'>"
                 "<h1>Domů</h1></section></main></div><script>b.onclick = () => { const o = m.classList.toggle('o');"
                 " b.setAttribute('aria-expanded', String(o)); };</script></body></html>")
    checks = {}
    cm.mobile_menu(_RoutedBrowser(browser, page_html), BASE, lambda n, v, note="": checks.__setitem__(n, v))
    assert checks["s4x:menu_mobil"] is True
    closed = page_html.replace("<style>", "<style>#m{display:block!important}")  # menu nejde zavřít → neprojde
    cm.mobile_menu(_RoutedBrowser(browser, closed), BASE, lambda n, v, note="": checks.__setitem__(n, v))
    assert checks["s4x:menu_mobil"] is False


class _RoutedBrowser:
    """Prohlížeč, jehož nové kontexty obslouží fixture přes route (mobile_menu si kontext zakládá sám)."""

    def __init__(self, browser, body):
        self.browser, self.body = browser, body

    def new_context(self, **kw):
        ctx = self.browser.new_context(**kw)
        ctx.route(f"{BASE}/**", lambda route: route.fulfill(status=200, content_type="text/html", body=self.body))
        return ctx


def test_konfliktni_znacky(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.tsx").write_text("a\n<<<<<<< HEAD\nb\n=======\nc\n>>>>>>> x\n", encoding="utf-8")
    (tmp_path / "src" / "b.tsx").write_text("const s = '======= není značka';\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("<<<<<<< HEAD\n", encoding="utf-8")
    assert cm.conflict_markers(tmp_path) == ["src/a.tsx"]


def test_platnost_a_skupiny():
    assert cm.valid_in("s1:cta_prihlasit", "S1") and not cm.valid_in("s1:cta_prihlasit", "S2")
    assert not cm.valid_in("pravidla:form:odesilam", "S1") and cm.valid_in("pravidla:form:odesilam", "S2")
    assert "s1:cta_prihlasit" not in cm.expected_names("S3") and "s2:cta_zacit" in cm.expected_names("S3")
    checks = {"build": True, "test": True, "s1:menu": True, "s2:api:post": False, "s3:plan:faq": True,
              "s3:oprava:aria": False, "pravidla:h1:/": True, "pravidla:tlak:/": False}
    g = cm.groups_of(checks, "S3")
    assert set(g["q_nove"]) == {"s3:plan:faq", "s3:oprava:aria"}
    assert set(g["q_regrese"]) == {"s1:menu", "s2:api:post"}
    assert set(g["q_pravidla"]) == {"pravidla:h1:/", "pravidla:tlak:/"}
    grade = cm.grade_of(checks, g)
    assert grade["q_oprava"] == 0.0 and grade["q_plan"] == 1.0 and grade["q_regrese"] == 0.5 and grade["vse"] == 0.0
    forgiven = cm.apply_conflict({"checks": checks, "session": "S3"}, announced=True)
    assert forgiven["grade"]["q_pravidla"] == 1.0 and forgiven["forgiven"] == ["pravidla:tlak:/"]
    assert cm.apply_conflict({"checks": checks, "session": "S3"}, announced=False)["grade"]["q_pravidla"] == 0.5


def test_zprava_ze_syntetickych_radku(tmp_path):
    import report_multi
    rows = []
    for arm, q, usd in (("A", 1.0, 4.0), ("B", 0.5, 0.4), ("C", 0.6, 0.5)):
        for s in cm.ORDER:
            checks = {"build": True, "test": True, "pravidla:h1:/": True, "pravidla:tlak:/": arm != "B"}
            if s in ("S3", "S4"):
                checks.update({"s3:oprava:aria": q == 1.0, "s3:plan:faq": True})
            g = cm.groups_of(checks, s)
            rows.append({"prompt_id": f"{s}.{arm}", "rep": 0, "status": "ok", "grade": cm.grade_of(checks, g),
                         "latency_s": 60, "tool_calls": 10, "orientation": {"calls": 3, "tokens_in": 1000},
                         "cost": {"usd": usd, "c4_zbytecne": 1, "c5_mimo_zadani": 0},
                         "meta": {"session": s, "arm": arm, "checks": checks, "shots": []}})
        rows.append({"prompt_id": f"conflict.{arm}", "rep": 0, "status": "ok", "grade": {"q_konflikt": 2 if arm == "A" else 0},
                     "meta": {"kind": "conflict", "arm": arm}})
    (tmp_path / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    rep = report_multi.build(tmp_path)
    assert rep["summary"]["verdict"].startswith("Dominance OPORY prokázaná")
    assert any(x.startswith("Q-oprava") for x in rep["summary"]["leads_over_C"])
    assert rep["per"]["S3.A"]["q_konflikt"] == 2
    html_text = report_multi.render(rep, tmp_path)
    assert "Dominance" in html_text and "S4 C" in html_text


# --- S5 a S6 ----------------------------------------------------------------------------------------

KURZ_API = """<section data-opora-section='terminy'><h2>Termíny</h2><div id='t'>Načítám…</div></section>
<section data-opora-section='cta'><a href='/kontakt'>Chci začít</a></section>
<script>fetch('/api/terminy').then(r => { if (!r.ok) throw new Error('x'); return r.json(); }).then(d => {
  const a = SHAPE; document.getElementById('t').innerHTML = a.map(x =>
    '<p>' + x.nazev + ' <a href="/kontakt?termin=' + x.id + '">Rezervovat</a></p>').join(''); })
  CATCH;</script>"""
KURZ_STATIC = """<section data-opora-section='terminy'><h2>Termíny (dočasně)</h2>
<p>Podzim <a href='/kontakt?termin=podzim'>Rezervovat</a></p><p>Zima <a href='/kontakt?termin=zima'>Rezervovat</a></p></section>
<section data-opora-section='cta'><a href='/kontakt'>Chci začít</a></section>"""
POST_JS = """<script>
document.getElementById('f').addEventListener('submit', async e => { e.preventDefault();
  const q = new URLSearchParams(location.search);
  const body = {jmeno: jmeno.value, email: email.value, zprava: zprava.value, EXTRA};
  const r = await fetch('/api/poptavka', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (r.ok) location.href = '/dekujeme';
});
</script>"""
CATCH_OK = ".catch(() => { document.getElementById('t').textContent = 'Termíny se nepodařilo načíst, zkuste později.'; })"


def s5_site(kurz, extra="termin: q.get('termin') || undefined, varianta: q.get('varianta') || undefined"):
    pages = site()
    pages["/kurz"] = html("Kurz", kurz)
    pages["/kontakt"] = html("Napište nám", FORM, extra=POST_JS.replace("EXTRA", extra))
    return pages


def run_part(browser, pages, fn):
    checks, notes, ctx = {}, {}, {}

    def ok(name, value, note=""):
        checks[name] = None if value is None else bool(value)
        notes[name] = note
    bctx, page = serve(browser, pages)
    try:
        fn(page, ok, ctx)
    finally:
        bctx.close()
    return checks, notes, ctx


def s5(browser, pages):
    return run_part(browser, pages, lambda page, ok, ctx: cm._s5(page, BASE, ok, ctx))


def test_s5_api_s_osetrenou_chybou_projde(browser):
    kurz = KURZ_API.replace("SHAPE", "Array.isArray(d) ? d : d.terminy").replace("CATCH", CATCH_OK)
    checks, notes, ctx = s5(browser, s5_site(kurz))
    assert checks == {"s5:terminy:polozky": True, "s5:terminy:chyba": True, "s5:poptavka:termin": True}, notes
    assert ctx["terminy"]["api"] is True and ctx["terminy"]["shape"] == "pole"


def test_s5_api_jen_objekt_najde_tvar(browser):
    kurz = KURZ_API.replace("SHAPE", "d.items").replace("CATCH", CATCH_OK)
    checks, notes, ctx = s5(browser, s5_site(kurz))
    assert checks["s5:terminy:polozky"] is True and ctx["terminy"]["shape"] == "objekt", notes


def test_s5_api_bez_osetreni_chyby_neprojde(browser):
    kurz = KURZ_API.replace("SHAPE", "d").replace("CATCH", "")
    checks, notes, _ = s5(browser, s5_site(kurz))
    assert checks["s5:terminy:polozky"] is True
    assert checks["s5:terminy:chyba"] is False, notes["s5:terminy:chyba"]


def test_s5_staticka_data_chyba_na(browser):
    checks, notes, ctx = s5(browser, s5_site(KURZ_STATIC))
    assert ctx["terminy"]["api"] is False
    assert checks["s5:terminy:polozky"] is True and checks["s5:terminy:chyba"] is None
    assert checks["s5:poptavka:termin"] is True, notes  # statická id: harness pošle první z nich
    assert "s5:terminy:chyba" not in cm.groups_of({**checks, "build": True}, "S5")["q_nove"]


def test_s5_bez_terminu_a_bez_termin_v_poptavce(browser):
    checks, notes, _ = s5(browser, s5_site("<section data-opora-section='obsah'><p>Lekce</p><a href='/kontakt'>Chci začít</a>"
                                           "</section>", extra="varianta: q.get('varianta') || undefined"))
    assert checks["s5:terminy:polozky"] is False and checks["s5:poptavka:termin"] is False
    assert checks["s5:terminy:chyba"] is None


def s6_pages(cenik_link=False, price=False, vybrat=False, redirect=True, variant=False):
    pages = s5_site(KURZ_STATIC, extra="termin: q.get('termin') || undefined"
                    + (", varianta: q.get('varianta') || undefined" if variant else ""))
    nav = NAV.replace("</nav>", " <a href='/cenik'>Ceník</a></nav>") if cenik_link else NAV
    for url in list(pages):
        pages[url] = pages[url].replace(NAV, nav)
    if price:
        pages["/kurz"] = pages["/kurz"].replace("Termíny (dočasně)", "Termíny – 990 Kč")
    if vybrat:
        pages["/kurz"] = pages["/kurz"].replace("</main>", "<section data-opora-section='v'><button>Vybrat</button></section></main>")
    pages["/cenik"] = ("<!doctype html><html><body><script>location.replace('/kurz')</script></body></html>" if redirect
                       else "<!doctype html><html><body><div id='root'></div></body></html>")
    return pages


def s6(browser, pages):
    def fn(page, ok, ctx):
        found = {}
        for url in cm.PAGES["S1"]:
            cm.goto(page, BASE, url)
            found[url] = cm.info(page)
        cm._s6(page, BASE, ok, found, list(found))
    return run_part(browser, pages, fn)


def test_s6_ciste_zruseni_projde(browser):
    checks, notes, _ = s6(browser, s6_pages())
    assert all(checks[n] for n in cm.EXPECTED["S6"]), notes


def test_s6_zbytky_ceniku_neprojdou(browser):
    checks, notes, _ = s6(browser, s6_pages(cenik_link=True, price=True, vybrat=True, redirect=False, variant=True))
    assert not any(checks[n] for n in cm.EXPECTED["S6"]), notes


def test_s6_rusi_kontroly_ceniku_a_varianty():
    for name in ("s2:stranka:/cenik", "s2:cenik:varianty", "s2:cenik:vybrat", "s2:menu_cenik", "s2:api:post",
                 "s3:oprava:cenik"):
        assert cm.valid_in(name, "S5") and not cm.valid_in(name, "S6"), name
    s6_names = cm.expected_names("S6")
    for keep in ("s2:cta_zacit", "s2:api:chyba500", "s3:oprava:aria", "s3:plan:faq", "s4x:paticka", "s4y:ukazka",
                 "s5:poptavka:termin", "s5:terminy:polozky"):
        assert keep in s6_names, keep
    assert "/cenik" not in cm.PAGES["S6"] and "/cenik" in cm.PAGES["S5"]
    g = cm.groups_of({"build": True, "test": True, "s5:poptavka:termin": True, "s6:bez_ceny": False, "s1:menu": True}, "S6")
    assert g["q_nove"] == ["s6:bez_ceny"] and set(g["q_regrese"]) == {"s5:poptavka:termin", "s1:menu"}


def test_zprava_s5_s6_realita_a_brief(tmp_path):
    import report_multi
    rows = []
    for arm, real in (("A", 2), ("C", 0), ("E", 1)):
        for s in cm.ORDER:
            checks = {"build": True, "test": True, "pravidla:h1:/": True}
            if s in ("S5", "S6"):
                checks.update({"s5:terminy:polozky": arm != "C", "s5:poptavka:termin": True})
            if s == "S6":
                checks["s6:bez_ceny"] = arm == "A"
            g = cm.groups_of(checks, s)
            rows.append({"prompt_id": f"{s}.{arm}", "rep": 0, "status": "ok", "grade": cm.grade_of(checks, g),
                         "latency_s": 60, "tool_calls": 10, "orientation": {"calls": 3, "tokens_in": 1000},
                         "cost": {"usd": 1.0, "c4_zbytecne": 0, "c5_mimo_zadani": 0},
                         "meta": {"session": s, "arm": arm, "checks": checks, "shots": [{"url": "/", "desktop": None}],
                                  **({"brief_questions": 2, "brief_rounds": 1} if arm == "E" else {})}})
        rows.append({"prompt_id": f"realita.{arm}", "rep": 0, "status": "ok", "grade": {"q_realita": real},
                     "meta": {"kind": "realita", "arm": arm, "session": "S5"}})
    (tmp_path / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    rep = report_multi.build(tmp_path)
    assert rep["final_session"] == "S6" and "A.r0" in rep["final_shots"]
    assert rep["per"]["S5.A"]["q_realita"] == 2 and rep["per"]["S5.C"]["q_realita"] == 0
    assert rep["per"]["S5.E"]["brief_questions"] == 2 and rep["per"]["S5.C"]["brief_questions"] is None
    assert any(x.startswith("Q-realita") for x in rep["summary"]["leads_over_C"])
    assert any(x.startswith("Q-nové S5–S6") for x in rep["summary"]["leads_over_C"])
    assert rep["summary"]["verdict"].startswith("Dominance OPORY prokázaná")
    html_text = report_multi.render(rep, tmp_path)
    assert "S6 E" in html_text and "Q-realita" in html_text and "otázek výslechu" in html_text and "po S6" in html_text
