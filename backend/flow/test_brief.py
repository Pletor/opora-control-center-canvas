import pytest

from backend.flow.brief import brief
from backend.flow.graph_check import FlowInvalid
from backend.flow.test_simulate import BAD_CASE, DOWN_CASE, OK_CASE, bmi_graph

FLOW = {"title": "Uložit BMI", "description": "Formulář, kontrola, výpočet a uložení.",
        "ownerRef": "opora:library:human:functions/ulozit-bmi"}


def bmi():
    graph = bmi_graph([OK_CASE, BAD_CASE, DOWN_CASE])
    graph["nodes"][0]["params"]["title"] = "Formulář"
    graph["nodes"][1]["params"] |= {"title": "Endpoint", "description": "Přijme měření."}
    graph["edges"][0]["data"] = {"kind": "json", "schema": {"height": "number"}, "example": {"height": 180}}
    graph["edges"][-1]["data"] = {"kind": "json", "schema": {"message": "text"}}
    return graph


def test_bmi_brief_has_every_section_in_order_with_layers_cases_and_back_link():
    out = brief(FLOW, {"n": 3}, bmi())
    assert list(out["sections"]) == ["Cíl", "Kroky po vrstvách", "Rozhraní", "Data", "Chybové stavy",
                                     "Případy jako testy", "Odkaz zpět"]
    text = out["markdown"]
    heads = [text.index(f"\n## {name}\n") for name in out["sections"]]
    assert heads == sorted(heads)
    steps = text.split("## Kroky po vrstvách")[1].split("## Rozhraní")[0]
    assert steps.index("### Frontend") < steps.index("### Backend") < steps.index("### Databáze")
    assert steps.index("**Formulář**") < steps.index("**bad**") and "Přijme měření." in steps
    assert "`POST /bmi` (Endpoint)" in out["markdown"] and '`{"height": "number"}`' in text
    assert "Tabulka `measurements` zapisuje" in text and "sloupce: `height`, `weight`, `bmi`" in text
    assert "druh `json`" in text and "příklad `{\"height\": 180}`" in text
    assert "výstup `false` vede na bad" in text and "Chybová zpráva ve FE: bad – Neplatná výška" in text
    assert "### V pořádku (`ok`)" in text and "- Simulace: shoda" in text
    assert "- Trasa: fe: Formulář, be: Endpoint, be: validate, be: bmi, db: write, be: confirm, fe: ok" in text
    assert "`opora:library:human:functions/ulozit-bmi@3`" in text and "plátno se nemění tiše" in text


def test_failing_case_is_reported_as_mismatch_and_empty_sections_are_dropped():
    graph = bmi_graph([{**OK_CASE, "input": {"height": 180, "weight": 90}}])
    graph["edges"] = [{k: v for k, v in e.items() if k != "via"} for e in graph["edges"]]
    out = brief({"title": "X", "ownerRef": "opora:library:agent:a/b"}, {"n": 1}, graph)
    assert "Simulace: NESHODA – Tabulka measurements" in out["markdown"]
    assert "Data" in out["sections"] and "Cíl" in out["sections"] and out["sections"]["Cíl"] == ["**X**"]
    plain = brief({"title": "X", "ownerRef": "o"}, {"n": 1}, {"nodes": graph["nodes"][:1], "edges": []})
    assert list(plain["sections"]) == ["Cíl", "Kroky po vrstvách", "Odkaz zpět"]


def test_graph_without_steps_is_422_material():
    with pytest.raises(FlowInvalid, match="Plátno nemá žádné kroky."):
        brief(FLOW, {"n": 1}, {"nodes": [], "edges": []})
