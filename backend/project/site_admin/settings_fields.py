"""Pravidla polí Nastavení webu: text, číslo, volba, ano/ne, seznam, objekt s výchozími hodnotami, odkaz a obrázek.

Sdílí je `site_settings.py` (SEO, Affiliate, E-mail, GDPR) a `site_chrome.py` (hlavička, patička). Chyba = 422
(`SiteAdminInvalid`); klíč, který zní jako tajemství, má vlastní zprávu (heslo do dokumentu nepatří).
"""

import copy
import re

from backend.project.site_admin.tokens import ASSET, shape

SECRET = re.compile(r"pass|heslo|secret|token|api.?key|credential", re.IGNORECASE)
SECRET_REF = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,15}:[A-Za-z0-9_./-]{1,200}$")
HOST = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
                  r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
EMAIL = re.compile(r"^[^\s@<>\"(),;:]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$")
PAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:./-]{0,127}$")
HTTPS = re.compile(r"^https://[^\s<>\"'`\\]{3,1990}$")
# Odkaz na webu: cesta, kotva, https, mailto nebo tel. Nikdy `javascript:`, `data:` ani `//host`.
URL = re.compile(r"^(?:/(?!/)[^\s<>\"'`\\]{0,1999}|#[A-Za-z0-9_-]{0,200}|https://[^\s<>\"'`\\]{3,1990}"
                 r"|mailto:[^\s<>\"'`\\]{3,320}|tel:\+?[0-9 ()-]{3,32})$")
PARAM = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
HANDLE = re.compile(r"^@[A-Za-z0-9_]{1,15}$")
LOCALE = re.compile(r"^[a-z]{2,3}(?:_[A-Z]{2})?$")


def text(limit, pattern=None, what="text"):
    def check(value, path):
        shape(isinstance(value, str) and len(value) <= limit, f"{path}: musí být text do {limit} znaků.")
        value = value.strip()
        shape(not value or pattern is None or pattern.match(value), f"{path}: neplatný {what} {value[:80]!r}.")
        return value
    return check


def number(low, high):
    def check(value, path):
        shape(isinstance(value, int) and not isinstance(value, bool) and low <= value <= high,
              f"{path}: celé číslo {low}–{high}.")
        return value
    return check


def choice(*values):
    def check(value, path):
        shape(value in values, f"{path}: jedna z možností {'|'.join(values)}.")
        return value
    return check


def flag(value, path):
    shape(isinstance(value, bool), f"{path}: ano/ne (true/false).")
    return value


def listof(limit, item):
    def check(value, path):
        shape(isinstance(value, list) and len(value) <= limit, f"{path} musí být pole o nejvýš {limit} položkách.")
        return [item(inner, f"{path}[{index}]") for index, inner in enumerate(value)]
    return check


def fields(raw, spec, path):
    """Objekt podle `spec = {klíč: (pravidlo, výchozí)}`; chybějící klíč dostane výchozí hodnotu."""
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), f"{path} musí být objekt.")
    for key in raw:
        # Pole schématu (`secretRef`) projdou; jiný klíč, který zní jako tajemství, má vlastní zprávu.
        shape(key in spec or not SECRET.search(str(key)),
              f"{path}.{key}: tajemství do dokumentu nepatří, ulož ho mimo a dej jen secretRef.")
        shape(key in spec, f"{path}: neznámé pole {key}.")
    return {key: rule(raw[key], f"{path}.{key}") if key in raw else copy.deepcopy(default)
            for key, (rule, default) in spec.items()}


def record(spec):
    return lambda value, path: fields(value, spec, path)


def link(value, path):
    """Odkaz menu nebo patičky: popisek a buď stránka webu (`pageId`), nebo URL."""
    out = fields(value, {"label": (text(80), ""), "pageId": (text(128, PAGE_ID, "pageId"), ""),
                         "url": (text(2000, URL, "odkaz"), "")}, path)
    shape(out["label"], f"{path}.label: odkaz potřebuje popisek.")
    shape(bool(out["pageId"]) != bool(out["url"]), f"{path}: odkaz míří buď na stránku (pageId), nebo na URL.")
    return out


def image(assets, path, value, notes):
    """Obrázek: asset projektu (`assets/<skupina>/<soubor>`, musí existovat) nebo https URL; chybějící asset se
    zahodí s poznámkou, aby smazaný soubor nezablokoval uložení."""
    value = text(2000)(value, path)
    if not value or HTTPS.match(value):
        return value
    shape(ASSET.match(value), f"{path}: obrázek je asset projektu assets/<skupina>/<soubor> nebo https URL.")
    if value not in assets:
        notes.append(f"{path}: asset {value} v Assets není, zahozen.")
        return ""
    return value
