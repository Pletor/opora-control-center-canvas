"""Přehrání plánu záměru stránky v prohlížeči (Python Playwright), §6 `docs/navrhy/2026-11-03-platno-2-zamer-stranky.md`.

Volá ho `tools/journey_run.py --intent`; pořadí, vyhodnocení a doklad jsou v `tools/intent_run_logic.py`.
Kroky nad sekcí `scope`: `open` otevře stránku plánu, `click` klikne na odkaz či tlačítko s `text` (bez textu na
sekci), `type` vyplní první pole sekce textem `text`, `submit` klikne na tlačítko odeslání v sekci.
"""
from __future__ import annotations

try:
    from tools import intent_run_logic as logic
    from tools import journey_run_logic as journey
except ImportError:  # spuštěno jako skript z tools/
    import intent_run_logic as logic  # type: ignore[no-redef]
    import journey_run_logic as journey  # type: ignore[no-redef]

STEP_TIMEOUT_MS = 15_000
CHECK_TIMEOUT_MS = 5_000
FIELDS = "input:not([type=hidden]):not([type=submit]), textarea, [contenteditable=true]"
SUBMIT = "button[type=submit], input[type=submit], button:not([type])"


def _act(page, url: str, step: dict) -> tuple[bool, str | None]:
    action, where = step.get("do") or "click", step["scope"]
    if action == "open":
        page.goto(url)
    scope = page.locator(where)
    if not scope.count():
        return False, f"na stránce chybí {where}"
    scope = scope.first
    if action == "open":
        return True, None
    if action == "type":
        field = scope.locator(FIELDS)
        if not field.count():
            return False, f"v {where} chybí pole"
        field.first.fill(step.get("text") or "")
        return True, None
    if action == "submit":
        target = scope.locator(SUBMIT)
        if not target.count():
            return False, f"v {where} chybí tlačítko odeslání"
        target.first.click()
        return True, None
    text = step.get("text")
    if not text:
        scope.click()
        return True, None
    for role in ("link", "button"):
        found = scope.get_by_role(role, name=text)
        if found.count():
            found.first.click()
            return True, None
    return False, f"v {where} chybí odkaz ani tlačítko „{text}“"


def replay(plan: dict, base_url: str, headed: bool, log) -> list[dict]:
    """Otevře stránku plánu a přehraje jeho uzly; vrací výsledky uzlů dokladu."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    url = journey.page_url(base_url, plan["path"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_context().new_page()
        page.set_default_timeout(STEP_TIMEOUT_MS)
        page.set_default_navigation_timeout(STEP_TIMEOUT_MS)

        def act(step):
            try:
                return _act(page, url, step)
            except PlaywrightError as error:  # timeout, odpojený prvek, neplatný selektor
                return False, journey.short_reason(error)

        def visible(text):
            try:
                page.get_by_text(text).first.wait_for(state="visible", timeout=CHECK_TIMEOUT_MS)
                return True
            except PlaywrightError:
                return False

        def path(expected):
            try:
                page.wait_for_url(lambda current: journey.normalize_path(current) == journey.normalize_path(expected),
                                  timeout=CHECK_TIMEOUT_MS)
                return True
            except PlaywrightError:
                return False

        try:
            page.goto(url)
            results = logic.walk(plan, act, {"visible": visible, "path": path}, log)
        except PlaywrightError as error:
            results = logic.unopened(plan, f"nelze otevřít {url}: {journey.short_reason(error)}", log)
        browser.close()
    return results
