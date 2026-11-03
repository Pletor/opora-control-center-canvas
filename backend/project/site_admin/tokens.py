"""Gramatika tokenů design systému projektu (`docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2).

Gramatika je převzatá z otevřeného formátu `tokens.json` typu Design System, kód typu ne. Pravidla:

- Tvar (rodina není objekt, `tokens` není pole, překročený počet) = `SiteAdminInvalid` (HTTP 422).
- Neplatná HODNOTA se zahodí s poznámkou v `notes`, stejně jako ve formátu: pojmenovaná barva, `var()`,
  `url()`, alias na chybějící token, na sebe, cyklus, řetěz hlubší než 16, špatná délka… Token bez platné
  hodnoty v žádném tématu se zahodí celý, styl se špatným `fontSize` taky. Dlouhý text se zkrátí.
- Jména tokenů a stylů `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`; úvodní `--` nebo `.` se ořízne. Všechny rodiny
  kromě `type` sdílejí jeden jmenný prostor (duplicita se zahodí), styly mají vlastní.
"""

import re

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
COLOR_FUNCTIONS = ("rgb", "rgba", "hsl", "hsla", "oklch", "oklab", "lab", "lch", "color")
FUNCTION = re.compile(r"^(" + "|".join(COLOR_FUNCTIONS) + r")\(([^()]*)\)$", re.IGNORECASE)
NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?(?:%|deg|rad|grad|turn)?$", re.IGNORECASE)
COLOR_SPACES = {"srgb", "srgb-linear", "display-p3", "a98-rgb", "prophoto-rgb", "rec2020", "xyz", "xyz-d50", "xyz-d65"}
ALIAS = re.compile(r"^\{([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\}$")
LENGTH = re.compile(r"^(?:[+-]?(?:\d+\.?\d*|\.\d+)(?:px|rem|em|%)|0)$")
PLAIN = re.compile(r"^[A-Za-z0-9 #%(),./+_-]{1,200}$")
STACK_FORBIDDEN = re.compile(r"[;{}<>\\()]")
FONT_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,127}\.(?:woff2|woff|ttf|otf|ttc)$", re.IGNORECASE)
WEIGHT = re.compile(r"^(\d{1,4})(?: (\d{1,4}))?$")
INLINE_FUNCTION = re.compile(r"\b(?:" + "|".join(COLOR_FUNCTIONS) + r")\([^()]*\)", re.IGNORECASE)

MAX_THEMES, MAX_COLORS, MAX_FONTS, MAX_FAMILIES = 8, 600, 4096, 12
MAX_GROUPS, MAX_STYLES, MAX_FAMILY_TOKENS, MAX_CUSTOM = 12, 80, 60, 12
MAX_NOTE, MAX_USAGE, MAX_SAMPLE, MAX_SHADOW = 400, 1000, 200, 400
MAX_ALIAS_DEPTH = 16
FIXED = ("color", "type", "spacing", "radius", "shadow")
DEFAULT_THEMES = [{"id": "light", "name": "Light"}]


class SiteAdminInvalid(ValueError):
    """Dokument Správy webu nemá předepsaný tvar (HTTP 422)."""


def shape(condition, message):
    if not condition:
        raise SiteAdminInvalid(message)


def name_of(value):
    """Jméno tokenu nebo stylu bez úvodního `--`/`.`; neplatné = None."""
    if not isinstance(value, str):
        return None
    value = value.removeprefix("--").removeprefix(".")
    return value if NAME.match(value) else None


def clamp(value, limit, label, notes):
    """Volitelný text: jiný typ se zahodí, delší se zkrátí; obojí s poznámkou."""
    if value is None:
        return None
    if not isinstance(value, str):
        notes.append(f"{label}: není text, zahozeno.")
        return None
    if len(value) > limit:
        notes.append(f"{label}: zkráceno na {limit} znaků.")
        return value[:limit]
    return value


