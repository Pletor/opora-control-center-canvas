import json

from backend.project.site_admin.compile import readme, tokens_css, tokens_json
from backend.project.site_admin.design_system import empty, normalize
from backend.project.site_admin.fixture import ember


def sample():
    document, _ = normalize(ember())
    return document


def test_tokens_css_follows_the_format_layout():
    css = tokens_css(sample())
    blocks = [line for line in css.splitlines() if line.endswith("{")]
    assert css.splitlines()[0] == "/* Ember — generated from tokens.json */"
    assert blocks == [':root, [data-theme="light"] {', '[data-theme="dark"] {', ":root {", ".display {", ".body {",
                      ".code {", "@font-face {"]
    first, dark = css.split('[data-theme="dark"] {')
    assert "--ember: rgb(214 88 42);" in first and "--link: var(--ember);" in first
    assert "--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.08);" in first
    dark = dark.split("}")[0]
    assert "--surface: #1c1714;" in dark and "--shadow-sm: none;" in dark
    assert "--ember:" not in dark  # stejná hodnota jako v prvním tématu se neopakuje
    assert "--link: var(--ember);" in dark  # alias se v tématu deklaruje znovu
    assert "--space-1\\.5: 6px;" in css and "--control: 40px;" in css and "--font-sans: Inter, system-ui, sans-serif;" in css
    assert ".display {\n  font-family: var(--font-sans);\n  font-size: 32px;\n  line-height: 40px;" in css
    assert 'src: url("fonts/inter.woff2") format("woff2");\n  font-weight: 300 800;' in css


def test_empty_system_and_title_cannot_close_the_comment():
    document = {**empty(), "title": "a */ body{} /*"}
    css = tokens_css(document)
    assert css == "/* a * / body{} /* — generated from tokens.json */\n"


def test_tokens_json_is_the_format_grammar():
    data = json.loads(tokens_json(sample()))
    assert data["version"] == 1 and data["color"]["themes"][1]["id"] == "dark"
    assert data["type"]["fonts"][0]["file"] == "fonts/inter.woff2" and "size" in data


def test_readme_carries_brand_book_and_generated_usage():
    text = readme(sample())
    book, generated = text.split("\n---\n")
    assert book.startswith("# Ember\n\nKrátké věty")
    assert "## Jak systém použít" in generated and "`light`, `dark`" in generated
    assert "- **Button** (Actions): Jedna primární akce na pohled." in generated
    assert "- Logos: `assets/Logos/mark.svg`" in generated
    assert "`.display`, `.body`, `.code`" in generated and "fonts/inter.woff2" in generated
