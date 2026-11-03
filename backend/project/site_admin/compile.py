"""Odvozené soubory design systému: `tokens.css`, `tokens.json` a `README.md` (kontrakt §2).

Generuje je jen server z normalizovaného dokumentu (`design_system.normalize`), ručně se nepíšou. Rozvržení
`tokens.css` je podle formátu Design System:

1. `/* <titulek> — generated from tokens.json */`
2. `:root, [data-theme="<první>"] { barvy; stíny }`
3. `[data-theme="<id>"] { … }` pro každé další téma: hodnoty, které se liší od prvního tématu, a znovu všechny aliasy
   (vlastní vlastnost s `var()` se počítá na prvku, kde je deklarovaná)
4. `:root { --space-*; --radius-*; vlastní rodiny; --font-<klíč> }`
5. třída `.<styl>` na každý typografický styl, `@font-face` na každý font (`url("fonts/<soubor>")` vedle `tokens.css`)

`components.css` jde po `tokens.css`: `@layer base` (prvky stránky z tokenů Vzhledu, jen ty tokeny, které existují),
`@layer components` (tlačítka `.ds-btn`, jen přes `var()`) a `@layer custom` (sanitizované vlastní CSS).
"""

import json
import re

from backend.project.site_admin import buttons as button_css
from backend.project.site_admin.custom_css import compile_button
from backend.project.site_admin.tokens import ALIAS, FIXED

PATTERNS = {  # vzorek pozadí → vrstvy background-image (velikost buňky násobí --bg-pattern-scale)
    "dots": ["radial-gradient(var(--pattern, currentColor) 1px, transparent 1.5px)"],
    "grid": ["linear-gradient(var(--pattern, currentColor) 1px, transparent 1px)",
             "linear-gradient(90deg, var(--pattern, currentColor) 1px, transparent 1px)"],
    "lines": ["linear-gradient(var(--pattern, currentColor) 1px, transparent 1px)"],
    "diagonal": ["repeating-linear-gradient(45deg, var(--pattern, currentColor) 0 1px, transparent 1px 12px)"],
}

FONT_FORMATS = {"woff2": "woff2", "woff": "woff", "ttf": "truetype", "otf": "opentype", "ttc": "collection"}
STYLE_CSS = (("fontSize", "font-size"), ("lineHeight", "line-height"), ("fontWeight", "font-weight"),
             ("letterSpacing", "letter-spacing"), ("fontStyle", "font-style"))


def _ident(name):
    return name.replace(".", "\\.")


def _value(raw):
    match = ALIAS.match(raw)
    return f"var(--{_ident(match[1])})" if match else raw


def _per_theme(token, theme, first):
    value = token["value"]
    return value if isinstance(value, str) else value.get(theme, value.get(first))


def _block(selector, lines):
    return [f"{selector} {{", *(f"  {line}" for line in lines), "}"] if lines else []


def _style_lines(group, style):
    family = style.get("family") or group.get("family")
    lines = [f"font-family: var(--font-{_ident(family)});"] if family else []
    lines += [f"{css}: {style[key]};" for key, css in STYLE_CSS if key in style]
    if "opticalSize" in style:
        lines.append(f"font-variation-settings: 'opsz' {style['opticalSize']:g};")
    return lines


def tokens_css(document):
    title = (document.get("title") or "Design system").replace("*/", "* /")
    tokens = document["design"]["tokens"]
    themes = [theme["id"] for theme in tokens["color"]["themes"]]
    first = themes[0]
    themed = tokens["color"]["tokens"] + tokens.get("shadow", {}).get("tokens", [])
    out = [f"/* {title} — generated from tokens.json */"]
    out += _block(f':root, [data-theme="{first}"]',
                  [f"--{_ident(t['name'])}: {_value(_per_theme(t, first, first))};" for t in themed])
    for theme in themes[1:]:
        lines = []
        for token in themed:
            raw = _per_theme(token, theme, first)
            if raw != _per_theme(token, first, first) or ALIAS.match(raw):
                lines.append(f"--{_ident(token['name'])}: {_value(raw)};")
        out += _block(f'[data-theme="{theme}"]', lines)
    plain = [key for key in tokens if key not in FIXED or key in ("spacing", "radius")]
    plain.sort(key=lambda key: (key != "spacing", key != "radius"))
    lines = [f"--{_ident(t['name'])}: {t['value']};" for key in plain for t in tokens[key]["tokens"]]
    lines += [f"--font-{_ident(key)}: {stack};" for key, stack in tokens["type"]["families"].items()]
    out += _block(":root", lines)
    for group in tokens["type"]["groups"]:
        for style in group["styles"]:
            out += _block(f".{_ident(style['name'])}", _style_lines(group, style))
    for font in tokens["type"]["fonts"]:
        extension = font["file"].rsplit(".", 1)[-1].lower()
        out += _block("@font-face", [f'font-family: "{font["family"]}";',
                                     f'src: url("{font["file"]}") format("{FONT_FORMATS[extension]}");',
                                     f"font-weight: {font['weight']};", f"font-style: {font['style']};",
                                     "font-display: swap;"])
    return "\n".join(out) + "\n"


