"""Vzhled webu `settings.appearance`: přátelský pohled na tokeny, nikdy druhý zdroj pravdy (kontrakt M1 bod 3).

Každé pole Vzhledu je jeden token nebo pole typografického stylu (`FIELDS`). Při uložení se pole, které se liší od
pohledu na uložené tokeny, zapíše do `design.tokens`; potom se pohled spočítá z výsledných tokenů znovu. Pole, které
v těle chybí, se nemění; `null` token smaže (u velikosti stylu celý styl). Když člověk v jednom uložení upraví token
v Colors i pole Vzhledu, vyhraje Vzhled; zastaralý pohled z dřívějška token nepřepíše, protože se neliší od uloženého.
Neplatná hodnota se zahodí s poznámkou, neznámé pole je 422.
"""

import copy
import re

from backend.project.site_admin.tokens import ALIAS, color_literal, length, shape

STYLE_FIELDS = {"size": "fontSize", "weight": "fontWeight", "lineHeight": "lineHeight",
                "letterSpacing": "letterSpacing"}
DEFAULT_SIZES = {"h1": "2.5rem", "h2": "2rem", "h3": "1.5rem", "h4": "1.25rem", "h5": "1.125rem", "h6": "1rem",
                 "subheading": "1.25rem", "body": "1rem"}
ASSET = re.compile(r"^assets/[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}/[A-Za-z0-9][A-Za-z0-9 _.-]{0,132}$")
STACK = re.compile(r"^[^;{}<>\\()]{1,200}$")
PATTERNS = ("dots", "grid", "lines", "diagonal")
MARKERS = ("disc", "circle", "square", "decimal", "decimal-leading-zero", "lower-alpha", "upper-alpha",
           "lower-roman", "upper-roman", "none")


def _color(value):
    if isinstance(value, str) and ALIAS.match(value.strip()):
        return value.strip()
    return color_literal(value)


def _enum(*allowed):
    return lambda value: value if value in allowed else None


def _number(low, high):
    def check(value):
        ok = isinstance(value, int | float) and not isinstance(value, bool) and low <= value <= high
        return f"{value:g}" if ok else None
    return check


def _stack(value):
    ok = isinstance(value, str) and STACK.match(value.strip()) and value.count('"') % 2 == 0 \
        and value.count("'") % 2 == 0
    return value.strip() if ok else None


