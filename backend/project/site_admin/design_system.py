"""Dokument Správy webu projektu: normalizace a validace (`docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2).

Jeden dokument na projekt `{v, revision, title, lastChange, settings, design}`. `settings.seo`, `affiliate`,
`email` a `gdpr` ověřuje `site_settings.py`, `header` a `footer` `site_chrome.py`, `settings.appearance` je pohled
na tokeny (`appearance.py`), `settings.buttons` tlačítka (`buttons.py`), `settings.customCss` jejich vlastní CSS
(`custom_css.py`). `revision` a `lastChange` píše
jen server (`store.py`), z těla se zahodí. Chyba tvaru (neznámý klíč, špatný typ, překročený počet) =
`SiteAdminInvalid` (HTTP 422). Neplatná hodnota tokenu se zahodí s poznámkou (`tokens.py`).

Tajemství do dokumentu nepatří: klíč, který zní jako heslo, token nebo API klíč, je 422 kdekoli v `settings`;
`settings.email` smí nést jen odkaz `secretRef` (např. `env:SMTP_PASSWORD`), nikdy hodnotu.
"""

import re

from backend.project.site_admin import appearance, buttons, custom_css, site_chrome, site_settings
from backend.project.site_admin.tokens import SiteAdminInvalid, clamp, normalize_tokens, shape

IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,63}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
GROUP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}[A-Za-z0-9_-]$|^[A-Za-z0-9]$")
MAX_README, MAX_SECTIONS, MAX_COMPONENTS = 200_000, 24, 200
MAX_COMPONENT_README, MAX_PREVIEW, MAX_ASSET_GROUPS, MAX_ASSETS = 64_000, 256_000, 50, 5000


def text(limit):
    return lambda value: isinstance(value, str) and len(value) <= limit


def integer(low, high):
    return lambda value: isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


PARTS = ("seo", "affiliate", "email", "header", "footer", "gdpr", "appearance", "buttons", "customCss")


def _settings(raw, tokens, base_tokens, assets, notes):
    """Nastavení webu, Vzhled jako pohled na tokeny, tlačítka a vlastní CSS; vrací (settings, tokeny).

    `assets` jsou cesty souborů z Assets (logo, obrázek sdílení)."""
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), "settings musí být objekt.")
    unknown = sorted(set(raw) - set(PARTS))
    shape(not unknown, f"settings: neznámá část {', '.join(unknown)}.")
    settings = site_settings.normalize(raw, assets, notes)
    if raw.get("appearance") is not None:
        tokens = normalize_tokens(appearance.project(raw["appearance"], tokens, base_tokens or tokens, notes), notes)
    settings["appearance"] = appearance.view(tokens)
    settings["buttons"] = buttons.normalize(raw.get("buttons"), tokens, notes)
    settings["customCss"] = custom_css.normalize(raw.get("customCss"), settings["buttons"]["variants"], notes)
    settings["header"] = site_chrome.header(raw.get("header"), assets, settings["buttons"]["variants"], notes)
    settings["footer"] = site_chrome.footer(raw.get("footer"), notes)
    return {key: settings[key] for key in PARTS}, tokens


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


def _design(raw, tokens, asset_groups, notes):
    unknown = sorted(set(raw) - {"readme", "sections", "tokens", "components", "assetGroups", "cover"})
    shape(not unknown, f"design: neznámé pole {', '.join(unknown)}.")
    cover = raw.get("cover")
    shape(cover is None or (isinstance(cover, dict) and set(cover) <= {"preview"}), "design.cover je {preview}.")
    return {
        "readme": _text_field(raw.get("readme"), MAX_README, "design.readme"),
        "sections": _sections(raw.get("sections")),
        "tokens": tokens,
        "components": _components(raw.get("components"), notes),
        "assetGroups": asset_groups,
        "cover": {"preview": _text_field(cover.get("preview"), MAX_PREVIEW, "design.cover.preview")} if cover else None,
    }


def normalize(document, base=None):
    """Tělo od klienta → `(dokument bez revision/lastChange, poznámky)`.

    `base` je uložený dokument: Vzhled zapíše jen pole, která se liší od pohledu na jeho tokeny (`appearance.py`).
    """
    shape(isinstance(document, dict), "Dokument musí být objekt.")
    unknown = sorted(set(document) - {"v", "revision", "title", "lastChange", "settings", "design"})
    shape(not unknown, f"Dokument: neznámé pole {', '.join(unknown)}.")
    shape(document.get("v", 1) == 1, "Dokument: v musí být 1.")
    title = document.get("title", "")
    shape(isinstance(title, str) and len(title) <= 200, "title musí být text do 200 znaků.")
    notes = []
    design = {} if document.get("design") is None else document["design"]
    shape(isinstance(design, dict), "design musí být objekt.")
    tokens = normalize_tokens(design.get("tokens"), notes)
    asset_groups = _asset_groups(design.get("assetGroups"))
    assets = {file["blob"] for group in asset_groups for file in group["files"]}
    settings, tokens = _settings(document.get("settings"), tokens, base and base["design"]["tokens"], assets, notes)
    return {"v": 1, "title": title, "settings": settings, "design": _design(design, tokens, asset_groups, notes)}, notes


def empty():
    """Dokument projektu, který zatím nikdo neuložil (`revision: 0`)."""
    document, _ = normalize({})
    return {**document, "revision": 0, "lastChange": None}


__all__ = ["SiteAdminInvalid", "empty", "normalize"]