def tokens_json(document):
    """Tokeny v gramatice formátu (`version: 1` + rodiny), čitelné nástroji, které formát znají."""
    return json.dumps({"version": 1, **document["design"]["tokens"]}, ensure_ascii=False, indent=2) + "\n"


def _first_sentence(markdown):
    text = re.sub(r"^#.*$", "", markdown or "", flags=re.MULTILINE).strip()
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0] if text else ""


def readme(document):
    """Brand book (README a sekce) a pod čarou generovaná sekce „Jak systém použít“."""
    design = document["design"]
    tokens = design["tokens"]
    title = document.get("title") or "Design system"
    out = [design["readme"].strip() or f"# {title}"]
    out += [section["markdown"].strip() or f"## {section['title']}" for section in design["sections"]]
    themes = ", ".join(f"`{theme['id']}`" for theme in tokens["color"]["themes"])
    out += ["---", "", "## Jak systém použít", "",
            "- Načti `tokens.css` jako první stylesheet. Hodnoty nikdy nepiš natvrdo, jen `var(--jméno)`.",
            f"- Témata: {themes}. Přepíná je atribut `data-theme` na `<html>`; první je výchozí.",
            "- Typografii dávej třídou stylu (`.jméno`), ne vlastním `font-size`.",
            ("- Po něm načti `components.css`: prvky stránky z Vzhledu (`body`, `h1`–`h6`, `a`, seznamy, kontejner "
             "`.ds-container`, inverzní text `.ds-inverse`), tlačítka `.ds-btn` a sanitizované vlastní CSS."),
            ("- Zdroj pravdy je dokument Správy webu v OPOŘE. `tokens.css`, `components.css`, `tokens.json` a tento "
             "README generuje server.")]
    families = [f"- `{family}`: {len(tokens[family]['tokens'])} tokenů" for family in tokens
                if family != "type" and tokens[family].get("tokens")]
    if families:
        out += ["", "### Tokeny", "", *families]
    styles = [f"`.{style['name']}`" for group in tokens["type"]["groups"] for style in group["styles"]]
    if styles:
        out += ["", "### Typografie", "", "Styly: " + ", ".join(styles) + "."]
    fonts = {font["family"]: font["file"] for font in tokens["type"]["fonts"]}
    if tokens["type"]["families"] or fonts:
        out += ["", "### Písma", ""]
        out += [f"- `--font-{key}`: {stack}" for key, stack in tokens["type"]["families"].items()]
        out += [f"- {family}: soubor `{file}` (`@font-face` v `tokens.css`)" for family, file in fonts.items()]
    if design["components"]:
        out += ["", "### Komponenty", ""]
        for component in design["components"]:
            summary = component.get("summary") or _first_sentence(component["readme"])
            group = f" ({component['group']})" if component.get("group") else ""
            out.append(f"- **{component['name']}**{group}" + (f": {summary}" if summary else ""))
    variants = document["settings"]["buttons"]["variants"]
    if variants:
        out += ["", "### Tlačítka", "", ("Třída `ds-btn`, varianta `ds-btn--<varianta>` a volitelně velikost "
                "`ds-btn--sm|md|lg` (výchozí md). Stavy hover, active, focus-visible a disabled (`disabled` nebo "
                "`aria-disabled=\"true\"`) řeší `components.css`, nepiš je znovu."), ""]
        for name, variant in variants.items():
            label = variant.get("label") or name.capitalize()
            tag = (f'<a class="ds-btn ds-btn--{name}" href="…">{label}</a>' if variant["preset"] == "link"
                   else f'<button class="ds-btn ds-btn--{name}" type="button">{label}</button>')
            out.append(f"- **{name}** ({variant['preset']}): `{tag}`")
    if design["assetGroups"]:
        out += ["", "### Assety", "", "Assety kopíruj, nikdy je nekresli znovu.", ""]
        for group in design["assetGroups"]:
            files = ", ".join(f"`{file['blob']}`" for file in group["files"]) or "zatím prázdná"
            out.append(f"- {group['name']}: {files}")
    return "\n\n".join(out[:out.index("---")]) + "\n\n" + "\n".join(out[out.index("---"):]) + "\n"


