"""Hlavička a patička webu a styly hlavičky, patičky a cookie lišty (kontrakt Správy webu §2 `header`, `footer`).

Tvar:

    header = {logoAsset, logoAlt, nav: "source:pages"|"manual", items: [odkaz], cta: {label, pageId, url, variant},
              sticky, variant: classic|centered|minimal}
    footer = {columns: [{title, links: [odkaz]}], legal, social: [{name, url}], variant: columns|simple|centered,
              cookieLink}
    odkaz  = {label, pageId | url}

`nav: source:pages` skládá menu z hlavních stránek mapy domény (dělník je čte z mapy); `items` jsou ruční menu,
nebo u `source:pages` odkazy navíc. Logo je asset projektu, CTA odkazuje variantu tlačítka. Chyba tvaru = 422.

`css()` dává pravidla `.ds-header`, `.ds-footer` a `.ds-cookie-bar` (BEM) jen přes tokeny s náhradní hodnotou, aby
fungovala i v systému bez `--surface`. Pohyb (vyjetí lišty) je jen v `prefers-reduced-motion: no-preference`,
`prefers-contrast: more` a `forced-colors` dostanou plné rámečky. Tlačítka souhlasu a odmítnutí mají stejnou třídu
i váhu (ÚOOÚ, EDPB: odmítnout stejně snadno jako přijmout).
"""

from backend.project.site_admin.site_settings import (
    HTTPS,
    PAGE_ID,
    URL,
    choice,
    fields,
    flag,
    image,
    link,
    listof,
    record,
    text,
)
from backend.project.site_admin.tokens import shape

SOCIAL = ("facebook", "instagram", "linkedin", "x", "youtube", "tiktok", "github", "pinterest", "mastodon", "other")
CTA = {"label": (text(40), ""), "pageId": (text(128, PAGE_ID, "pageId"), ""), "url": (text(2000, URL, "odkaz"), ""),
       "variant": (text(32), "")}
HEADER = {
    "logoAsset": (text(2000), ""), "logoAlt": (text(120), ""), "nav": (choice("source:pages", "manual"), "source:pages"),
    "items": (listof(12, link), []), "cta": (record(CTA), fields({}, CTA, "")), "sticky": (flag, False),
    "variant": (choice("classic", "centered", "minimal"), "classic"),
}
COLUMN = {"title": (text(80), ""), "links": (listof(12, link), [])}
FOOTER = {
    "columns": (listof(6, record(COLUMN)), []), "legal": (text(2000), ""),
    "social": (listof(12, record({"name": (choice(*SOCIAL), "other"), "url": (text(2000, HTTPS, "https URL"), "")})), []),
    "variant": (choice("columns", "simple", "centered"), "columns"), "cookieLink": (flag, True),
}


def header(raw, assets, variants, notes):
    out = fields(raw, HEADER, "settings.header")
    out["logoAsset"] = image(assets, "settings.header.logoAsset", out["logoAsset"], notes)
    if out["logoAsset"] and not out["logoAlt"]:
        notes.append("Hlavička: logo potřebuje alternativní text (jméno webu) pro čtečky obrazovky.")
    cta = out["cta"]
    shape(not (cta["pageId"] and cta["url"]), "settings.header.cta: míří buď na stránku (pageId), nebo na URL.")
    shape(not cta["label"] or cta["pageId"] or cta["url"], "settings.header.cta: tlačítko potřebuje cíl.")
    if cta["variant"] and cta["variant"] not in variants:
        notes.append(f"Hlavička: varianta tlačítka {cta['variant']} v Tlačítkách webu není, použije se výchozí.")
        cta["variant"] = ""
    if out["nav"] == "manual" and not out["items"]:
        notes.append("Hlavička: ruční menu je prázdné.")
    return out


def footer(raw, notes):
    out = fields(raw, FOOTER, "settings.footer")
    for index, item in enumerate(out["social"]):
        shape(item["url"], f"settings.footer.social[{index}].url: síť potřebuje adresu.")
    if (out["columns"] or out["social"]) and not out["legal"]:
        notes.append("Patička: chybí právní řádek (provozovatel, IČO, copyright).")
    return out


# --- CSS ------------------------------------------------------------------------------------------------------

