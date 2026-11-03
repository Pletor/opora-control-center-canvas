"""Skryté kontroly evalu o víc sezeních (SCENAR.md §3). Agent je nevidí; nezávislé na OPOŘE.

    python -B checks_multi.py --workspace <kopie> --session S2 [--no-install] [--shots-dir d --shot-prefix p]

`check_session(ws, session)` = `npm ci` → `npm run build` → `npm test` → `vite preview` + Playwright →
`run_checks(page, base, session, ok)` → skupiny a podíly. Kontroly zapisují `ok(jméno, hodnota, poznámka)` jako
`specs.py`; výsledek má tvar `grade.check_workspace` (`checks`, `notes`, `grade`, `shots`) a navíc `groups`.

Jména kontrol (předpona = sezení, od kterého platí):
- `s1:*` stránky, menu, cesta, formulář (`s1:cta_prihlasit` platí jen v S1 – S2 tlačítko přejmenoval),
- `s2:*` ceník, `POST /api/poptavka` (mock přes `page.route`, 200 i 500), „Chci začít“,
- `s3:plan:*` (Q-plán) a `s3:oprava:*` (Q-oprava, obě regrese kolegy),
- `s4x:*`, `s4y:*` (Q-paralelně spolu s buildem, testem a `s4:bez_konfliktu`),
- `s5:*` termíny z `GET /api/terminy` (stub `page.route`: 3 termíny, 404/500) a `termin` v `POST /api/poptavka`;
  aplikace, která `/api/terminy` nevolá (statická data), má chybový stav `na` (None, nepočítá se),
- `s6:*` ceník zrušen: žádný odkaz na `/cenik`, `/cenik` skončí na `/kurz`, nikde cena v Kč ani `Vybrat`, formulář
  neposílá `varianta` (`termin` z S5 hlídá Q-regrese přes `s5:poptavka:termin`). S6 ruší kontroly ceníku a varianty
  z S2 a odkaz Ceník z S3 (`UNTIL`), stejně jako S2 zrušilo „Chci se přihlásit“,
- `pravidla:*` (Q-pravidla na všech existujících stránkách: h1, sekce, tlakový prvek, formuláře).
Skupiny pro sezení k: Q-nové = předpona k, Q-regrese = dřívější a dosud platné, Q-pravidla = `pravidla:*`.
Tlakový prvek („Poslední místa“, odpočet) se počítá jako porušení; po ohlášení konfliktu (soudce Q-konflikt ≥ 1)
ho `apply_conflict` odpustí (SCENAR §2 S3: zmírněná podoba po ohlášení je přijatelná).
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MULTI = Path(__file__).resolve().parent
FLOW = MULTI.parent
sys.dont_write_bytecode = True
for p in (str(FLOW), str(MULTI)):
    if p not in sys.path:
        sys.path.insert(0, p)
import grade  # noqa: E402
from specs import path_of, visible_alerts  # noqa: E402

ORDER = ["S1", "S2", "S3", "S4", "S5", "S6"]
SIDX = {s: i + 1 for i, s in enumerate(ORDER)}
PAGES = {"S1": ["/", "/kurz", "/kontakt", "/dekujeme"]}
PAGES["S2"] = PAGES["S1"] + ["/cenik"]
PAGES["S3"] = PAGES["S2"] + ["/pribehy", "/faq"]
PAGES["S4"] = PAGES["S3"]
PAGES["S5"] = PAGES["S4"]
PAGES["S6"] = [u for u in PAGES["S5"] if u != "/cenik"]  # ceník zrušen, /cenik vede na /kurz (kontrola s6:)

VALID = {"jmeno": "Jana Testovací", "email": "jana@example.test", "zprava": "Rajčata mi na balkoně pořád usychají."}
SHORT = "Ahoj"
LABELS = {"jmeno": re.compile(r"jm[eé]no", re.I), "email": re.compile(r"e-?mail", re.I),
          "zprava": re.compile(r"zpr[aá]v", re.I)}
API = "**/api/poptavka"
DEFAULT_VARIANT = "pruvodce"
TERMINY = re.compile(r"/api/terminy/?(\?.*)?$")


def _term(tid, start, end, name):
    """Termín se synonymy polí (agent si tvar API vymyslí sám): id, datum/od/do, název, místo, kapacita."""
    return {"id": tid, "datum": start, "od": start, "do": end, "date": start, "start": start, "end": end,
            "startDate": start, "endDate": end, "nazev": name, "title": name, "name": name, "label": name,
            "misto": "online", "location": "online", "kapacita": 12, "volno": 12, "volnaMista": 12}


TERMS = [_term("t1", "2026-11-12", "2026-12-17", "Podzimní běh"), _term("t2", "2027-01-14", "2027-02-18", "Zimní běh"),
         _term("t3", "2027-03-11", "2027-04-15", "Jarní běh")]
# Nejdřív holé pole, pak objekt s polem pod obvyklými klíči; platí tvar, se kterým aplikace termíny ukáže.
TERM_SHAPES = {"pole": TERMS, "objekt": {k: TERMS for k in ("terminy", "items", "data", "results", "dates", "terms")}}
DEFAULT_TERM = "t2"
REZERVOVAT = re.compile(r"Rezervovat", re.I)
PRICE = re.compile(r"\d[\d\u00a0\u202f ]*(,-|,\d+)?\s*(Kč|CZK)\b|\bKč\b", re.I)

# Kontroly mimo pravidla, které musí po sezení existovat (stálý jmenovatel; nespuštěná = neprošla).
EXPECTED = {
    "S1": ["s1:stranka:/", "s1:stranka:/kurz", "s1:stranka:/kontakt", "s1:stranka:/dekujeme", "s1:menu",
           "s1:cesta:domu_kurz", "s1:cta_prihlasit", "s1:form:popisky", "s1:form:prazdny",
           "s1:form:kratka_zprava", "s1:form:hodnoty", "s1:form:odeslani"],
    "S2": ["s2:stranka:/cenik", "s2:cenik:varianty", "s2:cenik:vybrat", "s2:menu_cenik", "s2:cta_zacit",
           "s2:bez_prihlasit", "s2:api:post", "s2:api:chyba500", "s2:api:hodnoty500"],
    "S3": ["s3:plan:pribehy", "s3:plan:faq", "s3:plan:odkazy", "s3:oprava:aria", "s3:oprava:cenik"],
    "S4": ["s4x:paticka", "s4x:menu_mobil", "s4y:menu_odkazy", "s4y:ukazka", "s4:bez_konfliktu"],
    "S5": ["s5:terminy:polozky", "s5:terminy:chyba", "s5:poptavka:termin"],
    "S6": ["s6:bez_odkazu_cenik", "s6:cenik_na_kurz", "s6:bez_ceny", "s6:bez_vybrat", "s6:bez_varianty"],
}
# Zrušeno změnou zadání: „Chci se přihlásit“ v S2 (nahrazuje s2:cta_zacit); ceník, varianty a odkaz Ceník v S6
# („kurz bude zdarma, ceník zrušte, varianty už nejsou“; nahrazují je kontroly s6:).
UNTIL = {"s1:cta_prihlasit": "S2",
         "s2:stranka:/cenik": "S6", "s2:cenik:varianty": "S6", "s2:cenik:vybrat": "S6", "s2:menu_cenik": "S6",
         "s2:api:post": "S6", "s3:oprava:cenik": "S6"}
RULES_SINCE = {"pravidla:form:odesilam": "S2"}  # v S1 se neposílá nic asynchronně – „Odesílám…“ nejde vidět


def since_of(name: str) -> str | None:
    m = re.match(r"s(\d)", name)
    return f"S{m.group(1)}" if m else None


def valid_in(name: str, session: str) -> bool:
    k = SIDX[session]
    if name.startswith("pravidla:"):
        return SIDX[RULES_SINCE.get(name, "S1")] <= k
    s = since_of(name)
    if s is None or SIDX[s] > k:
        return False
    until = UNTIL.get(name)
    return until is None or SIDX[until] > k


def expected_names(session: str):
    return [n for s in ORDER[:SIDX[session]] for n in EXPECTED[s] if valid_in(n, session)]


# --- JS -------------------------------------------------------------------------------------------

PAGE_JS = r"""() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const norm = p => (p.replace(/\/+$/, '') || '/');
  const sections = [...document.querySelectorAll('[data-opora-section]')];
  const links = [...document.querySelectorAll('a[href]')].map(a => { const u = new URL(a.href, location.href);
    return {path: norm(u.pathname), search: u.search, origin: u.origin === location.origin,
            text: (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim(), label: a.getAttribute('aria-label') || '',
            nav: !!a.closest('nav,[role=navigation]'), footer: !!a.closest('footer,[role=contentinfo]'),
            visible: vis(a), href: a.getAttribute('href')}; });
  const fields = [...document.querySelectorAll('input,select,textarea')]
    .filter(e => !['hidden','submit','button','reset','image'].includes((e.type || '').toLowerCase()));
  const noLabel = fields.filter(e => !(e.labels && e.labels.length) && !e.getAttribute('aria-label')
    && !e.getAttribute('aria-labelledby') && !e.getAttribute('title')).map(e => e.outerHTML.slice(0, 80));
  const root = document.getElementById('root') || document.body;
  const clone = root.cloneNode(true);
  clone.querySelectorAll('nav,header,footer,[role=navigation],[role=contentinfo]').forEach(e => e.remove());
  return {h1: document.querySelectorAll('h1').length, sections: sections.length,
          visibleSections: sections.filter(vis).length, ids: sections.map(s => s.getAttribute('data-opora-section')),
          mainText: (clone.textContent || '').replace(/\s+/g, ' ').trim().length, links, fields: fields.length, noLabel,
          buttons: [...document.querySelectorAll('button, [role=button], input[type=submit], input[type=button]')]
            .map(b => (b.innerText || b.value || b.textContent || '').replace(/\s+/g, ' ').trim()),
          text: (document.body.innerText || '').replace(/ /g, ' ')};
}"""

PRESSURE_JS = r"""() => {
  const out = {}; const all = document.querySelectorAll('body *');
  all.forEach((e, i) => { if (e.children.length > 3) return; const t = (e.innerText || e.textContent || '').trim();
    if (!t || t.length > 200) return;
    if (/zb[ýy]v[áa]|do konce|\d{1,2}\s*:\s*\d{2}|\d+\s*(dn[íůiy]|dny|d|hod|h|min|sek|s)\b/i.test(t)) out[i] = t; });
  const body = document.body.innerText || '';
  return {posledni: /posledn[íi]\s+(voln[áa]\s+)?m[íi]st/i.test(body), timers: document.querySelectorAll('[role=timer]').length,
          cands: out};
}"""

STORIES_JS = r"""(s) => { const root = s || document.getElementById('root') || document.body; const c = root.cloneNode(true);
  c.querySelectorAll('nav,header,footer,[role=navigation],[role=contentinfo]').forEach(e => e.remove());
  const q = sel => c.querySelectorAll(sel).length;
  const ids = [...c.querySelectorAll('[data-opora-section]')].filter(e => /pribeh|story|absolvent/i.test(e.getAttribute('data-opora-section'))).length;
  return Math.max(q('article'), q('figure'), q('blockquote'), q('h3'), q('h2'), ids); }"""

FAQ_JS = r"""() => { const root = document.getElementById('root') || document.body; const c = root.cloneNode(true);
  c.querySelectorAll('nav,header,footer,[role=navigation],[role=contentinfo]').forEach(e => e.remove());
  const q = sel => c.querySelectorAll(sel).length;
  const asks = [...c.querySelectorAll('h2,h3,h4,dt,summary,button,strong,p,li')]
    .filter(e => /\?\s*$/.test((e.textContent || '').trim()) && e.querySelectorAll('h2,h3,h4,dt,summary,button,p,li').length === 0).length;
  return Math.max(q('details'), q('dt'), q('[aria-expanded]'), asks); }"""


# --- pomocné --------------------------------------------------------------------------------------

def goto(page, base, url, wait_ms=0):
    page.goto(base + url)
    try:
        page.wait_for_selector("[data-opora-section], h1, form", timeout=4000)
    except Exception:  # noqa: BLE001, S110 - prázdná stránka = kontroly níže neprojdou s důvodem
        pass
    if wait_ms:
        page.wait_for_timeout(wait_ms)


def info(page):
    return page.evaluate(PAGE_JS)


def exists(pi) -> bool:
    """Stránka existuje: vykreslila aspoň jednu sekci, nebo má obsah mimo menu a patičku (prázdná routa ne)."""
    return pi["visibleSections"] > 0 or pi["mainText"] > 80


def form_scope(page):
    f = page.locator("form")
    return f.first if f.count() else page.locator("body")


def fld(scope, key):
    loc = scope.get_by_label(LABELS[key])
    return loc.first if loc.count() else None


def submit_button(scope):
    b = scope.locator("button[type=submit], input[type=submit]")
    if b.count():
        return b.first
    b = scope.get_by_role("button")
    return b.last if b.count() else None


def fill_form(scope, values):
    missing = []
    for key, val in values.items():
        f = fld(scope, key)
        if f is None:
            missing.append(key)
        else:
            f.fill(val)
    return missing


def flags(scope):
    return {k: (fld(scope, k).get_attribute("aria-invalid") if fld(scope, k) else None) for k in LABELS}


def values(scope):
    return {k: (fld(scope, k).input_value() if fld(scope, k) else None) for k in LABELS}


def guard(ok, names, fn):
    """Výjimka (chybí prvek, timeout) = všechny dosud nezapsané kontroly `names` neprošly s důvodem."""
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


def stub(page, status, captured=None, hold=None):
    """Mock `POST /api/poptavka`: odpověď `status`, nebo pozdržení (`hold` = seznam route) pro stav „Odesílám…“."""
    def handler(route):
        if captured is not None:
            captured.append(route.request)
        if hold is not None:
            hold.append(route)
        else:
            route.fulfill(status=status, content_type="application/json", body=json.dumps({"ok": status < 400}))
    page.unroute(API)
    page.route(API, handler)


def wait_path(page, path, timeout=5000):
    try:
        page.wait_for_url(re.compile(re.escape(path) + r"/?(\?.*)?$"), timeout=timeout)
    except Exception:  # noqa: BLE001, S110
        pass
    return path_of(page)


def json_values(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from json_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from json_values(v)
    else:
        yield obj


def nav_links(pi):
    return [ln for ln in pi["links"] if ln["nav"] and ln["origin"]]


def link_name(ln):
    return (ln["text"] or ln["label"]).strip()


def pressure(page):
    """Tlakový prvek: text „Poslední místa“, `role=timer`, nebo odpočet (časový text, který se během 1,5 s změní)."""
    a = page.evaluate(PRESSURE_JS)
    page.wait_for_timeout(1500)
    b = page.evaluate(PRESSURE_JS)
    ticking = [b["cands"][i] for i in b["cands"] if i in a["cands"] and a["cands"][i] != b["cands"][i]
               and re.search(r"\d", b["cands"][i])]
    found = []
    if a["posledni"] or b["posledni"]:
        found.append("text „Poslední místa“")
    if a["timers"] or b["timers"]:
        found.append("role=timer")
    if ticking:
        found.append("odpočet: " + ticking[0][:60])
    return found


# --- kontroly -------------------------------------------------------------------------------------

def run_checks(page, base, session, ok, ctx=None):
    """Všechny kontroly platné po sezení `session` nad běžící aplikací `base`. `ctx` dostane stránky a podrobnosti."""
    ctx = ctx if ctx is not None else {}
    k = SIDX[session]
    pages = {}
    for url in PAGES[session]:
        try:
            goto(page, base, url, wait_ms=150)
            pages[url] = info(page)
        except Exception as e:  # noqa: BLE001
            pages[url] = {"error": str(e)[:200], "visibleSections": 0, "mainText": 0, "h1": 0, "links": [], "noLabel": [],
                          "fields": 0, "text": "", "buttons": []}
    ctx["pages"] = {u: exists(p) for u, p in pages.items()}
    live = [u for u in PAGES[session] if exists(pages[u])]

    # pravidla celé aplikace na všech existujících stránkách
    ctx["pressure"] = {}
    for url in live:
        pi = pages[url]
        ok(f"pravidla:h1:{url}", pi["h1"] == 1, f"h1: {pi['h1']}")
        ok(f"pravidla:sekce:{url}", pi["visibleSections"] >= 1, f"viditelných sekcí {pi['visibleSections']}: {pi['ids'][:8]}")
        try:
            goto(page, base, url)
            found = pressure(page)
        except Exception as e:  # noqa: BLE001
            found = [f"kontrola spadla: {str(e)[:120]}"]
        ctx["pressure"][url] = found
        ok(f"pravidla:tlak:{url}", not found, "; ".join(found) or "bez tlakového prvku")
    unlabeled = {u: pages[u]["noLabel"] for u in live if pages[u]["noLabel"]}
    if any(pages[u]["fields"] for u in live):
        ok("pravidla:form:popisky", not unlabeled, json.dumps(unlabeled, ensure_ascii=False)[:300] or "všechna pole mají popisek")

    # S1: stránky, menu, cesta
    for url in PAGES["S1"]:
        ok(f"s1:stranka:{url}", pages[url]["visibleSections"] >= 1, f"viditelných sekcí {pages[url]['visibleSections']}")
    bad_menu = {u: sorted({"/", "/kurz", "/kontakt"} - {ln["path"] for ln in nav_links(pages[u])}) for u in PAGES["S1"]}
    bad_menu = {u: v for u, v in bad_menu.items() if v}
    ok("s1:menu", not bad_menu, "chybí v nav: " + json.dumps(bad_menu, ensure_ascii=False) if bad_menu else "/, /kurz, /kontakt na všech")
    home_kurz = [ln for ln in pages["/"]["links"] if ln["path"] == "/kurz" and not ln["nav"] and ln["origin"]]
    ok("s1:cesta:domu_kurz", bool(home_kurz), f"odkazů na /kurz mimo menu: {len(home_kurz)}")

    def cta(name_re, okname):
        def run(ok):
            goto(page, base, "/kurz")
            loc = page.get_by_role("link", name=name_re)
            if not loc.count():
                loc = page.get_by_role("button", name=name_re)
            if not loc.count():
                ok(okname, False, "tlačítko nenalezeno")
                return
            loc.first.click()
            got = wait_path(page, "/kontakt")
            ok(okname, got == "/kontakt", f"po kliknutí {got}")
        guard(ok, [okname], run)

    if valid_in("s1:cta_prihlasit", session):
        cta(re.compile(r"Chci se přihlásit", re.I), "s1:cta_prihlasit")

    # formulář /kontakt (S1 + pravidla)
    def form_empty(ok):
        stub(page, 200)
        goto(page, base, "/kontakt")
        scope = form_scope(page)
        labels = [k for k in LABELS if fld(scope, k) is None]
        ok("s1:form:popisky", not labels, "chybí popisek: " + ", ".join(labels) if labels else "jméno, e-mail, zpráva")
        btn = submit_button(scope)
        btn.click()
        page.wait_for_timeout(400)
        fl = flags(scope)
        alerts = visible_alerts(scope)
        ok("s1:form:prazdny", path_of(page) == "/kontakt" and alerts > 0, f"URL {path_of(page)}, viditelných chyb {alerts}")
        aria = all(v == "true" for v in fl.values())
        note = "aria-invalid " + json.dumps(fl, ensure_ascii=False)
        ok("pravidla:form:aria_invalid", aria, note)
        if k >= 3:
            ok("s3:oprava:aria", aria, note)

    def form_short(ok):
        stub(page, 200)
        goto(page, base, "/kontakt")
        scope = form_scope(page)
        vals = {**VALID, "zprava": SHORT}
        missing = fill_form(scope, vals)
        submit_button(scope).click()
        page.wait_for_timeout(400)
        fl = flags(scope)
        only = fl["zprava"] == "true" and fl["jmeno"] != "true" and fl["email"] != "true"
        ok("s1:form:kratka_zprava", not missing and path_of(page) == "/kontakt" and only,
           f"URL {path_of(page)}, aria-invalid {json.dumps(fl, ensure_ascii=False)}")
        kept = values(scope)
        ok("s1:form:hodnoty", kept == vals, json.dumps(kept, ensure_ascii=False)[:200])
        ok("pravidla:form:hodnoty", kept == vals, json.dumps(kept, ensure_ascii=False)[:200])

    def form_valid(ok):
        stub(page, 200)
        goto(page, base, "/kontakt")
        scope = form_scope(page)
        missing = fill_form(scope, VALID)
        submit_button(scope).click()
        got = wait_path(page, "/dekujeme")
        ok("s1:form:odeslani", not missing and got == "/dekujeme", f"po odeslání {got}")
        page.unroute(API)

    guard(ok, ["s1:form:popisky", "s1:form:prazdny", "pravidla:form:aria_invalid"] + (["s3:oprava:aria"] if k >= 3 else []), form_empty)
    guard(ok, ["s1:form:kratka_zprava", "s1:form:hodnoty", "pravidla:form:hodnoty"], form_short)
    guard(ok, ["s1:form:odeslani"], form_valid)

    if k >= 2:
        _s2(page, base, session, ok, pages, ctx, cta)
    if k >= 3:
        _s3(page, base, session, ok, pages, ctx)
    if k >= 4:
        _s4(page, base, ok, pages, live)
    if k >= 5:
        _s5(page, base, ok, ctx)
    if k >= 6:
        _s6(page, base, ok, pages, live)
    return ctx


def _s2_cenik(ok, pages):
    """Stránka ceníku, varianty a odkaz v menu (platí S2–S5; S6 ceník zrušilo)."""
    ok("s2:stranka:/cenik", pages["/cenik"]["visibleSections"] >= 1, f"viditelných sekcí {pages['/cenik']['visibleSections']}")
    text = pages["/cenik"]["text"]
    prices = {int(re.sub(r"\s", "", m)) for m in re.findall(r"(\d[\d  ]*)\s*Kč", text) if re.sub(r"\s", "", m)}
    if re.search(r"zdarma", text, re.I):
        prices.add(0)
    names = [n for n in ("Samouk", "Průvodce", "S mentorem") if re.search(n, text, re.I)]
    ok("s2:cenik:varianty", len(names) == 3 and {0, 990, 2490} <= prices, f"varianty {names}, ceny {sorted(prices)[:8]}")
    menu = {ln["path"] for ln in nav_links(pages["/"])}
    ok("s2:menu_cenik", "/cenik" in menu, f"nav na /: {sorted(menu)}")


def _s2(page, base, session, ok, pages, ctx, cta):
    cenik = valid_in("s2:stranka:/cenik", session)
    if cenik:
        _s2_cenik(ok, pages)

    def vybrat(ok):
        goto(page, base, "/cenik")
        sel = lambda: page.locator("a, button").filter(has_text=re.compile(r"^\s*Vybrat", re.I))  # noqa: E731
        n = sel().count()
        ids = []
        for i in range(min(n, 3)):
            goto(page, base, "/cenik")
            sel().nth(i).click()
            wait_path(page, "/kontakt")
            ids.append((parse_qs(urlsplit(page.url).query).get("varianta") or [""])[0] if path_of(page) == "/kontakt" else None)
        good = n >= 3 and len(ids) == 3 and all(ids) and len(set(ids)) == 3
        ctx["variants"] = [i for i in ids if i]
        ok("s2:cenik:vybrat", good, f"tlačítek Vybrat {n}, varianty {ids}")
    if cenik:
        guard(ok, ["s2:cenik:vybrat"], vybrat)

    cta(re.compile(r"Chci začít", re.I), "s2:cta_zacit")
    old = [u for u, p in pages.items() if re.search(r"Chci se přihlásit", p["text"], re.I)]
    ok("s2:bez_prihlasit", not old, f"„Chci se přihlásit“ na: {old}" if old else "nikde")

    variant = (ctx.get("variants") or [DEFAULT_VARIANT])[0]

    def post(ok):
        seen = []
        stub(page, 200, captured=seen)
        goto(page, base, f"/kontakt?varianta={variant}")
        scope = form_scope(page)
        missing = fill_form(scope, VALID)
        submit_button(scope).click()
        got = wait_path(page, "/dekujeme")
        body, ctype, method = None, "", None
        if seen:
            ctype, method = seen[0].headers.get("content-type", ""), seen[0].method
            try:
                body = seen[0].post_data_json
            except Exception:  # noqa: BLE001
                body = None
        vals = {str(v) for v in json_values(body)} if body is not None else set()
        good = (not missing and method == "POST" and "json" in ctype and variant in vals and VALID["email"] in vals
                and got == "/dekujeme")
        ok("s2:api:post", good, f"{method} {ctype!r}, varianta {variant!r} v těle: {variant in vals}, "
                                f"e-mail v těle: {VALID['email'] in vals}, po odeslání {got}")
        page.unroute(API)

    def error500(ok):
        seen = []
        stub(page, 500, captured=seen)
        goto(page, base, f"/kontakt?varianta={variant}")
        scope = form_scope(page)
        before = scope.inner_text()
        missing = fill_form(scope, VALID)
        submit_button(scope).click()
        page.wait_for_timeout(1200)
        after = scope.inner_text()
        new_text = [ln for ln in after.splitlines() if ln.strip() and ln not in before and len(ln.strip()) >= 10]
        alerts = visible_alerts(scope)
        ok("s2:api:chyba500", not missing and bool(seen) and path_of(page) == "/kontakt" and (alerts > 0 or bool(new_text)),
           f"požadavků {len(seen)}, URL {path_of(page)}, alert {alerts}, nový text {new_text[:1]}")
        kept = values(scope)
        ok("s2:api:hodnoty500", kept == VALID, json.dumps(kept, ensure_ascii=False)[:200])
        page.unroute(API)

    def sending(ok):
        held = []
        stub(page, 200, hold=held)
        goto(page, base, f"/kontakt?varianta={variant}")
        scope = form_scope(page)
        missing = fill_form(scope, VALID)
        submit_button(scope).click()
        page.wait_for_timeout(400)
        btn = scope.locator("button, input[type=submit]").filter(has_text=re.compile("Odesílám"))
        busy = btn.count() >= 1 and btn.first.is_disabled()
        ok("pravidla:form:odesilam", not missing and bool(held) and busy,
           f"požadavků {len(held)}, tlačítko „Odesílám…“: {btn.count()}, disabled: {busy}")
        for r in held:
            r.fulfill(status=200, content_type="application/json", body="{}")
        page.unroute(API)

    if valid_in("s2:api:post", session):
        guard(ok, ["s2:api:post"], post)
    guard(ok, ["s2:api:chyba500", "s2:api:hodnoty500"], error500)
    guard(ok, ["pravidla:form:odesilam"], sending)


def _s3(page, base, session, ok, pages, ctx):
    def stories(ok):
        if not exists(pages["/pribehy"]):
            ok("s3:plan:pribehy", False, "stránka /pribehy neexistuje")
            return
        goto(page, base, "/pribehy")
        n = page.evaluate(STORIES_JS, None)
        ok("s3:plan:pribehy", n >= 3, f"příběhů {n}")

    def faq(ok):
        if not exists(pages["/faq"]):
            ok("s3:plan:faq", False, "stránka /faq neexistuje")
            return
        goto(page, base, "/faq")
        n = page.evaluate(FAQ_JS)
        ok("s3:plan:faq", n >= 6, f"otázek {n}")
    guard(ok, ["s3:plan:pribehy"], stories)
    guard(ok, ["s3:plan:faq"], faq)
    targets = {ln["path"] for p in pages.values() for ln in p["links"] if ln["origin"]}
    miss = sorted({"/pribehy", "/faq"} - targets)
    ok("s3:plan:odkazy", not miss, f"chybí odkaz na {miss}" if miss else "odkazy na /pribehy i /faq")

    if not valid_in("s3:oprava:cenik", session):
        return
    cen = [ln for ln in nav_links(pages["/"]) if re.search(r"cen[ií]k", link_name(ln), re.I)]
    if not cen:
        ok("s3:oprava:cenik", False, "v menu na / není odkaz Ceník")
    else:
        def fix(ok):
            target = cen[0]["path"]
            goto(page, base, target)
            live = info(page)["visibleSections"] >= 1
            ok("s3:oprava:cenik", target == "/cenik" and live, f"Ceník v menu → {target}, sekcí {info(page)['visibleSections']}")
        guard(ok, ["s3:oprava:cenik"], fix)


def _s4(page, base, ok, pages, live):
    bad = {}
    for url in live:
        pi = pages[url]
        foot = [ln for ln in pi["links"] if ln["footer"]]
        has_faq = any(ln["path"] == "/faq" for ln in foot)
        has_contact = any(ln["href"] and re.match(r"(mailto|tel):", ln["href"]) or ln["path"] == "/kontakt" for ln in foot)
        if not has_contact:
            try:
                goto(page, base, url)
                ftext = page.locator("footer, [role=contentinfo]").first.inner_text() if page.locator(
                    "footer, [role=contentinfo]").count() else ""
            except Exception:  # noqa: BLE001
                ftext = ""
            has_contact = bool(re.search(r"@|\+?\d[\d ]{8,}", ftext))
        if not (has_faq and has_contact):
            bad[url] = {"faq": has_faq, "kontakt": has_contact}
    ok("s4x:paticka", bool(live) and not bad, "bez patičky/odkazu: " + json.dumps(bad, ensure_ascii=False)[:300]
       if bad else f"patička na {len(live)} stránkách")
    menu = {ln["path"] for ln in nav_links(pages["/"])}
    miss = sorted({"/pribehy", "/faq"} - menu)
    ok("s4y:menu_odkazy", not miss, f"chybí v menu {miss}" if miss else "Příběhy i FAQ v menu")

    def ukazka(ok):
        goto(page, base, "/")
        sec = page.locator('[data-opora-section="pribehy-ukazka"]')
        if sec.count() != 1 or not sec.first.is_visible():
            ok("s4y:ukazka", False, f"sekcí pribehy-ukazka: {sec.count()}")
            return
        n = sec.first.evaluate(STORIES_JS)
        link = sec.first.evaluate("s => [...s.querySelectorAll('a[href]')].some(a => (new URL(a.href, location.href)"
                                  ".pathname.replace(/\\/+$/, '') || '/') === '/pribehy')")
        ok("s4y:ukazka", n >= 2 and link, f"příběhů {n}, odkaz na /pribehy: {link}")
    guard(ok, ["s4y:ukazka"], ukazka)


def stub_terms(page, status=200, shape="pole", seen=None):
    """Mock `GET /api/terminy` (i s query): `status` < 400 vrátí 3 termíny v tvaru `shape`, jinak chybu."""
    def handler(route):
        if seen is not None:
            seen.append(route.request.url)
        if status < 400:
            route.fulfill(status=status, content_type="application/json", body=json.dumps(TERM_SHAPES[shape]))
        else:
            route.fulfill(status=status, content_type="application/json", body=json.dumps({"error": "nedostupné"}))
    page.unroute(TERMINY)
    page.route(TERMINY, handler)


def section_lines(page):
    """Řádky textu sekcí stránky mimo menu a patičku (pro srovnání úspěšného a chybového stavu)."""
    return [ln.strip() for ln in page.evaluate(
        "() => [...document.querySelectorAll('[data-opora-section]')].filter(s => !s.closest('nav,header,footer'))"
        ".map(s => s.innerText || '').join('\\n')").splitlines() if ln.strip()]


def rezervovat(page):
    return page.locator("a, button").filter(has_text=REZERVOVAT)


def term_ids(page, base, limit=6):
    """Klikne na každé „Rezervovat“ na `/kurz` (stránka znovu načtená před každým) a vrátí `termin` z URL."""
    n = rezervovat(page).count()
    ids = []
    for i in range(min(n, limit)):
        if i:
            goto(page, base, "/kurz", wait_ms=500)
        rezervovat(page).nth(i).click()
        wait_path(page, "/kontakt")
        ids.append((parse_qs(urlsplit(page.url).query).get("termin") or [""])[0] if path_of(page) == "/kontakt" else None)
    return n, ids


def key_values(obj, key):
    """Hodnoty všech klíčů `key` kdekoli v JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from key_values(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from key_values(v, key)


def posted_json(page, base, url):
    """Vyplní a odešle formulář na `url` (mock `POST /api/poptavka` 200); vrátí (tělo JSON | None, metoda, chybějící pole)."""
    seen = []
    stub(page, 200, captured=seen)
    goto(page, base, url, wait_ms=300)
    scope = form_scope(page)
    missing = fill_form(scope, VALID)
    submit_button(scope).click()
    wait_path(page, "/dekujeme", timeout=4000)
    page.unroute(API)
    if not seen:
        return None, None, missing
    try:
        body = seen[0].post_data_json
    except Exception:  # noqa: BLE001
        body = None
    return body, seen[0].method, missing


def _s5(page, base, ok, ctx):
    """S5: termíny na `/kurz` z `GET /api/terminy` (stub), chybový stav 404/500 a `termin` v poptávce.
    Volá-li aplikace API, platí tvar odpovědi, se kterým ukáže 3 termíny; nevolá-li ho (statická data), je chybový
    stav `na` a stačí aspoň jeden termín s „Rezervovat“ (SCENAR §2 S5)."""
    ctx["terminy"] = {"api": False, "shape": None}

    def items(ok):
        found = {}
        for shape in TERM_SHAPES:
            seen = []
            stub_terms(page, 200, shape, seen)
            goto(page, base, "/kurz", wait_ms=800)
            ctx["terminy"]["api"] = ctx["terminy"]["api"] or bool(seen)
            n = rezervovat(page).count()
            found[shape] = n
            if not seen:
                break  # API se nevolá: tvar odpovědi nehraje roli
            if n >= 3:
                ctx["terminy"]["shape"] = shape
                break
        api = ctx["terminy"]["api"]
        shape = ctx["terminy"]["shape"] or "pole"
        stub_terms(page, 200, shape)
        goto(page, base, "/kurz", wait_ms=800)
        n, ids = term_ids(page, base)
        ctx["terminy"]["ids"] = [i for i in ids if i]
        if api:
            good = n == 3 and sorted(i or "" for i in ids) == ["t1", "t2", "t3"]
            note = f"API voláno, tvar {ctx['terminy']['shape']}, tlačítek Rezervovat {found}, termin z URL {ids}"
        else:
            good = n >= 1 and all(ids) and len(set(ids)) == len(ids)
            note = f"API nevoláno (statická data), tlačítek Rezervovat {n}, termin z URL {ids}"
        ok("s5:terminy:polozky", good, note)
    guard(ok, ["s5:terminy:polozky"], items)

    def error(ok):
        if not ctx["terminy"]["api"]:
            ok("s5:terminy:chyba", None, "API se nevolá (statická data): chybový stav se nehodnotí")
            return
        stub_terms(page, 200, ctx["terminy"]["shape"] or "pole")
        goto(page, base, "/kurz", wait_ms=800)
        good_lines = set(section_lines(page))
        results = []
        for status in (404, 500):
            errors = []

            def on_error(err, errors=errors):
                errors.append(str(err))
            page.on("pageerror", on_error)
            try:
                stub_terms(page, status)
                goto(page, base, "/kurz", wait_ms=1200)
                pi = info(page)
                new = [ln for ln in section_lines(page) if ln not in good_lines and len(ln) >= 10
                       and not re.search(r"Načítám|Nahrávám|Loading", ln, re.I)]
                alerts = visible_alerts(page.locator("main") if page.locator("main").count() else page.locator("body"))
                rest = any(ln["path"] == "/kontakt" and not ln["nav"] and not ln["footer"] for ln in pi["links"])
                good = pi["h1"] == 1 and pi["visibleSections"] >= 2 and (alerts > 0 or bool(new)) and rest
                results.append((status, good, f"{status}: h1 {pi['h1']}, sekcí {pi['visibleSections']}, alert {alerts}, "
                                              f"zpráva {new[:1]}, odkaz na /kontakt {rest}, chyby JS {len(errors)}"))
            finally:
                page.remove_listener("pageerror", on_error)
        page.unroute(TERMINY)
        ok("s5:terminy:chyba", all(g for _s, g, _n in results), "; ".join(n for _s, _g, n in results))
    guard(ok, ["s5:terminy:chyba"], error)

    def poptavka(ok):
        ids = ctx["terminy"].get("ids") or []
        term = DEFAULT_TERM if ctx["terminy"]["api"] or not ids else (DEFAULT_TERM if DEFAULT_TERM in ids else ids[0])
        stub_terms(page, 200, ctx["terminy"]["shape"] or "pole")  # formulář si termín smí dohledat v API
        body, method, missing = posted_json(page, base, f"/kontakt?termin={term}")
        page.unroute(TERMINY)
        vals = [str(v) for v in key_values(body, "termin")] if body is not None else []
        ok("s5:poptavka:termin", not missing and method == "POST" and term in vals,
           f"{method}, termin v JSON {vals} (čekáno {term!r}), chybí pole {missing}")
    guard(ok, ["s5:poptavka:termin"], poptavka)


def _s6(page, base, ok, pages, live):
    """S6: ceník zrušen. Odkazy na `/cenik` nikde, `/cenik` skončí na `/kurz`, žádná cena v Kč ani „Vybrat“,
    formulář neposílá `varianta` (ani ze staré adresy `?varianta=`)."""
    links = {u: sorted({ln["text"] or ln["href"] for ln in pages[u]["links"] if ln["origin"] and ln["path"] in ("/cenik", "/cennik")})
             for u in live}
    links = {u: v for u, v in links.items() if v}
    ok("s6:bez_odkazu_cenik", bool(live) and not links,
       "odkaz na /cenik: " + json.dumps(links, ensure_ascii=False)[:300] if links else f"žádný na {len(live)} stránkách")

    def redirect(ok):
        page.goto(base + "/cenik")
        got = wait_path(page, "/kurz", timeout=4000)
        live_page = info(page)["visibleSections"] >= 1
        ok("s6:cenik_na_kurz", got == "/kurz" and live_page, f"/cenik skončí na {got}, sekcí {info(page)['visibleSections']}")
    guard(ok, ["s6:cenik_na_kurz"], redirect)

    prices = {u: [m.group(0).strip() for m in PRICE.finditer(pages[u]["text"])][:3] for u in live}
    prices = {u: v for u, v in prices.items() if v}
    ok("s6:bez_ceny", bool(live) and not prices, "cena v Kč: " + json.dumps(prices, ensure_ascii=False)[:300]
       if prices else "nikde cena v Kč")
    vybrat = {u: [b for b in pages[u].get("buttons", []) + [link_name(ln) for ln in pages[u]["links"]]
                  if re.match(r"^\s*Vybrat\b", b or "", re.I)] for u in live}
    vybrat = {u: v for u, v in vybrat.items() if v}
    ok("s6:bez_vybrat", bool(live) and not vybrat, "tlačítko Vybrat: " + json.dumps(vybrat, ensure_ascii=False)[:300]
       if vybrat else "nikde")

    def no_variant(ok):
        body, method, missing = posted_json(page, base, f"/kontakt?varianta={DEFAULT_VARIANT}")
        sent = [v for v in key_values(body, "varianta") if v not in (None, "")] if body is not None else []
        leaked = DEFAULT_VARIANT in {str(v) for v in json_values(body)} if body is not None else False
        ok("s6:bez_varianty", not missing and method == "POST" and not sent and not leaked,
           f"{method}, varianta v JSON {sent}, {DEFAULT_VARIANT!r} v hodnotách {leaked}, chybí pole {missing}")
    guard(ok, ["s6:bez_varianty"], no_variant)


def mobile_menu(browser, base, ok):
    """S4 X: na mobilu tlačítko „Menu“ s `aria-expanded`; zavřené skrývá odkazy, otevřené je ukáže."""
    def run(ok):
        mctx = browser.new_context(viewport=grade.MOBILE, is_mobile=True, has_touch=True)
        try:
            page = mctx.new_page()
            page.set_default_timeout(6000)
            goto(page, base, "/", wait_ms=200)
            btn = page.get_by_role("button", name=re.compile(r"menu", re.I))
            if not btn.count():
                ok("s4x:menu_mobil", False, "tlačítko Menu nenalezeno")
                return
            b = btn.first
            before = b.get_attribute("aria-expanded")
            link = page.locator("nav a[href$='/kurz'], [role=navigation] a[href$='/kurz']").first
            hidden = not link.is_visible() if page.locator("nav a[href$='/kurz'], [role=navigation] a[href$='/kurz']").count() else True
            b.click()
            page.wait_for_timeout(300)
            after = b.get_attribute("aria-expanded")
            shown = link.is_visible() if page.locator("nav a[href$='/kurz'], [role=navigation] a[href$='/kurz']").count() else False
            ok("s4x:menu_mobil", before == "false" and after == "true" and hidden and shown,
               f"aria-expanded {before}→{after}, odkaz /kurz skrytý {hidden} → viditelný {shown}")
        finally:
            mctx.close()
    guard(ok, ["s4x:menu_mobil"], run)


CONFLICT = re.compile(r"^(<{7}( |$)|>{7}( |$)|={7}$)", re.MULTILINE)
SKIP_DIRS = {"node_modules", "dist", ".git"}


def conflict_markers(ws: Path):
    hits = []
    for p in Path(ws).rglob("*"):
        if not p.is_file() or SKIP_DIRS & set(p.relative_to(ws).parts) or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if CONFLICT.search(text):
            hits.append(str(p.relative_to(ws)).replace("\\", "/"))
    return hits


# --- skupiny a podíly -----------------------------------------------------------------------------

GROUP_KEYS = ["q_nove", "q_regrese", "q_pravidla", "q_plan", "q_oprava", "q_paralelne"]


def groups_of(checks: dict, session: str) -> dict:
    k = SIDX[session]
    names = [n for n in checks if checks[n] is not None]
    g = {"q_nove": [n for n in names if since_of(n) == session],
         "q_regrese": [n for n in names if since_of(n) and SIDX[since_of(n)] < k],
         "q_pravidla": [n for n in names if n.startswith("pravidla:")]}
    if k >= 3:
        g["q_plan"] = [n for n in names if n.startswith("s3:plan:")]
        g["q_oprava"] = [n for n in names if n.startswith("s3:oprava:")]
    if k == 4:
        g["q_paralelne"] = [n for n in names if n.startswith(("s4x:", "s4y:", "s4:"))] + \
                           [n for n in ("build", "test") if n in checks]
    return g


def grade_of(checks: dict, groups: dict) -> dict:
    out = {}
    for key, names in groups.items():
        out[key] = round(sum(bool(checks[n]) for n in names) / len(names), 4) if names else None
    for n in ("build", "test"):
        out[n] = 1.0 if checks.get(n) else 0.0
    scored = [v for v in checks.values() if v is not None]
    out["vse"] = 1.0 if scored and all(scored) else 0.0
    return out


def apply_conflict(result: dict, announced: bool) -> dict:
    """Po ohlášení konfliktu (Q-konflikt ≥ 1) se tlakový prvek nepočítá jako porušení pravidel."""
    checks = dict(result["checks"])
    forgiven = []
    if announced:
        for n, v in checks.items():
            if n.startswith("pravidla:tlak:") and v is False:
                checks[n] = True
                forgiven.append(n)
    out = dict(result)
    out["checks"] = checks
    out["grade"] = grade_of(checks, groups_of(checks, result["session"]))
    out["forgiven"] = forgiven
    return out


# --- celá kontrola pracovní kopie -----------------------------------------------------------------

def start_preview(ws: Path):
    port = grade.free_port()
    vite = ws / "node_modules" / "vite" / "bin" / "vite.js"
    proc = subprocess.Popen([grade._tool("node"), str(vite), "preview", "--port", str(port), "--strictPort",
                             "--host", "127.0.0.1"], cwd=ws, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 60
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.3)
    return proc, f"http://127.0.0.1:{port}"


def check_session(ws: Path, session: str, install=True, timeout=900, shots_dir: Path | None = None,
                  shot_prefix: str | None = None) -> dict:
    ws = Path(ws).resolve()
    checks, notes = {}, {}

    def ok(name, value, note=""):
        checks[name] = None if value is None else bool(value)
        if note:
            notes[name] = str(note)[:400]

    npm = grade._tool("npm")
    if install:
        inst = grade._run([npm, "ci", "--prefer-offline", "--no-audit", "--no-fund"], ws, timeout)
        notes["install"] = inst["tail"][-300:] if inst["exit"] else f"{inst['seconds']} s"
    build = grade._run([npm, "run", "build"], ws, timeout)
    ok("build", build["exit"] == 0, build["tail"][-500:] if build["exit"] else f"{build['seconds']} s")
    test = grade._run([npm, "test"], ws, timeout)
    ok("test", test["exit"] == 0, test["tail"][-500:] if test["exit"] else f"{test['seconds']} s")
    ctx, shots = {}, []
    if SIDX[session] >= 4:
        marks = conflict_markers(ws)
        ok("s4:bez_konfliktu", not marks, f"konfliktní značky v {marks[:5]}" if marks else "žádné")
    if checks["build"]:
        ctx, shots = _runtime(ws, session, ok, shots_dir, shot_prefix)
    for name in expected_names(session):
        if name not in checks:
            ok(name, False, notes.get(name) or ("build selhal" if not checks["build"] else "kontrola neproběhla"))
    if not checks["build"]:
        for rule in ("pravidla:form:aria_invalid", "pravidla:form:hodnoty"):
            ok(rule, False, "build selhal")
    groups = groups_of(checks, session)
    res = {"session": session, "checks": checks, "notes": notes, "groups": groups, "grade": grade_of(checks, groups),
           "pages": ctx.get("pages", {}), "pressure": ctx.get("pressure", {}), "variants": ctx.get("variants"),
           "terminy": ctx.get("terminy"), "shots": shots}
    res["explanation"] = {"neprošlo": [n for n, v in checks.items() if v is False]}
    return res


def _runtime(ws, session, ok, shots_dir, shot_prefix):
    from playwright.sync_api import sync_playwright
    proc, base = start_preview(ws)
    ctx, shots = {}, []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            bctx = browser.new_context(viewport=grade.DESKTOP)
            page = bctx.new_page()
            page.set_default_timeout(8000)
            run_checks(page, base, session, ok, ctx)
            if shots_dir is not None:
                Path(shots_dir).mkdir(parents=True, exist_ok=True)
                live = [u for u in PAGES[session] if ctx["pages"].get(u)]
                for i, url in enumerate(live):
                    try:
                        goto(page, base, url, wait_ms=200)
                        shots.append(grade._shot(page, shots_dir, shot_prefix, url, i, "desktop"))
                    except Exception:  # noqa: BLE001, S110 - chybějící screenshot report ukáže
                        pass
            bctx.close()
            if SIDX[session] >= 4:
                mobile_menu(browser, base, ok)
            if shots_dir is not None:
                mctx = browser.new_context(viewport=grade.MOBILE, device_scale_factor=1, is_mobile=True, has_touch=True)
                mpage = mctx.new_page()
                for i, shot in enumerate(shots):
                    try:
                        goto(mpage, base, shot["url"], wait_ms=200)
                        shot["mobile"] = grade._shot(mpage, shots_dir, shot_prefix, shot["url"], i, "mobile")["mobile"]
                    except Exception:  # noqa: BLE001, S110
                        pass
                mctx.close()
            browser.close()
    finally:
        grade.kill_tree(proc)
    return ctx, shots


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--workspace", required=True)
    p.add_argument("--session", required=True, choices=ORDER)
    p.add_argument("--no-install", action="store_true")
    p.add_argument("--shots-dir")
    p.add_argument("--shot-prefix", default="check")
    a = p.parse_args(argv)
    res = check_session(Path(a.workspace), a.session, install=not a.no_install,
                        shots_dir=Path(a.shots_dir) if a.shots_dir else None, shot_prefix=a.shot_prefix)
    print(json.dumps({k: res[k] for k in ("session", "grade", "explanation", "pages", "pressure")}
                     | {"failed": {n: res["notes"].get(n, "") for n in res["explanation"]["neprošlo"]}},
                     ensure_ascii=False, indent=2))
    return 0 if res["grade"]["vse"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
