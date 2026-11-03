"""Dokument Správy webu projektu: normalizace a validace (`docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2).

Jeden dokument na projekt `{v, revision, title, lastChange, settings, design}`. `revision` a `lastChange` píše
jen server (`store.py`), z těla se zahodí. Chyba tvaru (neznámý klíč, špatný typ, překročený počet) =
`SiteAdminInvalid` (HTTP 422). Neplatná hodnota tokenu se zahodí s poznámkou (`tokens.py`).

Tajemství do dokumentu nepatří: klíč, který zní jako heslo, token nebo API klíč, je 422 kdekoli v `settings`;
`settings.email` smí nést jen odkaz `secretRef` (např. `env:SMTP_PASSWORD`), nikdy hodnotu.
"""

import re

from backend.project.site_admin.tokens import SiteAdminInvalid, clamp, normalize_tokens, shape

SECRET = re.compile(r"pass|heslo|secret|token|api.?key|credential", re.IGNORECASE)
SECRET_REF = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,15}:[A-Za-z0-9_./-]{1,200}$")
IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,63}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
GROUP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}[A-Za-z0-9_-]$|^[A-Za-z0-9]$")
MAX_README, MAX_SECTIONS, MAX_COMPONENTS = 200_000, 24, 200
MAX_COMPONENT_README, MAX_PREVIEW, MAX_ASSET_GROUPS, MAX_ASSETS = 64_000, 256_000, 50, 5000
COOKIE_CATEGORIES = ("necessary", "analytics", "marketing", "preferences")


def text(limit):
    return lambda value: isinstance(value, str) and len(value) <= limit


def integer(low, high):
    return lambda value: isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def one_of(*values):
    return lambda value: value in values


def boolean(value):
    return isinstance(value, bool)


def record(fields):
    return ("record", fields)


def items(limit, item):
    return ("list", limit, item)


LINK = record({"label": text(200), "url": text(2000), "pageId": text(128)})
SETTINGS = {
    "seo": record({"titleTemplate": text(200), "description": text(500), "ogImage": text(500),
                   "robots": text(200), "canonicalHost": text(253), "sitemap": boolean,
                   "structuredData": text(20_000)}),
    "affiliate": record({"enabled": boolean, "param": text(64), "cookieDays": integer(0, 3650),
                         "programs": items(50, record({"name": text(200), "url": text(2000),
                                                       "commission": text(100)}))}),
    "email": record({"provider": text(64), "host": text(253), "port": integer(1, 65535), "secure": boolean,
                     "from": text(320), "replyTo": text(320),
                     "secretRef": lambda value: isinstance(value, str) and bool(SECRET_REF.match(value))}),
    "header": record({"logoAsset": text(500), "nav": one_of("source:pages", "manual"), "items": items(50, LINK),
                      "cta": record({"label": text(200), "pageId": text(128)}), "sticky": boolean,
                      "variant": text(64)}),
    "footer": record({"columns": items(12, record({"title": text(200), "links": items(50, LINK)})),
                      "legal": text(2000), "social": items(20, record({"name": text(64), "url": text(2000)})),
                      "variant": text(64)}),
    "buttons": items(40, record({"name": text(64), "component": text(64), "variant": text(64),
                                 "tokens": ("map", 40, text(200))})),
    "gdpr": record({"cookieBar": record({"enabled": boolean,
                                         "position": one_of("bottom", "top", "bottom-left", "bottom-right"),
                                         "text": text(2000),
                                         "categories": items(len(COOKIE_CATEGORIES), one_of(*COOKIE_CATEGORIES)),
                                         "policyPageId": text(128), "consentDays": integer(1, 3650)}),
                    "contact": text(500)}),
}


def _check(value, rule, path):
    """Ověří hodnotu podle pravidla `SETTINGS`; vrací ji beze změny (tvar se nenormalizuje)."""
    if callable(rule):
        shape(rule(value), f"{path}: neplatná hodnota.")
    elif rule[0] == "record":
        shape(isinstance(value, dict), f"{path} musí být objekt.")
        for key, inner in value.items():
            # Pole schématu (`secretRef`, `tokens` tlačítka) projdou; jiný klíč, který zní jako tajemství, má vlastní zprávu.
            shape(key in rule[1] or not SECRET.search(str(key)),
                  f"{path}.{key}: tajemství do dokumentu nepatří, ulož ho mimo a dej jen secretRef.")
            shape(key in rule[1], f"{path}: neznámé pole {key}.")
            _check(inner, rule[1][key], f"{path}.{key}")
    elif rule[0] == "list":
        shape(isinstance(value, list) and len(value) <= rule[1], f"{path} musí být pole o nejvýš {rule[1]} položkách.")
        for index, inner in enumerate(value):
            _check(inner, rule[2], f"{path}[{index}]")
    else:
        shape(isinstance(value, dict) and len(value) <= rule[1], f"{path} musí být objekt o nejvýš {rule[1]} klíčích.")
        for key, inner in value.items():
            _check(inner, rule[2], f"{path}.{key}")
    return value


def _settings(raw):
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), "settings musí být objekt.")
    unknown = sorted(set(raw) - set(SETTINGS))
    shape(not unknown, f"settings: neznámá část {', '.join(unknown)}.")
    return {key: _check(raw.get(key, [] if key == "buttons" else {}), rule, f"settings.{key}")
            for key, rule in SETTINGS.items()}


