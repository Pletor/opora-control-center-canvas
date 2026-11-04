"""Nastavení webu: SEO, Affiliate, E-mail (SMTP) a GDPR (kontrakt Správy webu §2 `settings`).

Každá část se normalizuje na celý tvar s výchozími hodnotami, aby editor i dělník četli vždy stejná pole. Chyba
tvaru nebo neplatná hodnota (špatný typ, překročená délka, neznámý klíč, URL `javascript:`) = `SiteAdminInvalid`
(HTTP 422). Rady, které uložení nebrání (dlouhý popis pro vyhledávání, lišta bez odkazu na zásady), jdou do `notes`.

Tajemství do dokumentu nepatří: klíč, který zní jako heslo, token nebo API klíč, je 422 kdekoli v `settings`;
`email` smí nést jen odkaz `secretRef` (např. `env:SMTP_PASSWORD`), nikdy hodnotu.

Zdroje pravidel: SEO podle Google Search Central (title, meta description, robots, canonical, sitemap, JSON-LD)
a protokolu Open Graph; SMTP podle RFC 6409 (587 + STARTTLS) a RFC 8314 (465 implicitní TLS); cookie lišta podle
ePrivacy čl. 5 odst. 3, EDPB Guidelines 05/2020 (souhlas aktivní, granulární, odvolatelný stejně snadno),
zprávy EDPB Cookie Banner Taskforce 2023 (odmítnout na první vrstvě, nic předem zaškrtnuté) a ÚOOÚ (tlačítko
odmítnutí na stejné úrovni jako souhlas, přiměřená doba platnosti).
"""

import copy
import json
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
COOKIE_CATEGORIES = ("necessary", "preferences", "analytics", "marketing")
DESCRIPTION_SHOWN = 160  # zhruba tolik znaků ukáže výsledek vyhledávání, delší se ořízne
CONSENT_ADVISED = 395  # 13 měsíců: nejdelší doba, po které dozorové úřady (CNIL) doporučují se zeptat znovu


# --- Pravidla polí --------------------------------------------------------------------------------------------

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


# --- SEO ------------------------------------------------------------------------------------------------------

ROBOTS = {"index": (flag, True), "follow": (flag, True), "noarchive": (flag, False), "nosnippet": (flag, False),
          "maxImagePreview": (choice("large", "standard", "none"), "large"), "maxSnippet": (number(-1, 10_000), -1)}
SEO = {
    "titleTemplate": (text(200), "%s"), "siteName": (text(120), ""), "description": (text(500), ""),
    "locale": (text(6, LOCALE, "jazyk (cs_CZ)"), "cs_CZ"), "canonicalHost": (text(253, HOST, "host"), ""),
    "ogImage": (text(2000), ""), "ogType": (choice("website", "article", "product", "profile"), "website"),
    "twitterCard": (choice("summary_large_image", "summary"), "summary_large_image"),
    "twitterSite": (text(16, HANDLE, "účet (@jmeno)"), ""), "robots": (record(ROBOTS), fields({}, ROBOTS, "")),
    "sitemap": (flag, True), "structuredData": (text(20_000), ""),
}


def structured_data(value, path):
    """JSON-LD: objekt nebo pole objektů schema.org, bez `</` (skončil by `<script type="application/ld+json">`)."""
    if not value:
        return
    try:
        data = json.loads(value)
    except ValueError as error:
        shape(False, f"{path}, řádek {error.lineno}: JSON-LD není platný JSON ({error.msg}).")
    shape(isinstance(data, dict) or isinstance(data, list) and data and all(isinstance(i, dict) for i in data),
          f"{path}: JSON-LD je objekt nebo pole objektů.")
    shape("</" not in value, f"{path}: JSON-LD nesmí obsahovat </ (ukončil by značku script).")


def seo(raw, assets, notes):
    out = fields(raw, SEO, "settings.seo")
    shape(not out["titleTemplate"] or out["titleTemplate"].count("%s") == 1,
          "settings.seo.titleTemplate: šablona obsahuje právě jednou %s (místo pro titulek stránky).")
    out["ogImage"] = image(assets, "settings.seo.ogImage", out["ogImage"], notes)
    structured_data(out["structuredData"], "settings.seo.structuredData")
    if len(out["description"]) > DESCRIPTION_SHOWN:
        notes.append(f"SEO: popis má {len(out['description'])} znaků, vyhledávač ukáže zhruba {DESCRIPTION_SHOWN}.")
    if not out["robots"]["index"]:
        notes.append("SEO: robots noindex, vyhledávače web neukážou (správně jen pro vývojovou doménu).")
    return out


# --- Affiliate a e-mail ---------------------------------------------------------------------------------------

PROGRAM = {"name": (text(120), ""), "url": (text(2000, HTTPS, "https URL"), ""), "commission": (text(100), ""),
           "code": (text(64), "")}
AFFILIATE = {"enabled": (flag, False), "param": (text(32, PARAM, "parametr (a-z0-9_-)"), "ref"),
             "cookieDays": (number(1, 365), 30), "attribution": (choice("last", "first"), "last"),
             "disclosure": (text(500), ""), "programs": (listof(50, record(PROGRAM)), [])}

EMAIL_FIELDS = {
    "provider": (choice("smtp", "sendgrid", "mailgun", "ses", "postmark", "resend", "other"), "smtp"),
    "host": (text(253, HOST, "host"), ""), "port": (number(1, 65535), 587),
    "security": (choice("starttls", "tls", "none"), "starttls"), "username": (text(320), ""),
    "from": (text(320, EMAIL, "e-mail"), ""), "fromName": (text(120), ""),
    "replyTo": (text(320, EMAIL, "e-mail"), ""), "secretRef": (text(217, SECRET_REF, "secretRef (env:JMENO)"), ""),
}


