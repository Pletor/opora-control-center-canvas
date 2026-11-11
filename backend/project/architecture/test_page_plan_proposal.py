import json

from backend.project.architecture.page_plan_proposal import FLOW_KEYS, prompt_for, proposal_of
from backend.project.architecture.test_page_plan_scan import GOOD

FLOW = {"inputs": ["e-mail"], "steps": ["odeslání formuláře"], "dataTo": ["platební brána"]}
DESIGN = {"color": {"tokens": [{"name": "surface", "value": "#FFFFFF"}, {"name": "ink", "value": "red"}]},
          "type": {"families": {"body": "Inter, sans-serif"}}, "button": {"tokens": [{"name": "button-radius", "value": "8px"}]}}


def found(**changes):
    value = json.loads(json.dumps(GOOD))
    value["sections"][1].update(intent="i" * 700, look="Tmavé pozadí, bílý text.", selector="#cta")
    value["logic"][0]["flow"] = FLOW
    value["design"] = DESIGN
    value.update(changes)
    return value


def test_v6_parts_are_kept_and_normalized():
    selectors = {}
    proposal = proposal_of(found(), selectors)
    cta = proposal["sections"][1]
    assert (len(cta["intent"]), cta["look"], "selector" in cta, selectors) == (600, "Tmavé pozadí, bílý text.", False,
                                                                                {"cta": "#cta"})
    assert proposal["logic"][0]["flow"] == {key: FLOW.get(key, []) for key in FLOW_KEYS}
    assert "flow" not in proposal["logic"][1]
    assert proposal["design"]["color"]["tokens"] == [{"name": "surface", "value": "#ffffff"}]
    assert proposal["design"]["button"]["tokens"][0]["value"] == "8px"
    assert any("intent zkrácen" in note for note in proposal["notes"])
    assert any(note.startswith("Design: ") and "ink" in note for note in proposal["notes"])


def test_invalid_v6_parts_are_dropped_with_note_not_failed():
    value = found(design={"color": []})
    value["sections"][0].update(look="", selector=5)
    value["logic"][0]["flow"] = {"inputs": [5]}
    value["logic"][1]["flow"] = {"kroky": ["x"]}
    selectors = {}
    proposal = proposal_of(value, selectors)
    assert "design" not in proposal and "look" not in proposal["sections"][0] and selectors == {"cta": "#cta"}
    assert all("flow" not in item for item in proposal["logic"])
    assert len(proposal["notes"]) == 6  # design, look, selector, zkrácený intent, dva toky
    assert "design" not in proposal_of(found(design={"color": {"tokens": [{"name": "x", "value": "blue"}]}}))
    assert len(proposal_of(found(design=None))["notes"]) == 1  # bez designu žádná poznámka o něm
    long = found()
    long["logic"][0]["flow"] = {"inputs": ["x" * 200] * 9}
    trimmed = proposal_of(long)
    assert trimmed["logic"][0]["flow"]["inputs"] == ["x" * 160] * 8 and any("zkrácen na 8" in note for note in trimmed["notes"])


def test_prompt_names_the_new_parts():
    prompt = prompt_for("https://example.com", "Jen formulář.", "")
    assert all(word in prompt for word in ("selector", "look", "flow", "dataTo", "surface", "Jen formulář."))
    assert "<" + "ROLES>" not in prompt and "actor" in prompt
