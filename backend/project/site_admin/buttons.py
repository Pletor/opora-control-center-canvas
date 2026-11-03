"""Tlačítka webu `settings.buttons`: komponentní tokeny, CSS a poznámky k přístupnosti (research §2, §5).

Tvar:

    {"sizes": {"sm"|"md"|"lg": {paddingX, paddingY, minHeight, fontSize}},
     "variants": {<slug>: {"label"?, "preset": solid|outline|ghost|link,
                           "states": {"default": {…}, "hover", "active", "focusVisible", "disabled"}}}}

Vlastnosti stavu: `background` (barva nebo `{gradient: {angle, stops: [{color, position 0–1}]}}`), `color`,
`border` {width, style, color}, `radius` (předvolba none|sm|md|lg|pill nebo délka), `font` {family, weight,
letterSpacing, transform}, `shadow`, `transition` {properties, duration, easing}, `width` auto|full a jen ve
`focusVisible` `outline` {width, style, color, offset}. Barva i délka smí být alias `{token}`.

Stav kromě `default` ukládá jen rozdíl proti `default`. Neznámý klíč, varianta nebo stav = 422; neplatná hodnota a
alias na chybějící token se zahodí s poznámkou. Kontrast, velikost cíle a focus ring jsou poznámky, ne chyby.
"""

import re

from backend.project.site_admin.tokens import (
    ALIAS,
    HEX,
    SiteAdminInvalid,
    color_literal,
    length,
    shadow_literal,
    shape,
)

SLUG = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
SIZES = ("sm", "md", "lg")
STATES = ("default", "hover", "active", "focusVisible", "disabled")
PRESETS = ("solid", "outline", "ghost", "link")
RADIUS = {"none": "0", "sm": "4px", "md": "8px", "lg": "16px", "pill": "999px"}
BORDER_STYLES = ("solid", "dashed", "dotted", "double", "none")
TRANSFORMS = ("none", "uppercase", "lowercase", "capitalize")
TRANSITION_PROPERTIES = ("background-color", "background", "color", "border-color", "box-shadow", "transform",
                         "opacity", "outline-color", "all")
EASING = re.compile(r"^(?:ease|ease-in|ease-out|ease-in-out|linear|cubic-bezier\((?:\s*-?[\d.]+\s*,){3}\s*-?[\d.]+\s*\))$")
DURATION = re.compile(r"^\d{1,5}(?:\.\d+)?(?:ms|s)$")
MAX_VARIANTS, MAX_STOPS = 16, 8
DEFAULT_SIZES = {"sm": {"paddingX": "0.875rem", "paddingY": "0.375rem", "minHeight": "32px", "fontSize": "0.875rem"},
                 "md": {"paddingX": "1.5rem", "paddingY": "0.625rem", "minHeight": "44px", "fontSize": "1rem"},
                 "lg": {"paddingX": "2rem", "paddingY": "0.875rem", "minHeight": "52px", "fontSize": "1.125rem"}}
STATE_SELECTORS = {"default": "", "hover": ':hover:not(:disabled):not([aria-disabled="true"])',
                   "active": ':active:not(:disabled):not([aria-disabled="true"])', "focusVisible": ":focus-visible",
                   "disabled": ':disabled, .ds-btn--{v}[aria-disabled="true"]'}


def _record(raw, fields, path):
    shape(isinstance(raw, dict), f"{path} musí být objekt.")
    unknown = sorted(set(raw) - set(fields))
    shape(not unknown, f"{path}: neznámé pole {', '.join(unknown)}.")
    return raw


class _Values:
    """Kontrola hodnot s aliasy na existující tokeny; neplatné se zahodí s poznámkou."""

    def __init__(self, tokens, notes):
        self.colors = {token["name"] for token in tokens["color"]["tokens"]}
        self.names = self.colors | {t["name"] for key, family in tokens.items() if key not in ("color", "type")
                                    for t in family.get("tokens", [])}
        self.families = set(tokens["type"]["families"])
        self.notes = notes

    def keep(self, value, check, path):
        if value is None:
            return None
        result = check(value)
        if result is None:
            self.notes.append(f"{path}: neplatná hodnota {value!r}, zahozena.")
        return result

    def alias(self, value, pool):
        match = ALIAS.match(value.strip()) if isinstance(value, str) else None
        return value.strip() if match and match[1] in pool else None

    def color(self, value):
        if value in ("transparent", "currentColor"):
            return value
        return self.alias(value, self.colors) or color_literal(value)

    def length(self, value):
        return self.alias(value, self.names) or length(value)

    def radius(self, value):
        return value if value in RADIUS else self.length(value)

    def shadow(self, value):
        return "none" if value == "none" else self.alias(value, self.names) or shadow_literal(value)

    def background(self, value):
        if not isinstance(value, dict):
            return self.color(value)
        if set(value) != {"gradient"} or not isinstance(value["gradient"], dict):
            return None
        gradient = value["gradient"]
        angle, stops = gradient.get("angle", 180), gradient.get("stops")
        if set(gradient) - {"angle", "stops"} or isinstance(angle, bool) or not isinstance(angle, int | float) \
                or not 0 <= angle <= 360 or not isinstance(stops, list) or not 2 <= len(stops) <= MAX_STOPS:
            return None
        kept = []
        for stop in stops:
            if not isinstance(stop, dict) or set(stop) != {"color", "position"}:
                return None
            color, position = self.color(stop["color"]), stop["position"]
            if color is None or isinstance(position, bool) or not isinstance(position, int | float) \
                    or not 0 <= position <= 1:
                return None
            kept.append({"color": color, "position": position})
        return {"gradient": {"angle": angle, "stops": kept}}


