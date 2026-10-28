"""Přehrání plánu cesty v prohlížeči (Python Playwright) podle `docs/brana-cesty.md` §2.

Volá ho `tools/journey_run.py`; rozhodování bez prohlížeče je v `tools/journey_run_logic.py`.
"""
from __future__ import annotations

try:
    from tools import journey_run_logic as logic
except ImportError:  # spuštěno jako skript z tools/
    import journey_run_logic as logic  # type: ignore[no-redef]

SEGMENT_TIMEOUT_MS = 15_000


def _find_element(page, scope, segment: dict):
    """Prvek přechodu podle `logic.element_strategy`, nebo (None, důvod)."""
    strategy = logic.element_strategy(segment)
    where = segment["scope"]
    if strategy["kind"] == "role":
        for role in strategy["roles"]:
            found = scope.get_by_role(role, name=strategy["name"])
            if found.count():
                return found.first, None
        kinds = " ani ".join("odkaz" if r == "link" else "tlačítko" for r in strategy["roles"])
        return None, f"v {where} chybí {kinds} „{strategy['name']}“"
    if strategy["kind"] == "submit-button":
        found = scope.locator(strategy["selector"])
        return (found.first, None) if found.count() else (None, f"v {where} chybí tlačítko odeslání")
    links = scope.locator("a[href]")
    for index in range(links.count()):
        link = links.nth(index)
        if logic.href_matches(link.get_attribute("href"), page.url, segment["expectPath"]):
            return link, None
    return None, f"v {where} chybí odkaz na {segment['expectPath']}"


def _fill_form(scope, fields: dict[str, str]) -> None:
    for key, value in fields.items():
        kind, target = logic.field_target(key)
        field = scope.locator(target) if kind == "selector" else scope.get_by_label(target)
        field.first.fill(value)


def replay_segment(page, base_url: str, segment: dict, fixtures: dict, journey_id: str) -> tuple[bool, str | None]:
    """Přehraje jeden segment podle §2; vrací (ok, důvod)."""
    from playwright.sync_api import Error as PlaywrightError

    url = logic.page_url(base_url, segment["open"])
    try:
        page.goto(url)
    except PlaywrightError as error:  # síť, timeout
        return False, f"nelze otevřít {url}: {logic.short_reason(error)}"
    scope = page.locator(segment["scope"])
    if not scope.count():
        return False, f"na {segment['open']} chybí {segment['scope']}"
    scope = scope.first
    if (segment.get("do") or "click") == "submit":
        fields = logic.form_data(fixtures, journey_id, segment["to"])
        if fields is None:
            return False, logic.MISSING_FORM_DATA
        _fill_form(scope, fields)
    element, reason = _find_element(page, scope, segment)
    if element is None:
        return False, reason
    expect = logic.normalize_path(segment["expectPath"])
    element.click()
    try:
        page.wait_for_url(lambda current: logic.normalize_path(current) == expect)
    except PlaywrightError:
        return False, f"URL {logic.normalize_path(page.url)}, čekáno {expect}"
    return True, None


def replay(plan: dict, base_url: str, fixtures: dict, headed: bool, log, progress=None) -> list[dict]:
    """Přehraje segmenty plánu; `progress(segment, ok=None)` (nepovinné) hlásí přechod před přehráním a po něm."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_context().new_page()
        page.set_default_timeout(SEGMENT_TIMEOUT_MS)
        page.set_default_navigation_timeout(SEGMENT_TIMEOUT_MS)
        for segment in plan["segments"]:
            if progress:
                progress(segment)
            try:
                ok, reason = replay_segment(page, base_url, segment, fixtures, plan["journeyId"])
            except PlaywrightError as error:  # timeout, odpojený prvek, neplatný selektor
                ok, reason = False, logic.short_reason(error)
            log(f"{segment['from']} -> {segment['to']}: {'ok' if ok else 'selhal: ' + str(reason)}")
            results.append({"from": segment["from"], "to": segment["to"], "ok": ok, "reason": reason})
            if progress:
                progress(segment, ok)
        browser.close()
    return results