def _number_text(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return f"{value:g}"
    return value.strip() if isinstance(value, str) else None


def length(value):
    """`12px|0.75rem|1em|50%|0`, číslo = px; jinak None."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return "0" if value == 0 else f"{value:g}px"
    if isinstance(value, str):
        text = value.strip()
        if LENGTH.match(text):
            return text
        if NUMBER.match(text) and text[-1].isdigit():
            return "0" if float(text) == 0 else f"{float(text):g}px"
    return None


def color_literal(value):
    """Hex (malými) nebo barevná funkce s čistě číselnými argumenty; jinak None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if HEX.match(text):
        return text.lower()
    match = FUNCTION.match(text)
    if not match:
        return None
    parts = [part for part in re.split(r"[\s,/]+", match[2].strip()) if part]
    if match[1].lower() == "color":
        if not parts or parts[0].lower() not in COLOR_SPACES:
            return None
        parts = parts[1:]
    if not parts or not all(NUMBER.match(part) or part.lower() == "none" for part in parts):
        return None
    return text


def shadow_literal(value):
    """Řetězec `box-shadow`: délky, hex nebo funkční barvy, `inset`, `none`; bez `var()`/`url()`; ≤400."""
    if not isinstance(value, str) or not 0 < len(value.strip()) <= MAX_SHADOW:
        return None
    text = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9 #%(),./+-]+", text):
        return None
    if any(color_literal(found) is None for found in INLINE_FUNCTION.findall(text)):
        return None
    rest = INLINE_FUNCTION.sub(" ", text)
    for part in re.split(r"[\s,]+", rest):
        if part and part.lower() not in ("inset", "none") and not HEX.match(part) and length(part) is None:
            return None
    return text


def plain_value(value):
    """Hodnota vlastní rodiny: jednoduchá CSS hodnota ≤200, vyvážené závorky, bez `url()`/`var()`."""
    text = _number_text(value)
    if not text or not PLAIN.match(text) or re.search(r"\b(?:url|var)\(", text, re.IGNORECASE):
        return None
    depth = 0
    for char in text:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth < 0:
            return None
    return text if depth == 0 else None


def _themes(raw, notes):
    shape(isinstance(raw, list), "tokens.color.themes musí být pole.")
    shape(len(raw) <= MAX_THEMES, f"Nejvýš {MAX_THEMES} témat.")
    themes = []
    for item in raw:
        shape(isinstance(item, dict), "Téma musí být objekt {id, name}.")
        identity = name_of(item.get("id"))
        identity = identity.lower() if identity else None
        if identity is None or any(theme["id"] == identity for theme in themes):
            notes.append(f"Téma {item.get('id')!r}: neplatné nebo duplicitní id, zahozeno.")
            continue
        label = clamp(item.get("name"), 64, f"Téma {identity}", notes) or identity
        themes.append({"id": identity, "name": label})
    return themes or [dict(theme) for theme in DEFAULT_THEMES]


def _tokens_list(family, raw, limit):
    shape(isinstance(raw, dict), f"tokens.{family} musí být objekt {{note?, tokens: []}}.")
    extra = sorted(set(raw) - {"note", "tokens", *(("themes",) if family == "color" else ())})
    shape(not extra, f"tokens.{family}: neznámé pole {', '.join(extra)} (rodina je seznam {{note?, tokens: []}}).")
    items = raw.get("tokens", [])
    shape(isinstance(items, list), f"tokens.{family}.tokens musí být pole.")
    shape(len(items) <= limit, f"tokens.{family}: nejvýš {limit} tokenů.")
    for item in items:
        shape(isinstance(item, dict), f"Token v tokens.{family} musí být objekt {{name, value, usage?}}.")
    return items


def _per_theme(value, themes, check, label, notes):
    """Hodnota `řetězec` (= první téma) nebo `{téma: hodnota}` → {téma: platná hodnota}."""
    ids = [theme["id"] for theme in themes]
    raw = value if isinstance(value, dict) else {ids[0]: value}
    kept = {}
    for theme, item in raw.items():
        if theme not in ids:
            notes.append(f"{label}: neznámé téma {theme!r}, zahozeno.")
        elif check(item) is None:
            notes.append(f"{label} [{theme}]: neplatná hodnota {item!r}, zahozena.")
        else:
            kept[theme] = check(item)
    return kept


def _color_or_alias(value):
    if isinstance(value, str) and ALIAS.match(value.strip()):
        return value.strip()
    return color_literal(value)


def _resolve_aliases(colors, ids, notes):
    """Zahodí aliasy na chybějící token, na sebe, v cyklu nebo hlubší než 16; chybějící téma dědí z prvního."""
    def effective(name, theme):
        values = colors.get(name, {}).get("value", {})
        return values.get(theme, values.get(ids[0]))

    def resolves(name, theme, seen):
        current = effective(name, theme)
        if current is None:
            return False
        match = ALIAS.match(current)
        if not match:
            return True
        target = match[1]
        if target in seen or len(seen) >= MAX_ALIAS_DEPTH:
            return False
        return resolves(target, theme, seen | {name})

    changed = True
    while changed:
        changed = False
        for name, token in list(colors.items()):
            for theme in list(token["value"]):
                if ALIAS.match(token["value"][theme]) and not resolves(name, theme, frozenset()):
                    notes.append(f"Barva {name} [{theme}]: alias {token['value'][theme]} nevede na platnou barvu, zahozen.")
                    del token["value"][theme]
                    changed = True
            if not token["value"]:
                notes.append(f"Barva {name}: žádná platná hodnota, zahozena.")
                del colors[name]
                changed = True


def _first_borrowed(value, ids):
    """Hodnota jen v pozdějším tématu se půjčí prvnímu tématu."""
    if ids[0] not in value:
        value[ids[0]] = next(value[theme] for theme in ids if theme in value)
    return value


def _named(item, family, used, notes):
    name = name_of(item.get("name"))
    if name is None:
        notes.append(f"{family}: neplatné jméno {item.get('name')!r}, token zahozen.")
        return None
    if name in used:
        notes.append(f"{family}: jméno {name} už je obsazené (jeden jmenný prostor), token zahozen.")
        return None
    return name


def _colors(raw, notes, used):
    shape(isinstance(raw, dict), "tokens.color musí být objekt {themes, tokens}.")
    themes = _themes(raw.get("themes", DEFAULT_THEMES), notes)
    ids = [theme["id"] for theme in themes]
    items = _tokens_list("color", raw, MAX_COLORS)
    colors = {}
    for item in items:
        name = _named(item, "color", used | set(colors), notes)
        if name is None:
            continue
        value = _per_theme(item.get("value"), themes, _color_or_alias, f"Barva {name}", notes)
        colors[name] = {"name": name, "value": value}
        usage = clamp(item.get("usage"), MAX_USAGE, f"Barva {name} usage", notes)
        if usage:
            colors[name]["usage"] = usage
    for name, token in list(colors.items()):
        if not token["value"]:
            notes.append(f"Barva {name}: žádná platná hodnota, zahozena.")
            del colors[name]
    _resolve_aliases(colors, ids, notes)
    tokens = []
    for token in colors.values():
        value = _first_borrowed(token["value"], ids)
        compact = value[ids[0]] if set(value) == {ids[0]} else {theme: value[theme] for theme in ids if theme in value}
        tokens.append({**token, "value": compact})
    used.update(colors)
    return {"themes": themes, "tokens": tokens}


def _family(family, raw, themes, notes, used):
    """Spacing, radius, shadow nebo vlastní rodina: `{note?, tokens: [{name, value, usage?}]}`."""
    items = _tokens_list(family, raw, MAX_FAMILY_TOKENS)
    out = {}
    note = clamp(raw.get("note"), MAX_NOTE, f"{family} note", notes)
    if note:
        out["note"] = note
    tokens = []
    ids = [theme["id"] for theme in themes]
    for item in items:
        name = _named(item, family, used, notes)
        if name is None:
            continue
        label = f"{family} {name}"
        if family == "shadow":
            value = _per_theme(item.get("value"), themes, shadow_literal, label, notes)
            value = _first_borrowed(value, ids) if value else value
            value = value.get(ids[0]) if set(value) == {ids[0]} else value or None
        else:
            check = length if family in ("spacing", "radius") else plain_value
            value = check(item.get("value"))
            if value is None:
                notes.append(f"{label}: neplatná hodnota {item.get('value')!r}, zahozena.")
        if not value:
            if family == "shadow":
                notes.append(f"{label}: žádná platná hodnota, zahozen.")
            continue
        token = {"name": name, "value": value}
        usage = clamp(item.get("usage"), MAX_USAGE, f"{label} usage", notes)
        if usage:
            token["usage"] = usage
        tokens.append(token)
        used.add(name)
    out["tokens"] = tokens
    return out


def _families(raw, notes):
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), "tokens.type.families musí být objekt {klíč: stack}.")
    shape(len(raw) <= MAX_FAMILIES, f"Nejvýš {MAX_FAMILIES} rodin písma.")
    families = {}
    for key, stack in raw.items():
        name = name_of(key)
        valid = (isinstance(stack, str) and 0 < len(stack.strip()) <= 200 and not STACK_FORBIDDEN.search(stack)
                 and stack.count('"') % 2 == 0 and stack.count("'") % 2 == 0)
        if name is None or not valid:
            notes.append(f"Rodina písma {key!r}: neplatný klíč nebo stack, zahozena.")
            continue
        families[name.lower()] = stack.strip()
    return families


