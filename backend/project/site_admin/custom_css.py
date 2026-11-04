"""Vlastní CSS tlačítek: parsování přes tinycss2, allowlist, přepis a zabalení (research §3, §7).

Uživatel píše CSS relativně ke kořeni tlačítka (`:scope`). Surový text se nikdy nevkládá: server ho rozparsuje,
každý uzel ověří a znovu sestaví.

- At-rules jen `@keyframes`, `@media`, `@supports`, `@container` (vnoření ≤ 3). Ostatní, `!important`,
  `expression(`, `behavior`, `-moz-binding`, `javascript:`/`vbscript:`, `<` (tedy `</style` a `<!--`), `\\`
  (escapes by obešly kontrolu), řídicí znaky, `position: fixed` a selektory `html`, `body`, `:root`, `:host`, `*`
  jsou chyba `CustomCssInvalid` (HTTP 422) s řádkem a důvodem.
- `url()` jen na `assets/<skupina>/<soubor>` projektu.
- Selektor dostane kořen `.ds-btn--<varianta>` (`:scope` se nahradí, jinak se předřadí), `@keyframes x` se
  přejmenuje na `ds-btn-<varianta>-x` i v `animation`/`animation-name`. Výsledek jde do `@layer custom` a dostane
  blok `prefers-reduced-motion: reduce`, který animace a přechody vypne (`!important` smí jen server).
- Limity: 16 KB na komponentu, 64 KB celkem, 200 deklarací, `animation-duration` ≥ 100 ms.
- Vypnutý focus ring bez náhrady je poznámka (`notes`), ne chyba.
"""

import re

import tinycss2
from tinycss2.ast import IdentToken

from backend.project.site_admin.tokens import ASSET, SiteAdminInvalid

MAX_COMPONENT, MAX_TOTAL, MAX_DECLARATIONS, MAX_DEPTH, MIN_DURATION_MS = 16_000, 64_000, 200, 3, 100
GROUPING = ("media", "supports", "container")
FORBIDDEN_TEXT = re.compile(r"[<\\\x00-\x08\x0b\x0e-\x1f\x7f]")
FORBIDDEN_VALUE = re.compile(r"expression\s*\(|javascript:|vbscript:", re.IGNORECASE)
FORBIDDEN_PROPERTY = re.compile(r"^(?:behavior|-moz-binding|binding|-o-link.*|-ms-behavior)$")
FORBIDDEN_SELECTOR = re.compile(r"(?:^|[\s>+~(,])(?:html|body)(?![\w-])|:root|:host|\*", re.IGNORECASE)
# Sourozenci (`~`, `+` na začátku nebo hned za `:scope`), `:has(` a `:scope` uprostřed by stylovaly okolí tlačítka.
OUTSIDE_SELECTOR = re.compile(r"^(?::scope\s*)?[~+]|:has\(|.:scope", re.IGNORECASE | re.DOTALL)
PRELUDE_TOKENS = {"ident", "hash", "literal", "string", "function", "number", "percentage", "dimension",
                  "whitespace", "[] block", "() block"}
FRAME = re.compile(r"^(?:from|to|\d{1,3}(?:\.\d+)?%)(?:\s*,\s*(?:from|to|\d{1,3}(?:\.\d+)?%))*$", re.IGNORECASE)


class CustomCssInvalid(SiteAdminInvalid):
    """Vlastní CSS neprošlo kontrolou; `detail` nese cestu, řádek a důvod pro odpověď 422."""

    def __init__(self, path, line, reason):
        super().__init__(f"{path}, řádek {line}: {reason}")
        self.detail = {"message": str(self), "path": path, "line": line, "reason": reason}


class _Component:
    def __init__(self, path, root, prefix):
        self.path, self.root, self.prefix = path, root, prefix
        self.declarations, self.keyframes = 0, set()

    def fail(self, node, reason):
        raise CustomCssInvalid(self.path, getattr(node, "source_line", 1) or 1, reason)


def _parse(text):
    return tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)


def _check_text(component, text):
    if len(text.encode("utf-8")) > MAX_COMPONENT:
        raise CustomCssInvalid(component.path, 1, f"CSS komponenty je delší než {MAX_COMPONENT // 1000} KB.")
    for number, line in enumerate(text.splitlines() or [""], start=1):
        found = FORBIDDEN_TEXT.search(line)
        if found:
            what = "znak <" if found[0] == "<" else "zpětné lomítko" if found[0] == "\\" else "řídicí znak"
            raise CustomCssInvalid(component.path, number, f"{what} není povolený.")


def _ms(token):
    unit = token.lower_unit if token.type == "dimension" else ""
    return token.value * 1000 if unit == "s" else token.value if unit == "ms" else None


