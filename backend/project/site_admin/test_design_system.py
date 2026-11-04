import pytest

from backend.project.site_admin.design_system import SiteAdminInvalid, empty, normalize
from backend.project.site_admin.fixture import ember


def tokens_of(raw):
    document, notes = normalize({"design": {"tokens": raw}})
    return document["design"]["tokens"], notes


def colors(*tokens, themes=("light", "dark")):
    return {"color": {"themes": [{"id": theme} for theme in themes], "tokens": list(tokens)}}


def test_empty_document_has_one_theme_and_every_settings_part():
    document = empty()
    assert document["revision"] == 0 and document["lastChange"] is None
    assert set(document["settings"]) == {"seo", "affiliate", "email", "header", "footer", "gdpr", "appearance",
                                         "buttons", "customCss"}
    assert document["settings"]["appearance"]["colors"]["link"] is None
    assert document["settings"]["buttons"]["variants"] == {} and document["settings"]["customCss"] == {"button": {}}
    assert document["design"]["tokens"]["color"] == {"themes": [{"id": "light", "name": "Light"}], "tokens": []}


def test_sample_passes_without_notes_and_keeps_its_shape():
    document, notes = normalize(ember())
    assert notes == []
    color = document["design"]["tokens"]["color"]
    assert color["tokens"][0]["value"] == {"light": "#fff8f0", "dark": "#1c1714"}  # hex malými
    assert color["tokens"][3] == {"name": "link", "value": "{ember}"}
    assert document["design"]["tokens"]["spacing"]["tokens"][0]["value"] == "4px"  # číslo = px
    assert document["settings"]["email"]["secretRef"] == "env:SMTP_PASSWORD"


def test_button_component_is_generated_from_buttons_and_cannot_be_edited():
    raw = ember()
    raw["design"]["components"].append({"name": "Button", "preview": "<b>ručně</b>", "readme": "ručně"})
    document, _ = normalize(raw)
    button, card = document["design"]["components"]
    assert button["name"] == "Button" and button["group"] == "Actions" and "ručně" not in button["readme"]
    assert '<button class="ds-btn ds-btn--primary" type="button">Objednat</button>' in button["preview"]
    assert 'aria-disabled="true" class="ds-btn ds-btn--primary"' in button["preview"]
    assert "ds-btn--primary ds-btn--sm" in button["preview"] and card["name"] == "Card"
    assert normalize(document)[0]["design"]["components"] == document["design"]["components"]
    without = normalize({"design": {"components": [{"name": "Button"}]}})[0]
    assert without["design"]["components"] == []  # bez variant tlačítek není ani komponenta


def test_component_name_grammar_and_readme_limit():
    document, _ = normalize({"design": {"components": [{"name": "card.small-2", "readme": "x" * 150_000}]}})
    assert document["design"]["components"][0]["name"] == "card.small-2"


@pytest.mark.parametrize("preview", ["<script>alert(1)</script>", '<img src="x" onerror="alert(1)">',
                                     '<a href="javascript:alert(1)">x</a>', "<iframe src=x>", "<b>&#106;</b>",
                                     "<svg><foreignObject/></svg>", '<div\nONclick = "x">'])
def test_component_preview_rejects_scripts_like_svg(preview):
    with pytest.raises(SiteAdminInvalid, match="Náhled komponenty Card"):
        normalize({"design": {"components": [{"name": "Card", "preview": preview}]}})


def test_bad_color_values_drop_with_a_note_and_missing_theme_inherits_the_first():
    tokens, notes = tokens_of(colors(
        {"name": "named", "value": "red"},
        {"name": "variable", "value": "var(--x)"},
        {"name": "mix", "value": "color-mix(in srgb, red, blue)"},
        {"name": "half", "value": {"light": "#000", "dark": "url(x)"}},
        {"name": "later", "value": {"dark": "oklch(0.5 0.1 200)"}},
        {"name": "p3", "value": "color(display-p3 1 0.5 0)"},
    ))
    names = [token["name"] for token in tokens["color"]["tokens"]]
    assert names == ["half", "later", "p3"]
    assert tokens["color"]["tokens"][0]["value"] == "#000"  # dark zahozen → dědí z prvního tématu
    assert tokens["color"]["tokens"][1]["value"] == {"light": "oklch(0.5 0.1 200)", "dark": "oklch(0.5 0.1 200)"}
    assert any("named" in note for note in notes) and any("half [dark]" in note for note in notes)


def test_aliases_drop_on_missing_target_self_cycle_and_depth():
    chain = [{"name": f"c{i}", "value": f"{{c{i + 1}}}"} for i in range(17)] + [{"name": "c17", "value": "#111"}]
    tokens, notes = tokens_of(colors(
        {"name": "base", "value": "#123456"},
        {"name": "ok", "value": "{base}"},
        {"name": "ghost", "value": "{nobody}"},
        {"name": "me", "value": "{me}"},
        {"name": "a", "value": "{b}"}, {"name": "b", "value": "{a}"},
        {"name": "themed", "value": {"light": "#fff", "dark": "{ghost}"}},
        *chain,
    ))
    names = {token["name"] for token in tokens["color"]["tokens"]}
    assert {"base", "ok", "themed", "c17", "c1", "c16"} <= names
    assert not names & {"ghost", "me", "a", "b", "c0"}  # c0 → c17 je 17 skoků
    assert next(t for t in tokens["color"]["tokens"] if t["name"] == "themed")["value"] == "#fff"
    assert any("alias" in note for note in notes)