def _text_field(value, limit, path):
    shape(value is None or (isinstance(value, str) and len(value.encode("utf-8")) <= limit),
          f"{path} musí být text do {limit // 1000} KB.")
    return value or ""


def _list(raw, limit, path):
    raw = [] if raw is None else raw
    shape(isinstance(raw, list) and len(raw) <= limit, f"{path} musí být pole o nejvýš {limit} položkách.")
    for item in raw:
        shape(isinstance(item, dict), f"Položka {path} musí být objekt.")
    return raw


def _sections(raw):
    out = []
    for item in _list(raw, MAX_SECTIONS, "design.sections"):
        shape(isinstance(item.get("slug"), str) and SLUG.match(item["slug"]), "design.sections: slug a-z0-9-.")
        shape(all(section["slug"] != item["slug"] for section in out), f"design.sections: duplicitní {item['slug']}.")
        out.append({"slug": item["slug"], "title": _text_field(item.get("title"), 200, "Titulek sekce"),
                    "markdown": _text_field(item.get("markdown"), MAX_README, "Markdown sekce")})
    return out


def _components(raw, notes):
    out = []
    for item in _list(raw, MAX_COMPONENTS, "design.components"):
        name = item.get("name")
        shape(isinstance(name, str) and IDENT.match(name), f"Komponenta {name!r}: jméno musí být identifikátor JS.")
        shape(all(component["name"] != name for component in out), f"Komponenta {name}: duplicitní jméno.")
        height = item.get("height", 120)
        if not (isinstance(height, int) and not isinstance(height, bool) and 40 <= height <= 4000):
            notes.append(f"Komponenta {name}: výška {height!r} mimo 40–4000, použito 120.")
            height = 120
        component = {"name": name, "height": height}
        for field, limit in (("group", 64), ("summary", 400)):
            value = clamp(item.get(field), limit, f"Komponenta {name} {field}", notes)
            if value:
                component[field] = value
        component["readme"] = _text_field(item.get("readme"), MAX_COMPONENT_README, f"README komponenty {name}")
        component["preview"] = _text_field(item.get("preview"), MAX_PREVIEW, f"Náhled komponenty {name}")
        out.append(component)
    return out


def _asset_groups(raw):
    out, total = [], 0
    for item in _list(raw, MAX_ASSET_GROUPS, "design.assetGroups"):
        name = item.get("name")
        shape(isinstance(name, str) and GROUP.match(name), f"Skupina assetů {name!r}: neplatné jméno.")
        shape(all(group["name"] != name for group in out), f"Skupina assetů {name}: duplicitní jméno.")
        files = _list(item.get("files"), MAX_ASSETS, f"Soubory skupiny {name}")
        total += len(files)
        shape(total <= MAX_ASSETS, f"Nejvýš {MAX_ASSETS} assetů.")
        kept = []
        for file in files:
            shape(isinstance(file.get("name"), str) and file.get("blob") == f"assets/{name}/{file['name']}",
                  f"Asset ve skupině {name}: blob musí být assets/{name}/<name>.")
            shape(integer(0, 10**9)(file.get("size")) and text(100)(file.get("type")),
                  f"Asset {file['name']}: size a type z nahrání.")
            kept.append({key: file[key] for key in ("name", "blob", "size", "type")})
        out.append({"name": name, "readme": _text_field(item.get("readme"), MAX_COMPONENT_README,
                                                        f"README skupiny {name}"), "files": kept})
    return out


def _design(raw, notes):
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), "design musí být objekt.")
    unknown = sorted(set(raw) - {"readme", "sections", "tokens", "components", "assetGroups", "cover"})
    shape(not unknown, f"design: neznámé pole {', '.join(unknown)}.")
    cover = raw.get("cover")
    shape(cover is None or (isinstance(cover, dict) and set(cover) <= {"preview"}), "design.cover je {preview}.")
    return {
        "readme": _text_field(raw.get("readme"), MAX_README, "design.readme"),
        "sections": _sections(raw.get("sections")),
        "tokens": normalize_tokens(raw.get("tokens"), notes),
        "components": _components(raw.get("components"), notes),
        "assetGroups": _asset_groups(raw.get("assetGroups")),
        "cover": {"preview": _text_field(cover.get("preview"), MAX_PREVIEW, "design.cover.preview")} if cover else None,
    }


def normalize(document):
    """Tělo od klienta → `(dokument bez revision/lastChange, poznámky o zahozených hodnotách)`."""
    shape(isinstance(document, dict), "Dokument musí být objekt.")
    unknown = sorted(set(document) - {"v", "revision", "title", "lastChange", "settings", "design"})
    shape(not unknown, f"Dokument: neznámé pole {', '.join(unknown)}.")
    shape(document.get("v", 1) == 1, "Dokument: v musí být 1.")
    title = document.get("title", "")
    shape(isinstance(title, str) and len(title) <= 200, "title musí být text do 200 znaků.")
    notes = []
    return {"v": 1, "title": title, "settings": _settings(document.get("settings")),
            "design": _design(document.get("design"), notes)}, notes


def empty():
    """Dokument projektu, který zatím nikdo neuložil (`revision: 0`)."""
    document, _ = normalize({})
    return {**document, "revision": 0, "lastChange": None}


__all__ = ["SiteAdminInvalid", "empty", "normalize"]
