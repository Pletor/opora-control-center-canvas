import pytest

from backend.project.site_admin.buttons import contrast, css, normalize
from backend.project.site_admin.tokens import SiteAdminInvalid, normalize_tokens

TOKENS = normalize_tokens({
    "color": {"tokens": [{"name": "surface", "value": "#ffffff"}, {"name": "primary", "value": "#0066cc"},
                         {"name": "focus", "value": "#0066cc"}]},
    "type": {"families": {"sans": "Inter, sans-serif"}},
    "radius": {"tokens": [{"name": "radius-md", "value": "8px"}]},
}, [])


def buttons(variants, sizes=None):
    notes = []
    raw = {"variants": variants, **({"sizes": sizes} if sizes else {})}
    return normalize(raw, TOKENS, notes), notes


def test_states_keep_only_the_difference_from_default():
    out, notes = buttons({"primary": {"states": {
        "default": {"background": "{primary}", "color": "#ffffff", "radius": "{radius-md}",
                    "border": {"width": "0", "style": "solid"}, "font": {"family": "sans", "weight": 600}},
        "hover": {"background": {"gradient": {"angle": 135, "stops": [{"color": "#004488", "position": 0},
                                                                     {"color": "#003377", "position": 1}]}},
                  "color": "#ffffff", "border": {"width": "0", "style": "dashed"}},
        "active": {"color": "#ffffff"},
        "focusVisible": {"outline": {"width": "3px", "color": "{focus}", "offset": "2px"}},
        "disabled": {"background": "#ccd1d9", "color": "#5b6470"},
    }}})
    states = out["variants"]["primary"]["states"]
    assert states["hover"] == {"background": {"gradient": {"angle": 135, "stops": [
        {"color": "#004488", "position": 0}, {"color": "#003377", "position": 1}]}}, "border": {"style": "dashed"}}
    assert "active" not in states and out["variants"]["primary"]["preset"] == "solid"
    assert out["sizes"]["md"] == {"paddingX": "1.5rem", "paddingY": "0.625rem", "minHeight": "44px", "fontSize": "1rem"}
    assert notes == []


def test_bad_values_and_missing_tokens_drop_with_a_note():
    out, notes = buttons({"ghost": {"preset": "ghost", "states": {"default": {
        "background": "{nobody}", "color": "red", "radius": "pill", "width": "full", "shadow": "0 0 2px var(--x)",
        "transition": {"properties": ["background-color", "left"], "duration": "150ms", "easing": "ease-out"}}}}},
        sizes={"sm": {"minHeight": "20px", "paddingX": "1vw"}})
    default = out["variants"]["ghost"]["states"]["default"]
    assert default == {"radius": "pill", "width": "full", "transition": {"duration": "150ms", "easing": "ease-out"}}
    assert out["sizes"]["sm"]["minHeight"] == "20px" and out["sizes"]["sm"]["paddingX"] == "0.875rem"
    assert sum("neplatná hodnota" in note for note in notes) == 5
    assert any("minHeight 20px je pod 24 px" in note for note in notes)


@pytest.mark.parametrize("variants, message", [
    ({"sm": {}}, "jméno varianty"),
    ({"Primary": {}}, "jméno varianty"),
    ({"primary": {"preset": "neon"}}, "preset"),
    ({"primary": {"states": {"pressed": {}}}}, "neznámé pole pressed"),
    ({"primary": {"states": {"hover": {"outline": {"width": "2px"}}}}}, "neznámé pole outline"),
    ({"primary": {"states": {"default": {"padding": "1px"}}}}, "neznámé pole padding"),
    ({"primary": {"states": {"default": {"border": {"radius": "1px"}}}}}, "neznámé pole radius"),
])
def test_shape_errors(variants, message):
    with pytest.raises(SiteAdminInvalid, match=message):
        buttons(variants)


def test_accessibility_notes():
    _, notes = buttons({
        "pale": {"states": {"default": {"background": "#ffffff", "color": "#999999"},
                            "hover": {"background": "#eeeeee"}, "disabled": {"color": "#eeeeee"}}},
        "outline": {"preset": "outline", "states": {
            "default": {"background": "transparent", "color": "{primary}",
                        "border": {"width": "2px", "color": "#dddddd"}},
            "focusVisible": {"outline": {"style": "none"}}}},
        "gradient": {"states": {"default": {"color": "#ffffff", "background": {"gradient": {"stops": [
            {"color": "#0066cc", "position": 0}, {"color": "#99ccff", "position": 1}]}}}}},
    })
    assert any(note.startswith("Tlačítko pale (default): kontrast textu 2.85:1") for note in notes)
    assert any(note.startswith("Tlačítko pale (hover)") for note in notes)
    assert not any("pale (disabled)" in note for note in notes)  # neaktivní prvek je z kontrastu výjimka
    assert any("outline (default): rámeček" in note for note in notes)
    assert "Tlačítko outline: focus ring je vypnutý bez náhrady (stín nebo outline)." in notes
    assert sum("gradient" in note and "kontrast" in note for note in notes) == 1  # jen světlý konec


def test_contrast_matches_wcag():
    assert round(contrast((0, 0, 0), (255, 255, 255)), 2) == 21
    assert round(contrast((0, 102, 204), (255, 255, 255)), 2) == 5.57


def test_css_uses_only_component_tokens():
    out, _ = buttons({"primary": {"states": {
        "default": {"background": "{primary}", "color": "#ffffff", "radius": "md", "width": "full",
                    "font": {"family": "sans", "transform": "uppercase"}, "transition": {"duration": "200ms"}},
        "hover": {"shadow": "0 4px 12px rgb(0 0 0 / 0.12)"},
        "disabled": {"background": "#cccccc"}}}})
    text = "\n".join(css(out))
    assert ".ds-btn {\n    --btn-bg: transparent;" in text and "background: var(--btn-bg);" in text
    assert ".ds-btn--sm {\n    --btn-px: 0.875rem;" in text
    assert (".ds-btn--primary {\n    --btn-bg: var(--primary);\n    --btn-color: #ffffff;\n    --btn-radius: 8px;\n"
            "    --btn-width: 100%;\n    --btn-font-family: var(--font-sans);\n    --btn-text-transform: uppercase;\n"
            "    --btn-transition: background-color 200ms ease, color 200ms ease, border-color 200ms ease, "
            "box-shadow 200ms ease;") in text
    assert '.ds-btn--primary:hover:not(:disabled):not([aria-disabled="true"]) {' in text
    assert '.ds-btn--primary:disabled, .ds-btn--primary[aria-disabled="true"] {\n    --btn-bg: #cccccc;' in text
    assert ".ds-btn:focus-visible {\n    outline: var(--btn-ring-width) var(--btn-ring-style) var(--btn-ring-color);" in text