def test_shared_namespace_name_rules_and_lengths():
    tokens, notes = tokens_of({
        **colors({"name": "--brand", "value": "#000"}),
        "spacing": {"tokens": [{"name": "brand", "value": 4}, {"name": ".space-2", "value": "0.5rem"},
                               {"name": "bad name", "value": 4}, {"name": "space-x", "value": "4vw"}]},
        "radius": {"tokens": [{"name": "space-2", "value": "2px"}]},
    })
    assert tokens["color"]["tokens"][0]["name"] == "brand"
    assert tokens["spacing"]["tokens"] == [{"name": "space-2", "value": "0.5rem"}]
    assert tokens["radius"]["tokens"] == []
    assert len(notes) == 4


def test_shadow_and_custom_family_values():
    tokens, notes = tokens_of({
        **colors({"name": "ink", "value": "#000"}),
        "shadow": {"tokens": [{"name": "ok", "value": "inset 0 0 0 1px #00000014, 0 2px 4px hsl(0 0% 0% / 0.2)"},
                              {"name": "var", "value": "0 0 2px var(--ink)"},
                              {"name": "per", "value": {"light": "none", "dark": "0 0 0 2px #fff"}}]},
        "zIndex": {"note": "x" * 500, "tokens": [{"name": "z-modal", "value": 100}, {"name": "z-bad", "value": "url(a)"}]},
    })
    assert [token["name"] for token in tokens["shadow"]["tokens"]] == ["ok", "per"]
    assert tokens["shadow"]["tokens"][1]["value"] == {"light": "none", "dark": "0 0 0 2px #fff"}
    assert tokens["zIndex"]["tokens"] == [{"name": "z-modal", "value": "100"}]
    assert len(tokens["zIndex"]["note"]) == 400
    assert any("zkráceno" in note for note in notes)


def test_typography_rules():
    tokens, notes = tokens_of({"type": {
        "families": {"Sans": "Inter, sans-serif", "evil": "x; } body { color: red", "q": '"Open Sans'},
        "fonts": [{"family": "Inter", "file": "inter.woff2", "weight": "300 800"},
                  {"family": "Bad", "file": "../x.woff2"}, {"family": "Heavy", "file": "h.ttf", "weight": 1200}],
        "groups": [{"name": "Text", "family": "sans", "styles": [
            {"name": "body", "fontSize": "1rem", "lineHeight": 12, "fontWeight": "bold", "fontStyle": "oblique",
             "opticalSize": 14},
            {"name": "huge", "fontSize": "big"},
            {"name": "body", "fontSize": 12},
            {"name": "range", "fontSize": 20, "fontWeight": "300 800", "lineHeight": "1.2", "family": "nope"},
        ]}],
    }})
    assert tokens["type"]["families"] == {"sans": "Inter, sans-serif"}
    assert tokens["type"]["fonts"] == [{"family": "Inter", "file": "fonts/inter.woff2", "weight": "300 800", "style": "normal"}]
    styles = tokens["type"]["groups"][0]["styles"]
    assert styles[0] == {"name": "body", "fontSize": "1rem", "lineHeight": "12px", "fontWeight": 700, "opticalSize": 14}
    assert styles[1] == {"name": "range", "fontSize": "20px", "fontWeight": "300 800", "lineHeight": 1.2}
    assert len(styles) == 2 and len(notes) >= 7


@pytest.mark.parametrize("raw, message", [
    ({"design": {"tokens": {"color": {"themes": [{"id": f"t{i}"} for i in range(9)]}}}}, "8 témat"),
    ({"design": {"tokens": {"spacing": {"tokens": [{"name": f"s{i}", "value": 1} for i in range(61)]}}}}, "60"),
    ({"design": {"tokens": {"spacing": {"space-1": "4px"}}}}, "neznámé pole space-1"),
    ({"design": {"tokens": {"spacing": {"tokens": {"space-1": "4px"}}}}}, "tokens.spacing.tokens"),
    ({"design": {"tokens": {"color": []}}}, "tokens.color"),
    ({"design": {"readme": "x" * 200_001}}, "design.readme"),
    ({"design": {"unknown": 1}}, "neznámé pole"),
    ({"settings": {"seo": {"titleTemplate": 1}}}, "settings.seo.titleTemplate"),
    ({"settings": {"web": {}}}, "neznámá část"),
    ({"settings": {"email": {"password": "hunter2"}}}, "tajemství"),
    ({"settings": {"email": {"smtpToken": "x"}}}, "tajemství"),
    ({"settings": {"email": {"secretRef": "hunter2"}}}, "secretRef"),
    ({"settings": {"gdpr": {"cookieBar": {"categories": ["tracking"]}}}}, "categories"),
    ({"design": {"components": [{"name": "-card"}]}}, "Komponenta '-card'"),
    ({"design": {"components": [{"name": "Card", "readme": "x" * 200_001}]}}, "README komponenty Card"),
    ({"design": {"assetGroups": [{"name": "Logos", "files": [{"name": "a.svg", "blob": "../a.svg"}]}]}}, "blob"),
    ({"v": 2}, "v musí být 1"),
    ({"settings": {"appearance": {"colors": {"brand": "#000"}}}}, "neznámé pole colors.brand"),
    ({"settings": {"buttons": {"variants": {"Primary": {}}}}}, "jméno varianty"),
    ({"settings": {"customCss": {"button": {"ghost": ":scope { color: red }"}}}}, "varianta tlačítka neexistuje"),
])
def test_shape_errors_are_422_with_a_message(raw, message):
    with pytest.raises(SiteAdminInvalid, match=message):
        normalize(raw)


def test_normalized_document_is_stable():
    document, _ = normalize(ember())
    assert normalize(document) == (document, [])