def _check_value(component, declaration):
    tokens = list(_walk(declaration.value))
    for token in tokens:
        if token.type == "error":
            component.fail(declaration, f"Chyba syntaxe v hodnotě {declaration.name} ({token.message}).")
        if token.type == "url" and not ASSET.match(token.value):
            component.fail(declaration, f"url({token.value}) míří mimo assets/ projektu.")
        if token.type == "function" and token.lower_name in ("url", "src", "image-set", "image", "cross-fade"):
            strings = [arg.value for arg in token.arguments if arg.type == "string"]
            if not strings and token.lower_name in ("url", "src") or not all(map(ASSET.match, strings)):
                component.fail(declaration, f"{token.lower_name}() míří mimo assets/ projektu.")
    if FORBIDDEN_VALUE.search(tinycss2.serialize(declaration.value)):
        component.fail(declaration, f"Hodnota {declaration.name} obsahuje zakázaný výraz.")
    name = declaration.lower_name
    if name == "position" and any(t.type == "ident" and t.lower_value == "fixed" for t in tokens):
        component.fail(declaration, "position: fixed není povolené (překryje stránku).")
    if name in ("animation", "animation-duration"):
        for animation in _split_commas(declaration.value):
            times = [_ms(t) for t in animation if t.type == "dimension" and _ms(t) is not None]
            if times and times[0] < MIN_DURATION_MS:
                component.fail(declaration, f"animation-duration musí být aspoň {MIN_DURATION_MS} ms.")


def _walk(tokens):
    for token in tokens:
        yield token
        if token.type == "function":
            yield from _walk(token.arguments)
        elif token.type in ("() block", "[] block", "{} block"):
            yield from _walk(token.content)


def _broken(tokens):
    """Prelude s tokenem mimo allowlist: chyba parseru (`}`), `{`, `;`, at-keyword, `url()`…"""
    return any(t.type not in PRELUDE_TOKENS or t.type == "literal" and t.value in "{};" for t in _walk(tokens))


def _split_commas(tokens, keep_space=False):
    parts, current = [], []
    for token in tokens:
        if token.type == "literal" and token.value == ",":
            parts.append(current)
            current = []
        elif token.type != "comment" and (keep_space or token.type != "whitespace"):
            current.append(token)
    return [*parts, current]


def _rename(component, tokens):
    return [IdentToken(t.source_line, t.source_column, f"{component.prefix}-{t.value}")
            if t.type == "ident" and t.value in component.keyframes else t for t in tokens]


def _declarations(component, node, keyframe=False):
    """Tělo pravidla → (řádky deklarací, vypíná focus ring, má náhradu)."""
    lines, kills_ring, replaced = [], False, False
    for item in tinycss2.parse_blocks_contents(node.content, skip_comments=True, skip_whitespace=True):
        if item.type == "error":
            component.fail(item, f"Chyba syntaxe ({item.message}).")
        if item.type != "declaration":
            component.fail(item, "Vnořená pravidla nejsou povolená, napiš je jako samostatný selektor.")
        component.declarations += 1
        if component.declarations > MAX_DECLARATIONS:
            component.fail(item, f"Nejvýš {MAX_DECLARATIONS} deklarací.")
        if item.important:
            component.fail(item, "!important není povolené.")
        if item.lower_name.startswith("--") or FORBIDDEN_PROPERTY.match(item.lower_name):
            component.fail(item, f"Vlastnost {item.name} není povolená.")
        _check_value(component, item)
        value = item.value
        if item.lower_name in ("animation", "animation-name") and not keyframe:
            value = _rename(component, value)
        text = tinycss2.serialize(value).strip()
        if item.lower_name in ("outline", "outline-style", "outline-width") and re.fullmatch(r"none|0(?:px)?", text):
            kills_ring = True
        elif item.lower_name in ("outline", "outline-width", "box-shadow"):
            replaced = True
        lines.append(f"{item.lower_name}: {text};")
    return lines, kills_ring, replaced


def _selectors(component, node):
    if _broken(node.prelude):
        component.fail(node, "Neplatný selektor (obsahuje {, } nebo ;).")
    out = []
    for part in _split_commas(node.prelude, keep_space=True):
        selector = tinycss2.serialize(part).strip()
        if not selector:
            component.fail(node, "Prázdný selektor.")
        if FORBIDDEN_SELECTOR.search(selector):
            component.fail(node, f"Selektor {selector} míří mimo tlačítko (html, body, :root, :host, * nejsou povolené).")
        if OUTSIDE_SELECTOR.search(selector):
            component.fail(node, f"Selektor {selector} míří mimo tlačítko (:has(, ~ a + na začátku a :scope jinde "
                                 "než na začátku nejsou povolené).")
        out.append(selector.replace(":scope", component.root) if ":scope" in selector
                   else f"{component.root} {selector}")
    return out