def _font(item, notes):
    shape(isinstance(item, dict), "Font v tokens.type.fonts musí být objekt {family, file, weight?, style?}.")
    family, file = item.get("family"), item.get("file")
    if isinstance(file, str) and "/" not in file:
        file = f"fonts/{file}"
    weight = _number_text(item.get("weight", "400"))
    match = WEIGHT.match(weight or "")
    ok = (isinstance(family, str) and 0 < len(family) <= 100 and not STACK_FORBIDDEN.search(family)
          and '"' not in family and "'" not in family
          and isinstance(file, str) and file.startswith("fonts/") and FONT_FILE.match(file.removeprefix("fonts/"))
          and match and all(1 <= int(part) <= 1000 for part in match.groups() if part)
          and item.get("style", "normal") in ("normal", "italic", "oblique"))
    if not ok:
        notes.append(f"Font {item.get('family')!r} ({item.get('file')!r}): neplatný záznam, zahozen.")
        return None
    return {"family": family, "file": file, "weight": weight, "style": item.get("style", "normal")}


def _weight(value):
    if value in ("normal", "bold"):
        return 400 if value == "normal" else 700
    text = _number_text(value)
    match = WEIGHT.match(text or "")
    if not match or not all(1 <= int(part) <= 1000 for part in match.groups() if part):
        return None
    return int(match[1]) if match[2] is None else text