def _weight(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 1000 else None


def _line_height(value):
    if isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value < 10:
        return value
    return length(value)


# Cesta pole → (druh, cíl, kontrola). Druhy: color = barevný token, family = rodina písma (`type.families`),
# plain = token vlastní rodiny, style = pole typografického stylu (skupina, styl, pole).
FIELDS = {
    "background.color": ("color", "surface", _color),
    "background.image.asset": ("plain", ("background", "bg-image"), lambda v: v if isinstance(v, str) and ASSET.match(v) else None),
    "background.image.size": ("plain", ("background", "bg-size"), _enum("cover", "contain", "auto")),
    "background.image.position": ("plain", ("background", "bg-position"),
                                  _enum("center", "top", "bottom", "left", "right", "top left", "top right",
                                        "bottom left", "bottom right")),
    "background.image.repeat": ("plain", ("background", "bg-repeat"),
                                _enum("no-repeat", "repeat", "repeat-x", "repeat-y")),
    "background.image.attachment": ("plain", ("background", "bg-attachment"), _enum("scroll", "fixed")),
    "background.pattern.preset": ("plain", ("background", "bg-pattern"), _enum(*PATTERNS)),
    "background.pattern.color": ("color", "pattern", _color),
    "background.pattern.scale": ("plain", ("background", "bg-pattern-scale"), _number(0.25, 8)),
    "background.overlay.color": ("color", "overlay", _color),
    "background.overlay.opacity": ("plain", ("background", "bg-overlay-opacity"), _number(0, 1)),
    "text.heading.font": ("family", "heading", _stack),
    "text.subheading.font": ("family", "subheading", _stack),
    "text.subheading.size": ("style", ("Text", "subheading", "fontSize"), length),
    "text.body.font": ("family", "body", _stack),
    "text.body.size": ("style", ("Text", "body", "fontSize"), length),
    "colors.text": ("color", "ink", _color),
    "colors.textInverse": ("color", "ink-inverse", _color),
    "colors.link": ("color", "link", _color),
    "colors.linkHover": ("color", "link-hover", _color),
    "colors.focus": ("color", "focus", _color),
    **{f"headings.h{level}.{field}": ("style", ("Nadpisy", f"h{level}", target),
                                      {"fontSize": length, "fontWeight": _weight, "lineHeight": _line_height,
                                       "letterSpacing": length}[target])
       for level in range(1, 7) for field, target in STYLE_FIELDS.items()},
    "lists.marker": ("plain", ("list", "list-style"), _enum(*MARKERS)),
    "lists.color": ("color", "list-marker", _color),
    "lists.indent": ("plain", ("list", "list-indent"), length),
    "layout.contentSize": ("plain", ("layout", "layout-content"), length),
    "layout.wideSize": ("plain", ("layout", "layout-wide"), length),
    "layout.gutter": ("plain", ("layout", "layout-gutter"), length),
}
STYLE_FAMILY = {"Nadpisy": "heading", "subheading": "subheading", "body": "body"}


def _leaves(raw, prefix=""):
    """Tělo Vzhledu → {cesta: hodnota}; neznámé pole je 422."""
    shape(isinstance(raw, dict), f"settings.appearance{prefix and '.' + prefix} musí být objekt.")
    out = {}
    for key, value in raw.items():
        path = f"{prefix}.{key}" if prefix else key
        if path in FIELDS:
            out[path] = value
        else:
            shape(any(field.startswith(path + ".") for field in FIELDS) and isinstance(value, dict),
                  f"settings.appearance: neznámé pole {path}.")
            out.update(_leaves(value, path))
    return out


def _style(tokens, name):
    return next((style for group in tokens["type"]["groups"] for style in group["styles"] if style["name"] == name),
                None)


def _family_tokens(tokens, family):
    return tokens.get(family, {}).get("tokens", [])


def _read(tokens, kind, target):
    if kind == "color":
        token = next((t for t in tokens["color"]["tokens"] if t["name"] == target), None)
        value = token["value"] if token else None
        return next(iter(value.values())) if isinstance(value, dict) else value
    if kind == "family":
        return tokens["type"]["families"].get(target)
    if kind == "plain":
        value = next((t["value"] for t in _family_tokens(tokens, target[0]) if t["name"] == target[1]), None)
        if value is not None and target[1] in ("bg-pattern-scale", "bg-overlay-opacity"):
            return float(value)
        return value
    style = _style(tokens, target[1])
    return style.get(target[2]) if style else None


def view(tokens):
    """Normalizované tokeny → celý Vzhled (chybějící pole = `null`)."""
    out = {}
    for path, (kind, target, _) in FIELDS.items():
        node = out
        *parents, leaf = path.split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = _read(tokens, kind, target)
    return out


def _write(tokens, kind, target, value):
    if kind == "color":
        colors = tokens["color"]["tokens"]
        token = next((t for t in colors if t["name"] == target), None)
        if value is None:
            colors[:] = [t for t in colors if t["name"] != target]
        elif token is None:
            colors.append({"name": target, "value": value})
        elif isinstance(token["value"], dict):
            token["value"][next(iter(token["value"]))] = value
        else:
            token["value"] = value
    elif kind == "family":
        families = tokens["type"]["families"]
        families.pop(target, None) if value is None else families.__setitem__(target, value)
    elif kind == "plain":
        family, name = target
        items = [t for t in _family_tokens(tokens, family) if t["name"] != name]
        if value is not None:
            current = next((t for t in _family_tokens(tokens, family) if t["name"] == name), {"name": name})
            items.append({**current, "value": value})
        tokens.setdefault(family, {})["tokens"] = items
    else:
        _write_style(tokens, *target, value)


def _write_style(tokens, group_name, name, field, value):
    style = _style(tokens, name)
    if style is None and value is None:
        return
    if value is None and field == "fontSize":
        for group in tokens["type"]["groups"]:
            group["styles"] = [s for s in group["styles"] if s["name"] != name]
        return
    if style is None:
        group = next((g for g in tokens["type"]["groups"] if g["name"] == group_name), None)
        if group is None:
            group = {"name": group_name, "styles": []}
            tokens["type"]["groups"].append(group)
        style = {"name": name, "fontSize": DEFAULT_SIZES[name]}
        family = STYLE_FAMILY.get(group_name) or STYLE_FAMILY.get(name)
        if family in tokens["type"]["families"]:
            style["family"] = family
        group["styles"].append(style)
    if value is None:
        style.pop(field, None)
    else:
        style[field] = value


def project(raw, tokens, base_tokens, notes):
    """Promítne změněná pole Vzhledu do (normalizovaných) `tokens`; vrací nový objekt tokenů k normalizaci."""
    if raw is None:
        return tokens
    leaves = _leaves(raw)
    base = {path: _read(base_tokens, *FIELDS[path][:2]) for path in leaves}
    out = copy.deepcopy(tokens)
    for path, value in leaves.items():
        if value == base[path]:
            continue
        kind, target, check = FIELDS[path]
        kept = None if value is None else check(value)
        if value is not None and kept is None:
            notes.append(f"settings.appearance.{path}: neplatná hodnota {value!r}, zahozena.")
            continue
        _write(out, kind, target, kept)
    return out
