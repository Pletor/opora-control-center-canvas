"""Komponenta `Button` design systému jako pohled na Tlačítka webu (`settings.buttons`, kontrakt §0 M1 bod 3).

Ručně se needituje: server ji skládá při každém uložení z variant tlačítek (`design_system._components`), takže
náhled, README i seznam komponent v `README.md` vždy sedí s `components.css`. Bez variant komponenta není.
"""

from html import escape

NAME, GROUP = "Button", "Actions"


def _tag(name, variant, extra=""):
    label = escape(variant.get("label") or name.capitalize(), quote=False)
    classes = f"ds-btn ds-btn--{name}{extra}"
    if variant["preset"] == "link":
        return f'<a class="{classes}" href="#">{label}</a>'
    return f'<button class="{classes}" type="button">{label}</button>'


def _row(tags):
    return '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px">' + "".join(tags) + "</div>"


def component(buttons):
    """`settings.buttons` (normalizované) → záznam `design.components[]`, nebo None bez variant."""
    variants = buttons["variants"]
    if not variants:
        return None
    first = next(iter(variants))
    rows = [_row(_tag(name, variant) for name, variant in variants.items()),
            _row(_tag(first, variants[first], f" ds-btn--{size}") for size in ("sm", "md", "lg")),
            _row(_tag(name, variant).replace(' class="', ' aria-disabled="true" class="', 1)
                 for name, variant in variants.items())]
    listed = "\n".join(f"- `ds-btn--{name}` ({variant['preset']}): {variant.get('label') or name.capitalize()}"
                       for name, variant in variants.items())
    readme = (f"# Button\n\nTlačítko webu pro jednu akci (odeslat, objednat, přejít dál).\n\n## Varianty\n\n{listed}\n\n"
              "## Jak použít\n\n`<button class=\"ds-btn ds-btn--<varianta>\" type=\"button\">…</button>`, velikost "
              "`ds-btn--sm|md|lg` (výchozí md), nedostupné `disabled` nebo `aria-disabled=\"true\"`. Odkaz, který "
              "vede jinam, je `<a class=\"ds-btn ds-btn--…\">`.\n\n## Kdy ne\n\nOdkaz v běžném textu je `a` bez "
              "`ds-btn`. Vlastní barvy a stavy se nepíšou, řeší je `components.css`.\n\n"
              "Komponentu skládá server z části Tlačítka webu; měň ji tam.")
    return {"name": NAME, "height": 240, "group": GROUP,
            "summary": "Tlačítko webu ve variantách " + ", ".join(variants) + ".",
            "readme": readme, "preview": '<div style="display:grid;gap:16px;padding:16px">' + "".join(rows) + "</div>"}