def _sub(raw, fields, path, values):
    """Vnořený objekt (border, outline, font, transition) → jen platná pole; prázdný = None."""
    _record(raw, fields, path)
    out = {key: values.keep(raw[key], check, f"{path}.{key}") for key, check in fields.items() if key in raw}
    out = {key: value for key, value in out.items() if value is not None}
    return out or None


def _transition_properties(value):
    if isinstance(value, list) and 0 < len(value) <= len(TRANSITION_PROPERTIES) and all(
            item in TRANSITION_PROPERTIES for item in value):
        return list(dict.fromkeys(value))
    return None


def _state(raw, name, path, values):
    fields = ["background", "color", "border", "radius", "font", "shadow", "transition", "width"]
    _record(raw, fields + (["outline"] if name == "focusVisible" else []), path)
    pick = lambda value: value if value in (*BORDER_STYLES,) else None
    nested = {
        "border": {"width": values.length, "style": pick, "color": values.color},
        "outline": {"width": values.length, "style": pick, "color": values.color, "offset": values.length},
        "font": {"family": lambda v: v if v in values.families else None,
                 "weight": lambda v: v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 1000 else None,
                 "letterSpacing": values.length, "transform": lambda v: v if v in TRANSFORMS else None},
        "transition": {"properties": _transition_properties,
                       "duration": lambda v: v if isinstance(v, str) and DURATION.match(v) else None,
                       "easing": lambda v: v if isinstance(v, str) and EASING.match(v) else None},
    }
    plain = {"background": values.background, "color": values.color, "radius": values.radius,
             "shadow": values.shadow, "width": lambda v: v if v in ("auto", "full") else None}
    out = {}
    for key, value in raw.items():
        kept = _sub(value, nested[key], f"{path}.{key}", values) if key in nested else \
            values.keep(value, plain[key], f"{path}.{key}")
        if kept is not None:
            out[key] = kept
    return out


def _diff(state, default):
    """Jen to, co se liší od `default` (u vnořených objektů po polích)."""
    out = {}
    for key, value in state.items():
        if isinstance(value, dict) and "gradient" not in value and isinstance(default.get(key), dict):
            changed = {k: v for k, v in value.items() if default[key].get(k) != v}
            if changed:
                out[key] = changed
        elif default.get(key) != value:
            out[key] = value
    return out


def _sizes(raw, values):
    raw = {} if raw is None else _record(raw, SIZES, "settings.buttons.sizes")
    out = {}
    for size in SIZES:
        given = _record(raw.get(size, {}), ("paddingX", "paddingY", "minHeight", "fontSize"),
                        f"settings.buttons.sizes.{size}")
        out[size] = {key: values.keep(given.get(key), values.length, f"settings.buttons.sizes.{size}.{key}")
                     or default for key, default in DEFAULT_SIZES[size].items()}
    return out


def normalize(raw, tokens, notes):
    """`settings.buttons` → normalizovaný tvar; poznámky (zahozené hodnoty, přístupnost) do `notes`."""
    raw = {} if raw is None else _record(raw, ("sizes", "variants"), "settings.buttons")
    values = _Values(tokens, notes)
    variants = raw.get("variants", {})
    shape(isinstance(variants, dict) and len(variants) <= MAX_VARIANTS,
          f"settings.buttons.variants musí být objekt o nejvýš {MAX_VARIANTS} variantách.")
    out = {"sizes": _sizes(raw.get("sizes"), values), "variants": {}}
    for name, variant in variants.items():
        path = f"settings.buttons.variants.{name}"
        shape(isinstance(name, str) and SLUG.match(name) and name not in SIZES,
              f"{path}: jméno varianty a-z0-9- (ne sm, md, lg).")
        _record(variant, ("label", "preset", "states"), path)
        shape(variant.get("preset", "solid") in PRESETS, f"{path}.preset je {'|'.join(PRESETS)}.")
        label = variant.get("label")
        shape(label is None or isinstance(label, str) and len(label) <= 64, f"{path}.label je text do 64 znaků.")
        states = _record(variant.get("states", {}), STATES, f"{path}.states")
        default = _state(states.get("default", {}), "default", f"{path}.states.default", values)
        kept = {"default": default}
        for state in STATES[1:]:
            if state in states:
                diff = _diff(_state(states[state], state, f"{path}.states.{state}", values), default)
                if diff:
                    kept[state] = diff
        out["variants"][name] = {**({"label": label} if label else {}), "preset": variant.get("preset", "solid"),
                                 "states": kept}
    notes += accessibility(out, tokens)
    return out