def _base(tokens):
    """Prvky stránky z tokenů Vzhledu (`appearance.py`): pozadí, text, odkazy, nadpisy, seznamy, kontejner."""
    names = {t["name"] for key, family in tokens.items() if key != "type" for t in family.get("tokens", [])}
    plain = {t["name"]: t["value"] for key, family in tokens.items() if key not in FIXED
             for t in family.get("tokens", [])}
    families = tokens["type"]["families"]
    has = lambda *wanted: all(name in names for name in wanted)
    styles = {style["name"]: (group, style) for group in tokens["type"]["groups"] for style in group["styles"]}
    text = _style_lines(*styles["body"]) if "body" in styles else []
    if "body" in families and not any(line.startswith("font-family") for line in text):
        text.insert(0, "font-family: var(--font-body);")
    body = [*(["background-color: var(--surface);"] if has("surface") else []),
            *(["color: var(--ink);"] if has("ink") else []), *text]
    layers = []
    if has("overlay"):
        overlay = "color-mix(in srgb, var(--overlay) calc(var(--bg-overlay-opacity, 1) * 100%), transparent)"
        layers.append((f"linear-gradient({overlay}, {overlay})", "auto", "no-repeat", "0 0"))
    cell = "calc(16px * var(--bg-pattern-scale, 1))"
    layers += [(layer, f"{cell} {cell}", "repeat", "0 0") for layer in PATTERNS.get(plain.get("bg-pattern"), [])]
    if "bg-image" in plain:
        layers.append((f'url("{plain["bg-image"]}")', "var(--bg-size, cover)", "var(--bg-repeat, no-repeat)",
                       "var(--bg-position, center)"))
    if layers:
        body += [f"background-image: {', '.join(layer[0] for layer in layers)};",
                 f"background-size: {', '.join(layer[1] for layer in layers)};",
                 f"background-repeat: {', '.join(layer[2] for layer in layers)};",
                 f"background-position: {', '.join(layer[3] for layer in layers)};",
                 "background-attachment: var(--bg-attachment, scroll);"]
    out = _block("body", body)
    for level in range(1, 7):
        if f"h{level}" in styles:
            out += _block(f"h{level}", _style_lines(*styles[f"h{level}"]))
    out += _block("a", ["color: var(--link);"] if has("link") else [])
    out += _block("a:hover", ["color: var(--link-hover);"] if has("link-hover") else [])
    out += _block(":focus-visible", ["outline: 2px solid var(--focus);", "outline-offset: 2px;"] if has("focus") else [])
    out += _block(".ds-inverse", ["color: var(--ink-inverse);"] if has("ink-inverse") else [])
    out += _block("ul", ["list-style-type: var(--list-style);"] if has("list-style") else [])
    out += _block("ul, ol", ["padding-inline-start: var(--list-indent);"] if has("list-indent") else [])
    out += _block("li::marker", ["color: var(--list-marker);"] if has("list-marker") else [])
    container = [*(["max-width: var(--layout-content);"] if has("layout-content") else []),
                 *(["padding-inline: var(--layout-gutter);"] if has("layout-gutter") else [])]
    out += _block(".ds-container", ["box-sizing: border-box;", "margin-inline: auto;", *container] if container else [])
    out += _block(".ds-container--wide", ["max-width: var(--layout-wide);"] if has("layout-wide") else [])
    return out


def _layer(name, lines):
    return [f"@layer {name} {{", *(f"  {line}" for line in lines), "}"] if lines else []


def components_css(document):
    """Vrstvy `base`, `components` a `custom` nad proměnnými z `tokens.css`."""
    title = (document.get("title") or "Design system").replace("*/", "* /")
    settings = document["settings"]
    custom = [compile_button(variant, text, []) for variant, text in settings["customCss"]["button"].items()]
    out = [f"/* {title} — components.css, generated from design-system.json; load after tokens.css */",
           "@layer base, components, custom;"]
    out += _layer("base", _base(document["design"]["tokens"]))
    out += ["@layer components {", *button_css.css(settings["buttons"]), "}"]
    custom = [block for block in custom if block]
    if custom:
        out += ["@layer custom {", *custom, "}"]
    return "\n".join(out) + "\n"