def _rules(component, nodes, depth, notes, indent="  "):
    out = []
    for node in nodes:
        if node.type == "error":
            component.fail(node, f"Chyba syntaxe ({node.message}).")
        if node.type == "qualified-rule":
            selectors = _selectors(component, node)
            lines, kills_ring, replaced = _declarations(component, node)
            if kills_ring and not replaced and any("focus" in selector for selector in selectors):
                notes.append(f"{component.path}, řádek {node.source_line}: focus ring je vypnutý bez náhrady "
                             "(outline nebo box-shadow).")
            out += [f"{indent}{', '.join(selectors)} {{", *(f"{indent}  {line}" for line in lines), f"{indent}}}"]
            continue
        keyword = node.lower_at_keyword
        if keyword == "keyframes":
            name = [t for t in node.prelude if t.type not in ("whitespace", "comment")]
            if len(name) != 1 or name[0].type != "ident" or node.content is None:
                component.fail(node, "@keyframes potřebuje jedno jméno a tělo.")
            out.append(f"{indent}@keyframes {component.prefix}-{name[0].value} {{")
            for frame in _parse_content(component, node):
                step = tinycss2.serialize(frame.prelude).strip() if frame.type == "qualified-rule" else ""
                if not FRAME.match(step):
                    component.fail(frame, "V @keyframes jsou jen kroky (from, to, %).")
                lines, _, _ = _declarations(component, frame, keyframe=True)
                out += [f"{indent}  {step} {{",
                        *(f"{indent}    {line}" for line in lines), f"{indent}  }}"]
            out.append(f"{indent}}}")
        elif keyword in GROUPING:
            if depth >= MAX_DEPTH:
                component.fail(node, f"Vnoření nejvýš {MAX_DEPTH} úrovně.")
            prelude = tinycss2.serialize(node.prelude).strip()
            if node.content is None or _broken(node.prelude) or FORBIDDEN_VALUE.search(prelude) or "url(" in prelude.lower():
                component.fail(node, f"@{keyword} potřebuje podmínku a tělo.")
            inner = _rules(component, _parse_content(component, node), depth + 1, notes, indent + "  ")
            out += [f"{indent}@{keyword} {prelude} {{", *inner, f"{indent}}}"]
        else:
            component.fail(node, f"@{node.at_keyword} není povolené (jen @keyframes, @media, @supports, @container).")
    return out


def _parse_content(component, node):
    return tinycss2.parse_rule_list(node.content, skip_comments=True, skip_whitespace=True)


def compile_button(variant, text, notes, path=None):
    """CSS jedné varianty → sanitizovaný blok pro `@layer custom` (bez obalu vrstvy)."""
    component = _Component(path or f"customCss.button.{variant}", f".ds-btn--{variant}", f"ds-btn-{variant}")
    _check_text(component, text)
    nodes = _parse(text)
    component.keyframes = {t.value for node in nodes if node.type == "at-rule" and node.lower_at_keyword == "keyframes"
                           for t in node.prelude if t.type == "ident"}
    body = _rules(component, nodes, 1, notes)
    if not body:
        return ""
    root = component.root
    motion = ", ".join(f"{root}{part}" for part in ("", "::before", "::after", " *", " *::before", " *::after"))
    return "\n".join([f"  /* {root} */", *body, "  @media (prefers-reduced-motion: reduce) {", f"    {motion} {{",
                      "      animation-duration: 0.01ms !important;", "      animation-iteration-count: 1 !important;",
                      "      transition-duration: 0.01ms !important;", "    }", "  }"])


def normalize(raw, variants, notes):
    """`settings.customCss` → `{button: {varianta: css}}`; CSS se ověří (422) a uloží tak, jak ho člověk napsal."""
    raw = {} if raw is None else raw
    if not isinstance(raw, dict) or set(raw) - {"button"}:
        raise SiteAdminInvalid("settings.customCss je {button: {varianta: css}}.")
    buttons = raw.get("button", {})
    if not isinstance(buttons, dict):
        raise SiteAdminInvalid("settings.customCss.button musí být objekt {varianta: css}.")
    total, out = 0, {}
    for variant, text in buttons.items():
        if variant not in variants:
            raise SiteAdminInvalid(f"settings.customCss.button.{variant}: varianta tlačítka neexistuje.")
        if not isinstance(text, str):
            raise SiteAdminInvalid(f"settings.customCss.button.{variant} musí být text CSS.")
        total += len(text.encode("utf-8"))
        if total > MAX_TOTAL:
            raise CustomCssInvalid(f"settings.customCss.button.{variant}", 1,
                                   f"Vlastní CSS je dohromady delší než {MAX_TOTAL // 1000} KB.")
        compile_button(variant, text, notes, f"settings.customCss.button.{variant}")
        if text.strip():
            out[variant] = text
    return {"button": out}
