import pytest

from backend.project.site_admin.custom_css import CustomCssInvalid, compile_button, normalize

SHINE = (":scope { position: relative; overflow: hidden; }\n"
         ":scope::after { content: \"\"; background: url(\"assets/Bg/shine.png\"); }\n"
         ":scope:hover::after { animation: shine .8s ease-out; }\n"
         "@keyframes shine { from { opacity: 0 } to { transform: translateX(100%); } }\n"
         "@media (hover: hover) { span { color: currentColor } }\n"
         "@supports (display: grid) { @container (min-width: 10em) { :scope i { gap: 1px } } }")


def test_rules_are_scoped_renamed_and_get_reduced_motion():
    css = compile_button("primary", SHINE, [])
    assert "  .ds-btn--primary {\n    position: relative;" in css
    assert ".ds-btn--primary:hover::after {\n    animation: ds-btn-primary-shine .8s ease-out;" in css
    assert "@keyframes ds-btn-primary-shine {" in css and "@keyframes shine" not in css
    assert "@media (hover: hover) {\n    .ds-btn--primary span {" in css
    assert "@container (min-width: 10em) {\n      .ds-btn--primary i {" in css
    assert 'url("assets/Bg/shine.png")' in css
    motion = css.split("@media (prefers-reduced-motion: reduce)")[1]
    assert ".ds-btn--primary *::after" in motion and "animation-duration: 0.01ms !important;" in motion


def test_empty_css_compiles_to_nothing():
    assert compile_button("primary", "  ", []) == ""


@pytest.mark.parametrize("css, line, reason", [
    ("a { color: red }\n@import url(x.css);", 2, "@import není povolené"),
    ("@font-face { font-family: x }", 1, "@font-face"),
    ("@layer x { a { color: red } }", 1, "@layer"),
    ("a { color: red !important }", 1, "!important"),
    ("a {\n  width: expression(alert(1));\n}", 2, "zakázaný výraz"),
    ("a { behavior: url(x.htc) }", 1, "behavior"),
    ("a { -moz-binding: url(x.xml) }", 1, "-moz-binding"),
    ("a { background: url(javascript:alert) }", 1, "mimo assets"),
    ("a { background: url(javascript:alert(1)) }", 1, "Chyba syntaxe"),
    ("a { background: url('https://evil.example/x.png') }", 1, "mimo assets"),
    ("a { background: url(assets/../secret) }", 1, "mimo assets"),
    ("a { background: image-set(\"https://x/y.png\" 1x) }", 1, "image-set"),
    ("a { content: 'x' }\n</style><script>", 2, "znak <"),
    ("<!-- a {} -->", 1, "znak <"),
    ("a { content: '\\6a avascript:' }", 1, "zpětné lomítko"),
    ("html a { color: red }", 1, "míří mimo tlačítko"),
    ("body { color: red }", 1, "míří mimo tlačítko"),
    (":root { --x: 1 }", 1, "míří mimo tlačítko"),
    ("* { color: red }", 1, "míří mimo tlačítko"),
    (":scope > * { color: red }", 1, "míří mimo tlačítko"),
    (".a } } .b { color: red }", 1, "Neplatný selektor"),
    ("a { position: fixed; inset: 0 }", 1, "position: fixed"),
    ("a { animation: x 50ms }", 1, "100 ms"),
    ("a { animation-duration: 0.05s }", 1, "100 ms"),
    ("a { b { color: red } }", 1, "Vnořená pravidla"),
    ("a { --x: red }", 1, "Vlastnost --x"),
    ("@keyframes k { 50%, nope { opacity: 1 } }", 1, "kroky"),
    ("@media a { @media b { @media c { a { color: red } } } }", 1, "Vnoření"),
])
def test_forbidden_input_reports_line_and_reason(css, line, reason):
    with pytest.raises(CustomCssInvalid) as error:
        compile_button("primary", css, [])
    assert error.value.detail["line"] == line and reason in error.value.detail["reason"]
    assert error.value.detail["path"] == "customCss.button.primary"


def test_allowed_delay_and_disabled_focus_ring_is_a_note():
    notes = []
    css = compile_button("primary", ":scope { animation: x 200ms 0s }\n:scope:focus-visible { outline: none }", notes)
    assert "animation: x 200ms 0s;" in css
    assert notes == ["customCss.button.primary, řádek 2: focus ring je vypnutý bez náhrady (outline nebo box-shadow)."]
    replaced = []
    compile_button("primary", ":scope:focus-visible { outline: none; box-shadow: 0 0 0 3px #000 }", replaced)
    assert replaced == []


def test_limits():
    with pytest.raises(CustomCssInvalid, match="16 KB"):
        compile_button("primary", "a { color: red }" * 1100, [])
    with pytest.raises(CustomCssInvalid, match="200 deklarací"):
        compile_button("primary", "a { color: red }\n" * 201, [])
    big = {f"v{i}": "/*" + "x" * 15_000 + "*/" for i in range(5)}
    with pytest.raises(CustomCssInvalid, match="64 KB"):
        normalize({"button": big}, set(big), [])


def test_normalize_keeps_source_and_checks_variants():
    assert normalize({"button": {"primary": ":scope { color: red }", "ghost": " "}}, {"primary", "ghost"}, []) == {
        "button": {"primary": ":scope { color: red }"}}
    with pytest.raises(CustomCssInvalid) as error:
        normalize({"button": {"primary": "a {}\n@import x;"}}, {"primary"}, [])
    assert error.value.detail["path"] == "settings.customCss.button.primary" and error.value.detail["line"] == 2