# --- CSS ---------------------------------------------------------------------------------------------------------

def _css_value(value):
    match = ALIAS.match(value) if isinstance(value, str) else None
    return "var(--" + match[1].replace(".", "\\.") + ")" if match else value


def _background(value):
    if isinstance(value, dict):
        gradient = value["gradient"]
        stops = ", ".join(f"{_css_value(s['color'])} {s['position'] * 100:g}%" for s in gradient["stops"])
        return f"linear-gradient({gradient['angle']:g}deg, {stops})"
    return _css_value(value)


def _properties(state):
    """Stav → deklarace komponentních tokenů `--btn-*`."""
    lines = []
    for key, value in state.items():
        if key == "background":
            lines.append(f"--btn-bg: {_background(value)};")
        elif key in ("color", "shadow"):
            lines.append(f"--btn-{key}: {_css_value(value)};")
        elif key == "radius":
            lines.append(f"--btn-radius: {_css_value(RADIUS.get(value, value))};")
        elif key == "width":
            lines.append(f"--btn-width: {'100%' if value == 'full' else 'auto'};")
        elif key in ("border", "outline"):
            prefix = "--btn-border" if key == "border" else "--btn-ring"
            lines += [f"{prefix}-{field}: {_css_value(item)};" for field, item in value.items()]
        elif key == "font":
            names = {"family": "--btn-font-family", "weight": "--btn-font-weight",
                     "letterSpacing": "--btn-letter-spacing", "transform": "--btn-text-transform"}
            lines += [f"{names[field]}: {f'var(--font-{item})' if field == 'family' else _css_value(item)};"
                      for field, item in value.items()]
        elif key == "transition":
            properties = value.get("properties", ["background-color", "color", "border-color", "box-shadow"])
            timing = f"{value.get('duration', '150ms')} {value.get('easing', 'ease')}"
            lines.append(f"--btn-transition: {', '.join(f'{p} {timing}' for p in properties)};")
    return lines


BASE = [
    "--btn-bg: transparent;", "--btn-color: currentColor;", "--btn-border-width: 0;", "--btn-border-style: solid;",
    "--btn-border-color: transparent;", "--btn-radius: 0;", "--btn-font-family: inherit;", "--btn-font-weight: 600;",
    "--btn-letter-spacing: normal;", "--btn-text-transform: none;", "--btn-shadow: none;", "--btn-transition: none;",
    "--btn-width: auto;", "--btn-ring-width: 2px;", "--btn-ring-style: solid;",
    "--btn-ring-color: var(--focus, currentColor);", "--btn-ring-offset: 2px;",
]
RULES = [
    "display: inline-flex;", "align-items: center;", "justify-content: center;", "gap: 0.5em;",
    "box-sizing: border-box;", "padding: var(--btn-py) var(--btn-px);", "min-height: var(--btn-min-height);",
    "width: var(--btn-width);", "font-family: var(--btn-font-family);", "font-size: var(--btn-font-size);",
    "font-weight: var(--btn-font-weight);", "letter-spacing: var(--btn-letter-spacing);",
    "text-transform: var(--btn-text-transform);", "line-height: 1.2;", "text-decoration: none;",
    "background: var(--btn-bg);", "color: var(--btn-color);",
    "border: var(--btn-border-width) var(--btn-border-style) var(--btn-border-color);",
    "border-radius: var(--btn-radius);", "box-shadow: var(--btn-shadow);", "transition: var(--btn-transition);",
    "cursor: pointer;",
]


def _size_lines(size):
    return [f"--btn-px: {_css_value(size['paddingX'])};", f"--btn-py: {_css_value(size['paddingY'])};",
            f"--btn-min-height: {_css_value(size['minHeight'])};", f"--btn-font-size: {_css_value(size['fontSize'])};"]


def _block(selector, lines, indent="  "):
    return [f"{indent}{selector} {{", *(f"{indent}  {line}" for line in lines), f"{indent}}}"] if lines else []


