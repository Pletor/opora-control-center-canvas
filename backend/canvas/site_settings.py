"""Globální nastavení a design webu (docs/navrhy/2026-11-03-platno-2-zamer-stranky.md §7).

Projekt nese `settings.site` celé: každá část a každé pole je vždy přítomné, nevyplněné je `""`.
Stránka (`site.kind == "page"`) smí přebít jen `seo` a `design.header` / `design.footer`; přebíjí jen to,
co uvede, a prázdné pole vynechá. Tajemství sem nepatří: klíč, který vypadá jako heslo nebo token, se odmítne
dřív než tvar, ať chyba řekne proč (SMTP heslo patří do prostředí serveru, ne do nastavení projektu).
Modul nic neimportuje z grafu, aby ho `site_metadata` (a přes něj graf) mohl použít bez cyklu.
"""
import re

from backend.canvas.payload_errors import keys_problem

TYPOGRAPHY = {"h1": 120, "h2": 120, "h3": 120, "h4": 120, "h5": 120, "body": 120, "fonts": 200}
# Část → pole → nejvýš znaků (vnořený slovník = vnořený objekt).
SITE_SHAPE = {
    "seo": {"titleTemplate": 120, "description": 300, "ogImage": 500},
    "legal": {"gdprContact": 200, "cookies": 300},
    "email": {"from": 200, "replyTo": 200},
    "design": {"header": 300, "footer": 300, "typography": TYPOGRAPHY, "buttons": 300},
}
PAGE_SHAPE = {"seo": SITE_SHAPE["seo"], "design": {"header": 300, "footer": 300}}
EMAILS = {"email.from", "email.replyTo"}
SECRET = re.compile(r"pass|heslo|secret|token|api.?key|credential", re.IGNORECASE)


def empty(shape=SITE_SHAPE):
    """Nevyplněné nastavení webu: stejný tvar, všude `""`."""
    return {key: empty(limit) if isinstance(limit, dict) else "" for key, limit in shape.items()}


def _secret(value, path):
    if isinstance(value, dict):
        for key, inner in value.items():
            if SECRET.search(str(key)):
                return path + str(key)
            found = _secret(inner, f"{path}{key}.")
            if found:
                return found
    return None


def _check(value, shape, path, partial):
    """`(pole, problém, očekávám)` u první chyby, jinak None."""
    field = path.rstrip(".") or "site"
    problem = keys_problem(value, () if partial else shape, shape)
    if problem:
        return field, problem, "přesně " + ", ".join(shape) if not partial else "jen " + ", ".join(shape)
    if partial and not value:
        return field, "je prázdné.", "aspoň jedno pole; bez přebití část vynechte"
    for key, limit in shape.items():
        if key not in value:
            continue
        inner, name = value[key], path + key
        if isinstance(limit, dict):
            found = _check(inner, limit, name + ".", partial)
            if found:
                return found
            continue
        minimum = 1 if partial else 0
        if (not isinstance(inner, str) or not minimum <= len(inner) <= limit or (partial and not inner.strip())
                or any(ord(char) < 32 or ord(char) == 127 for char in inner)):
            return name, f"má neplatnou hodnotu {inner!r}.", (
                f"text {minimum}–{limit} znaků bez řídicích znaků" + ("; prázdné pole vynechte" if partial else ""))
        if name in EMAILS and inner and "@" not in inner:
            return name, f"{inner!r} není e-mailová adresa.", "adresa s @, např. Jméno <info@example.cz>"
    return None


def site_problem(value, partial=False):
    """Chyba nastavení webu projektu (`partial=False`) nebo přebití stránky (`partial=True`) jako
    `(pole, problém, očekávám)`, nebo None. Pole je cesta uvnitř `site` (`seo.titleTemplate`)."""
    secret = _secret(value, "")
    if secret:
        return secret, "vypadá jako tajemství; hesla a tokeny do nastavení webu nepatří (SMTP heslo patří do prostředí serveru).", \
            "jen veřejná pole bez tajemství"
    return _check(value, PAGE_SHAPE if partial else SITE_SHAPE, "", partial)