SURFACE, INK, LINE = "var(--surface, #ffffff)", "var(--ink, #1a1a1a)", \
    "color-mix(in srgb, var(--ink, #1a1a1a) 16%, transparent)"
RULES = {
    ".ds-header": ["display: block;", f"background: {SURFACE};", f"color: {INK};", f"border-bottom: 1px solid {LINE};",
                   "z-index: 50;"],
    ".ds-header--sticky": ["position: sticky;", "top: 0;"],
    ".ds-header__inner": ["display: flex;", "flex-wrap: wrap;", "align-items: center;", "gap: 1rem 2rem;",
                          "box-sizing: border-box;", "max-width: var(--layout-wide, 1200px);", "margin-inline: auto;",
                          "padding: 0.75rem var(--layout-gutter, 1.5rem);", "min-height: 64px;"],
    ".ds-header__logo": ["display: inline-flex;", "align-items: center;", "gap: 0.5rem;", "color: inherit;",
                         "font-weight: 700;", "text-decoration: none;"],
    ".ds-header__logo-img": ["display: block;", "height: 40px;", "width: auto;"],
    ".ds-header__nav": ["display: flex;", "flex-wrap: wrap;", "gap: 0.25rem 1.25rem;", "margin-inline-start: auto;"],
    ".ds-header__link": ["display: inline-flex;", "align-items: center;", "min-height: 44px;", "color: inherit;",
                         "text-decoration: none;"],
    '.ds-header__link:hover, .ds-header__link[aria-current="page"]': ["color: var(--link, currentColor);",
                                                                      "text-decoration: underline;",
                                                                      "text-underline-offset: 0.3em;"],
    ".ds-header--centered .ds-header__inner": ["flex-direction: column;", "justify-content: center;"],
    ".ds-header--centered .ds-header__nav": ["margin-inline: auto;", "justify-content: center;"],
    ".ds-header--minimal .ds-header__nav": ["gap: 0.25rem 0.75rem;", "font-size: 0.9375rem;"],
    ".ds-footer": ["display: block;", f"background: {SURFACE};", f"color: {INK};", f"border-top: 1px solid {LINE};"],
    ".ds-footer__inner": ["display: grid;", "gap: 2rem;", "box-sizing: border-box;",
                          "max-width: var(--layout-wide, 1200px);", "margin-inline: auto;",
                          "padding: 2.5rem var(--layout-gutter, 1.5rem) 1.5rem;"],
    ".ds-footer__columns": ["display: grid;", "grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));",
                            "gap: 1.5rem 2rem;"],
    ".ds-footer__title": ["margin: 0 0 0.5rem;", "font-size: 0.875rem;", "font-weight: 700;",
                          "letter-spacing: 0.02em;"],
    ".ds-footer__links": ["display: grid;", "gap: 0.25rem;", "margin: 0;", "padding: 0;", "list-style: none;"],
    ".ds-footer__link": ["display: inline-block;", "padding-block: 0.25rem;", "color: inherit;",
                         "text-decoration: none;"],
    ".ds-footer__link:hover": ["color: var(--link, currentColor);", "text-decoration: underline;"],
    ".ds-footer__social": ["display: flex;", "flex-wrap: wrap;", "gap: 0.75rem;", "margin: 0;", "padding: 0;",
                           "list-style: none;"],
    ".ds-footer__legal": ["display: flex;", "flex-wrap: wrap;", "justify-content: space-between;", "gap: 0.5rem 1rem;",
                          "padding-top: 1rem;", f"border-top: 1px solid {LINE};", "font-size: 0.8125rem;",
                          "opacity: 0.85;"],
    ".ds-footer--simple .ds-footer__columns": ["display: flex;", "flex-wrap: wrap;", "gap: 0.5rem 1.5rem;"],
    ".ds-footer--simple .ds-footer__title": ["display: none;"],
    ".ds-footer--centered .ds-footer__inner, .ds-footer--centered .ds-footer__legal": ["justify-items: center;",
                                                                                      "justify-content: center;",
                                                                                      "text-align: center;"],
    ".ds-cookie-bar": ["position: fixed;", "inset: auto 0 0 0;", "z-index: 1000;", "display: grid;", "gap: 0.75rem;",
                       "box-sizing: border-box;", "max-height: 90vh;", "overflow: auto;", "padding: 1.25rem 1.5rem;",
                       f"background: {SURFACE};", f"color: {INK};", f"border-top: 1px solid {LINE};",
                       "box-shadow: var(--shadow-lg, 0 -4px 24px rgba(0, 0, 0, 0.12));"],
    ".ds-cookie-bar--top": ["inset: 0 0 auto 0;", "border-top: 0;", f"border-bottom: 1px solid {LINE};"],
    ".ds-cookie-bar--bottom-left, .ds-cookie-bar--bottom-right": ["inset: auto auto 1rem 1rem;",
                                                                  "width: min(420px, calc(100% - 2rem));",
                                                                  f"border: 1px solid {LINE};",
                                                                  "border-radius: var(--radius-md, 12px);"],
    ".ds-cookie-bar--bottom-right": ["inset: auto 1rem 1rem auto;"],
    ".ds-cookie-bar--center": ["inset: 50% auto auto 50%;", "transform: translate(-50%, -50%);",
                               "width: min(560px, calc(100% - 2rem));", f"border: 1px solid {LINE};",
                               "border-radius: var(--radius-md, 12px);"],
    ".ds-cookie-bar__title": ["margin: 0;", "font-size: 1.0625rem;", "font-weight: 700;"],
    ".ds-cookie-bar__text": ["margin: 0;", "font-size: 0.9375rem;", "line-height: 1.5;"],
    ".ds-cookie-bar__policy": ["color: var(--link, currentColor);", "text-decoration: underline;"],
    ".ds-cookie-bar__categories": ["display: grid;", "gap: 0.5rem;", "margin: 0;", "padding: 0;", "border: 0;"],
    ".ds-cookie-bar__category": ["display: grid;", "grid-template-columns: auto 1fr;", "gap: 0 0.5rem;",
                                 "align-items: start;", "font-size: 0.875rem;"],
    ".ds-cookie-bar__category-note": ["grid-column: 2;", "opacity: 0.8;"],
    ".ds-cookie-bar__actions": ["display: flex;", "flex-wrap: wrap;", "gap: 0.5rem;"],
    ".ds-cookie-bar__choice": ["flex: 1 1 140px;", "min-height: 44px;", "padding: 0.5rem 1rem;", "font: inherit;",
                               "font-weight: 600;", f"background: {INK};", f"color: {SURFACE};",
                               f"border: 1px solid {INK};", "border-radius: var(--radius-md, 8px);",
                               "cursor: pointer;"],
    ".ds-cookie-bar__choice--settings": ["background: transparent;", f"color: {INK};"],
    ".ds-cookie-reopen": ["position: fixed;", "inset: auto auto 1rem 1rem;", "z-index: 999;", "min-height: 44px;",
                          "padding: 0.5rem 0.875rem;", "font: inherit;", "font-size: 0.8125rem;",
                          f"background: {SURFACE};", f"color: {INK};", f"border: 1px solid {LINE};",
                          "border-radius: 999px;", "cursor: pointer;"],
    (".ds-header__link:focus-visible, .ds-header__logo:focus-visible, .ds-footer__link:focus-visible, "
     ".ds-cookie-bar__choice:focus-visible, .ds-cookie-bar__policy:focus-visible, .ds-cookie-reopen:focus-visible"):
        ["outline: 2px solid var(--focus, currentColor);", "outline-offset: 2px;"],
}
MOTION = ["@media (prefers-reduced-motion: no-preference) {",
          "  .ds-cookie-bar {", "    animation: ds-cookie-bar-in 240ms ease-out;", "  }",
          "  @keyframes ds-cookie-bar-in {", "    from {", "      opacity: 0;", "    }", "  }", "}"]
CONTRAST = ["@media (prefers-contrast: more), (forced-colors: active) {",
            "  .ds-header, .ds-footer, .ds-cookie-bar, .ds-cookie-reopen {",
            "    border-color: currentColor;", "  }", "  .ds-cookie-bar__choice {", "    border: 2px solid currentColor;",
            "  }", "}"]


def css(indent="  "):
    """Pravidla `@layer components` (bez obalu) pro hlavičku, patičku a cookie lištu."""
    out = []
    for selector, lines in RULES.items():
        out += [f"{indent}{selector} {{", *(f"{indent}  {line}" for line in lines), f"{indent}}}"]
    return out + [f"{indent}{line}" for line in (*MOTION, *CONTRAST)]