def css(buttons):
    """Pravidla `@layer components` (bez obalu): `.ds-btn`, velikosti, varianty a jejich stavy, jen přes `var()`."""
    out = _block(".ds-btn", [*BASE, *_size_lines(buttons["sizes"]["md"]), *RULES])
    out += _block(".ds-btn:focus-visible", ["outline: var(--btn-ring-width) var(--btn-ring-style) var(--btn-ring-color);",
                                            "outline-offset: var(--btn-ring-offset);"])
    out += _block('.ds-btn:disabled, .ds-btn[aria-disabled="true"]', ["cursor: not-allowed;"])
    for size in SIZES:
        out += _block(f".ds-btn--{size}", _size_lines(buttons["sizes"][size]))
    for name, variant in buttons["variants"].items():
        for state, properties in variant["states"].items():
            selector = f".ds-btn--{name}" + STATE_SELECTORS[state].replace("{v}", name)
            out += _block(selector, _properties(properties))
    return out


# --- Přístupnost -------------------------------------------------------------------------------------------------

def _rgb(value, colors, depth=0):
    """Barva (hex, `rgb()` s čísly nebo alias) → (r, g, b) 0–255 v prvním tématu; jinak None."""
    if not isinstance(value, str) or depth > 16:
        return None
    match = ALIAS.match(value)
    if match:
        target = colors.get(match[1])
        target = next(iter(target.values())) if isinstance(target, dict) else target
        return _rgb(target, colors, depth + 1)
    if HEX.match(value):
        digits = value[1:]
        digits = "".join(c * 2 for c in digits) if len(digits) in (3, 4) else digits
        return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
    found = re.fullmatch(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*(?:[,/]\s*[\d.]+%?\s*)?\)", value.strip())
    return tuple(min(255.0, float(part)) for part in found.groups()) if found else None


def _luminance(rgb):
    channel = [c / 255 for c in rgb]
    channel = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channel]
    return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2]


def contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _px(value):
    found = re.fullmatch(r"([\d.]+)(px|rem|em)", value or "")
    return float(found[1]) * (1 if found[2] == "px" else 16) if found else None


def accessibility(buttons, tokens):
    """Poznámky WCAG 2.2: text ≥ 4,5:1 (stavy kromě disabled), rámeček a focus ≥ 3:1, cíl ≥ 24 px, focus ring."""
    colors = {t["name"]: t["value"] for t in tokens["color"]["tokens"]}
    page = _rgb("{surface}", colors) or (255, 255, 255)
    notes = []
    for size, values in buttons["sizes"].items():
        height = _px(values["minHeight"])
        if height is not None and height < 24:
            notes.append(f"Tlačítka {size}: minHeight {values['minHeight']} je pod 24 px (WCAG 2.5.8).")
    for name, variant in buttons["variants"].items():
        default, checked = variant["states"]["default"], set()
        for state in STATES[:-1]:
            merged = {**default, **variant["states"].get(state, {})}
            border = {**default.get("border", {}), **variant["states"].get(state, {}).get("border", {})}
            seen = repr((merged.get("color"), merged.get("background"), border))
            if seen in checked:  # stav se stejnými barvami jako už ověřený nehlásí totéž znovu
                continue
            checked.add(seen)
            label = f"Tlačítko {name} ({state})"
            background = merged.get("background")
            backgrounds = [s["color"] for s in background["gradient"]["stops"]] if isinstance(background, dict) \
                else [background]
            text = _rgb(merged.get("color"), colors)
            for item in backgrounds:
                fill = page if item in (None, "transparent") else _rgb(item, colors)
                if text and fill and contrast(text, fill) < 4.5:
                    notes.append(f"{label}: kontrast textu {contrast(text, fill):.2f}:1 je pod 4,5:1.")
            border_color = _rgb(border.get("color"), colors)
            if border_color and _px(border.get("width")) and contrast(border_color, page) < 3:
                notes.append(f"{label}: rámeček má proti pozadí stránky {contrast(border_color, page):.2f}:1, pod 3:1.")
        ring = variant["states"].get("focusVisible", {})
        outline = ring.get("outline", {})
        ring_color = _rgb(outline.get("color", "{focus}"), colors)
        if ring_color and contrast(ring_color, page) < 3:
            notes.append(f"Tlačítko {name}: focus ring má proti pozadí {contrast(ring_color, page):.2f}:1, pod 3:1.")
        if (outline.get("style") == "none" or outline.get("width") == "0") and "shadow" not in ring:
            notes.append(f"Tlačítko {name}: focus ring je vypnutý bez náhrady (stín nebo outline).")
    return notes


__all__ = ["SiteAdminInvalid", "accessibility", "contrast", "css", "normalize"]