def _line_height(value):
    text = _number_text(value)
    if text and NUMBER.match(text) and text[-1].isdigit() and 0 <= float(text) < 10:
        return float(text) if "." in text else int(text)
    return length(value)


STYLE_FIELDS = {
    "lineHeight": _line_height,
    "fontWeight": _weight,
    "letterSpacing": length,
    "fontStyle": lambda value: value if value in ("normal", "italic") else None,
    "opticalSize": lambda value: value if isinstance(value, int | float) and not isinstance(value, bool) else None,
}


def _style(item, families, label, notes):
    shape(isinstance(item, dict), f"Styl ve skupině {label} musí být objekt {{name, fontSize, …}}.")
    name = name_of(item.get("name"))
    size = length(item.get("fontSize"))
    if name is None or size is None:
        notes.append(f"Styl {item.get('name')!r} ({label}): neplatné jméno nebo fontSize, zahozen.")
        return None
    style = {"name": name, "fontSize": size}
    for field, check in STYLE_FIELDS.items():
        if field in item:
            value = check(item[field])
            if value is None:
                notes.append(f"Styl {name} {field}: neplatná hodnota {item[field]!r}, zahozena.")
            else:
                style[field] = value
    if "family" in item:
        if item["family"] in families:
            style["family"] = item["family"]
        else:
            notes.append(f"Styl {name}: rodina {item['family']!r} neexistuje, zahozena.")
    for field, limit in (("sample", MAX_SAMPLE), ("usage", MAX_USAGE)):
        text = clamp(item.get(field), limit, f"Styl {name} {field}", notes)
        if text:
            style[field] = text
    return style


