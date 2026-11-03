from backend.project.site_admin.appearance import FIELDS, view
from backend.project.site_admin.design_system import normalize
from backend.project.site_admin.fixture import ember

APPEARANCE = {
    "background": {"color": "#ffffff", "image": {"asset": "assets/Bg/paper.png", "size": "cover", "repeat": "no-repeat"},
                   "pattern": {"preset": "dots", "color": "#e5e7eb", "scale": 2}, "overlay": {"color": "#000000", "opacity": 0.2}},
    "text": {"heading": {"font": "Inter, system-ui, sans-serif"}, "subheading": {"font": "Inter, sans-serif", "size": "1.25rem"},
             "body": {"font": "Georgia, serif", "size": "1.0625rem"}},
    "colors": {"text": "#12171f", "textInverse": "#ffffff", "link": "{ember}", "linkHover": "#004488", "focus": "#0066cc"},
    "headings": {"h1": {"size": "2.5rem", "weight": 700, "lineHeight": 1.15, "letterSpacing": "-0.01em"},
                 "h6": {"size": "1rem"}},
    "lists": {"marker": "square", "color": "{ember}", "indent": "1.25em"},
    "layout": {"contentSize": "1140px", "wideSize": "1440px", "gutter": "1.25rem"},
}


def saved(appearance, document=None, base=None):
    document = document or ember()
    document["settings"]["appearance"] = appearance
    return normalize(document, base)


def color(document, name):
    return next((t["value"] for t in document["design"]["tokens"]["color"]["tokens"] if t["name"] == name), None)


def test_every_field_lands_in_a_token_and_the_view_reads_it_back():
    document, notes = saved(APPEARANCE)
    assert notes == []
    tokens = document["design"]["tokens"]
    assert color(document, "ink") == {"light": "#12171f", "dark": "#f4ebe3"}  # první téma, ostatní zůstanou
    assert color(document, "link") == "{ember}" and color(document, "link-hover") == "#004488"
    assert tokens["type"]["families"]["heading"] == "Inter, system-ui, sans-serif"
    headings = next(g for g in tokens["type"]["groups"] if g["name"] == "Nadpisy")
    assert headings["styles"][0] == {"name": "h1", "fontSize": "2.5rem", "lineHeight": 1.15, "fontWeight": 700,
                                     "letterSpacing": "-0.01em", "family": "heading"}
    body = next(s for g in tokens["type"]["groups"] for s in g["styles"] if s["name"] == "body")
    assert body["fontSize"] == "1.0625rem" and body["lineHeight"] == 1.45  # existující styl se jen upraví
    assert {t["name"]: t["value"] for t in tokens["layout"]["tokens"]} == {
        "layout-content": "1140px", "layout-wide": "1440px", "layout-gutter": "1.25rem"}
    assert {t["name"] for t in tokens["background"]["tokens"]} >= {"bg-image", "bg-pattern", "bg-overlay-opacity"}
    appearance = document["settings"]["appearance"]
    assert appearance["background"]["pattern"]["scale"] == 2 and appearance["background"]["image"]["position"] is None
    assert appearance["headings"]["h1"]["weight"] == 700 and appearance["text"]["body"]["size"] == "1.0625rem"
    assert appearance == view(tokens) and len(FIELDS) == 51


def test_missing_field_is_unchanged_null_deletes_and_bad_value_is_a_note():
    document, _ = saved(APPEARANCE)
    document["settings"]["appearance"] = {"colors": {"linkHover": None, "focus": "blue"},
                                          "headings": {"h6": {"size": None}}, "layout": {"gutter": "1vw"}}
    again, notes = normalize(document)
    assert color(again, "link-hover") is None and color(again, "focus") == "#0066cc"
    assert color(again, "ink") == {"light": "#12171f", "dark": "#f4ebe3"}
    assert all(s["name"] != "h6" for g in again["design"]["tokens"]["type"]["groups"] for s in g["styles"])
    assert len(notes) == 2 and "colors.focus" in notes[0] and "layout.gutter" in notes[1]


def test_stale_view_does_not_overwrite_a_token_edited_in_colors():
    stored, _ = saved(APPEARANCE)
    edited = {**stored, "design": {**stored["design"]}}
    edited["design"]["tokens"] = {**stored["design"]["tokens"], "color": {
        **stored["design"]["tokens"]["color"],
        "tokens": [t if t["name"] != "link-hover" else {**t, "value": "#112233"}
                   for t in stored["design"]["tokens"]["color"]["tokens"]]}}
    document, _ = normalize(edited, stored)  # appearance v těle je pořád stará
    assert color(document, "link-hover") == "#112233"
    assert document["settings"]["appearance"]["colors"]["linkHover"] == "#112233"
    edited["settings"] = {**edited["settings"], "appearance": {"colors": {"linkHover": "#445566"}}}
    both, _ = normalize(edited, stored)  # změna v obou editorech: vyhraje Vzhled
    assert color(both, "link-hover") == "#445566"
