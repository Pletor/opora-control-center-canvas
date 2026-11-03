"""Odvozené soubory design systému: `tokens.css`, `tokens.json` a `README.md` (kontrakt §2).

Generuje je jen server z normalizovaného dokumentu (`design_system.normalize`), ručně se nepíšou. Rozvržení
`tokens.css` je podle formátu Design System:

1. `/* <titulek> — generated from tokens.json */`
2. `:root, [data-theme="<první>"] { barvy; stíny }`
3. `[data-theme="<id>"] { … }` pro každé další téma: hodnoty, které se liší od prvního tématu, a znovu všechny aliasy
   (vlastní vlastnost s `var()` se počítá na prvku, kde je deklarovaná)
4. `:root { --space-*; --radius-*; vlastní rodiny; --font-<klíč> }`
5. třída `.<styl>` na každý typografický styl, `@font-face` na každý font (`url("fonts/<soubor>")` vedle `tokens.css`)
"""

import json
import re

from backend.project.site_admin.tokens import ALIAS, FIXED

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
            family = style.get("family") or group.get("family")
            lines = [f"font-family: var(--font-{_ident(family)});"] if family else []
            lines += [f"{css}: {style[key]};" for key, css in STYLE_CSS if key in style]
            if "opticalSize" in style:
                lines.append(f"font-variation-settings: 'opsz' {style['opticalSize']:g};")
            out += _block(f".{_ident(style['name'])}", lines)
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
            "- Zdroj pravdy je dokument Správy webu v OPOŘE. `tokens.css`, `tokens.json` a tento README generuje server."]
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
    if design["assetGroups"]:
        out += ["", "### Assety", "", "Assety kopíruj, nikdy je nekresli znovu.", ""]
        for group in design["assetGroups"]:
            files = ", ".join(f"`{file['blob']}`" for file in group["files"]) or "zatím prázdná"
            out.append(f"- {group['name']}: {files}")
    return "\n\n".join(out[:out.index("---")]) + "\n\n" + "\n".join(out[out.index("---"):]) + "\n"