def _type(raw, notes):
    shape(isinstance(raw, dict), "tokens.type musí být objekt {fonts, families, groups}.")
    fonts, groups = raw.get("fonts", []), raw.get("groups", [])
    shape(isinstance(fonts, list) and len(fonts) <= MAX_FONTS, f"tokens.type.fonts: pole, nejvýš {MAX_FONTS}.")
    shape(isinstance(groups, list) and len(groups) <= MAX_GROUPS, f"tokens.type.groups: pole, nejvýš {MAX_GROUPS}.")
    families = _families(raw.get("families"), notes)
    out_groups, names, count = [], set(), 0
    for group in groups:
        shape(isinstance(group, dict), "Skupina typografie musí být objekt {name, family?, note?, styles}.")
        styles = group.get("styles", [])
        shape(isinstance(styles, list), "styles skupiny typografie musí být pole.")
        count += len(styles)
        shape(count <= MAX_STYLES, f"Nejvýš {MAX_STYLES} typografických stylů.")
        label = clamp(group.get("name"), 64, "Skupina typografie", notes) or "Text"
        out = {"name": label}
        if "family" in group:
            if group["family"] in families:
                out["family"] = group["family"]
            else:
                notes.append(f"Skupina {label}: rodina {group['family']!r} neexistuje, zahozena.")
        note = clamp(group.get("note"), MAX_NOTE, f"Skupina {label} note", notes)
        if note:
            out["note"] = note
        out["styles"] = []
        for item in styles:
            style = _style(item, families, label, notes)
            if style and style["name"] in names:
                notes.append(f"Styl {style['name']}: duplicitní jméno, zahozen.")
            elif style:
                names.add(style["name"])
                out["styles"].append(style)
        out_groups.append(out)
    kept_fonts = [font for font in (_font(item, notes) for item in fonts) if font]
    return {"fonts": kept_fonts, "families": families, "groups": out_groups}


def normalize_tokens(raw, notes):
    """Celý objekt `design.tokens` → normalizovaný tvar formátu; zahozené hodnoty přidá do `notes`."""
    raw = {} if raw is None else raw
    shape(isinstance(raw, dict), "design.tokens musí být objekt rodin.")
    custom = [key for key in raw if key not in FIXED and key != "version"]
    shape(len(custom) <= MAX_CUSTOM, f"Nejvýš {MAX_CUSTOM} vlastních rodin tokenů.")
    used = set()
    color = _colors(raw.get("color", {}), notes, used)
    out = {"color": color, "type": _type(raw.get("type", {}), notes)}
    for family in ("spacing", "radius", "shadow"):
        if family in raw:
            out[family] = _family(family, raw[family], color["themes"], notes, used)
    for key in custom:
        name = name_of(key)
        shape(name is not None, f"Vlastní rodina {key!r}: neplatný klíč.")
        out[name] = _family(name, raw[key], color["themes"], notes, used)
    return out