def affiliate(raw, notes):
    out = fields(raw, AFFILIATE, "settings.affiliate")
    for index, program in enumerate(out["programs"]):
        shape(program["name"], f"settings.affiliate.programs[{index}].name: program potřebuje jméno.")
    if out["enabled"] and not out["disclosure"]:
        notes.append("Affiliate: chybí upozornění pro návštěvníky, že odkazy jsou provizní.")
    return out


def email(raw, notes):
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), "settings.email musí být objekt.")
    if "secure" in raw:  # starší tvar: secure = šifrované spojení; 465 je implicitní TLS, jinak STARTTLS
        secure = flag(raw["secure"], "settings.email.secure")
        raw = {key: value for key, value in raw.items() if key != "secure"}
        raw.setdefault("security", ("tls" if raw.get("port") == 465 else "starttls") if secure else "none")
    out = fields(raw, EMAIL_FIELDS, "settings.email")
    if out["port"] == 465 and out["security"] == "starttls":
        notes.append("E-mail: port 465 čeká implicitní TLS (RFC 8314), ne STARTTLS.")
    if out["port"] == 587 and out["security"] == "tls":
        notes.append("E-mail: port 587 je submission se STARTTLS (RFC 6409), implicitní TLS běží na 465.")
    if out["host"] and out["security"] == "none":
        notes.append("E-mail: spojení bez šifrování, přihlašovací údaje i pošta půjdou čitelně.")
    if out["host"] and not out["from"]:
        notes.append("E-mail: chybí adresa odesílatele (from).")
    return out


# --- GDPR -----------------------------------------------------------------------------------------------------

CATEGORY = {"label": (text(80), ""), "description": (text(500), "")}
COOKIE_BAR = {
    "enabled": (flag, False), "position": (choice("bottom", "top", "bottom-left", "bottom-right", "center"), "bottom"),
    "title": (text(120), ""), "text": (text(2000), ""),
    "categories": (listof(len(COOKIE_CATEGORIES), choice(*COOKIE_CATEGORIES)), ["necessary"]),
    "categoryInfo": (lambda value, path: _category_info(value, path), {}),
    "acceptLabel": (text(40), "Přijmout vše"), "rejectLabel": (text(40), "Odmítnout vše"),
    "settingsLabel": (text(40), "Nastavení"), "saveLabel": (text(40), "Uložit výběr"),
    "policyPageId": (text(128, PAGE_ID, "pageId"), ""), "policyUrl": (text(2000, URL, "odkaz"), ""),
    "consentDays": (number(1, 730), 180), "reopen": (flag, True), "version": (number(1, 9999), 1),
}
CONTACT = {"controller": (text(200), ""), "email": (text(320, EMAIL, "e-mail"), ""),
           "dpoEmail": (text(320, EMAIL, "e-mail"), ""), "address": (text(300), "")}


def _category_info(value, path):
    shape(isinstance(value, dict) and set(value) <= set(COOKIE_CATEGORIES),
          f"{path}: objekt s klíči {'|'.join(COOKIE_CATEGORIES)}.")
    return {key: fields(value[key], CATEGORY, f"{path}.{key}") for key in COOKIE_CATEGORIES if key in value}


def gdpr(raw, notes):
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), "settings.gdpr musí být objekt.")
    if isinstance(raw.get("contact"), str):  # starší tvar: kontakt jako jeden text
        raw = {**raw, "contact": {"controller": raw["contact"]}}
    out = fields(raw, {"cookieBar": (record(COOKIE_BAR), fields({}, COOKIE_BAR, "")),
                       "contact": (record(CONTACT), fields({}, CONTACT, ""))}, "settings.gdpr")
    bar = out["cookieBar"]
    # Nezbytné cookies platí vždy (bez souhlasu), ostatní kategorie jdou v pevném pořadí bez opakování.
    bar["categories"] = [key for key in COOKIE_CATEGORIES if key == "necessary" or key in bar["categories"]]
    bar["categoryInfo"] = {key: info for key, info in bar["categoryInfo"].items() if key in bar["categories"]}
    out["cookieBar"] = bar
    if bar["enabled"]:
        if not bar["policyPageId"] and not bar["policyUrl"]:
            notes.append("Cookie lišta: chybí odkaz na zásady cookies (stránka nebo URL).")
        if bar["categories"] == ["necessary"]:
            notes.append("Cookie lišta: jen nezbytné cookies souhlas nepotřebují (ePrivacy čl. 5 odst. 3), "
                         "stačí informace v zásadách.")
        if bar["consentDays"] > CONSENT_ADVISED:
            notes.append(f"Cookie lišta: souhlas platí {bar['consentDays']} dní, úřady doporučují se zeptat "
                         f"nejpozději po 13 měsících.")
    if bar["enabled"] and not out["contact"]["email"]:
        notes.append("GDPR: chybí kontakt správce (e-mail) pro dotazy a odvolání souhlasu.")
    return out


def normalize(raw, assets, notes):
    """Části `seo`, `affiliate`, `email` a `gdpr` z `settings` (`assets` = blob cesty z Assets)."""
    parts = {"seo": seo(raw.get("seo"), assets, notes), "affiliate": affiliate(raw.get("affiliate"), notes),
             "email": email(raw.get("email"), notes), "gdpr": gdpr(raw.get("gdpr"), notes)}
    if parts["affiliate"]["enabled"] and parts["gdpr"]["cookieBar"]["enabled"] \
            and "marketing" not in parts["gdpr"]["cookieBar"]["categories"]:
        notes.append("Affiliate ukládá cookie s kódem partnera, cookie lišta by měla mít kategorii marketing.")
    return parts
