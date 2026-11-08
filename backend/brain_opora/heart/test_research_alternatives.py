import json

from backend.brain_opora.heart.test_opora_research_map import AT, args, mapping, result
from backend.editor.research import model


def test_verified_citation_does_not_turn_project_inference_into_verified_fact():
    source = result()
    source["facts"][0]["kind"] = "practice"
    source["facts"][0]["claim"] = "Derived recommendation for this project"
    batch = mapping.batch(source, "vf_interpretation", args(), AT)
    finding = next(op for op in batch["operations"] if op.get("title") == "Derived recommendation for this project")
    assert finding["verification"]["status"] == "inference"
    assert finding["sources"][0]["verification"]["status"] == "verified"
    assert json.loads(finding["content"]) == source["facts"][0]
    model.card({key: finding[key] for key in model.CARD})


def test_compared_options_keep_evidence_risks_and_unknowns_without_implied_approval():
    source = result()
    source["digest"]["layers"] = {"security": {
        "recommended": "Select only after tenant isolation review", "risks": ["cross-tenant session"],
        "options": [
            {"approach": "Shared issuer", "pros": "central policy", "cons": "tenant context required", "facts": ["f0", "f2"]},
            {"approach": "Separate issuers", "pros": "independent configuration", "cons": "operations cost", "facts": ["f1", "missing"]}]}}
    source["digest"]["hypotheses"] = [{"claim": "Customer requires own issuer", "check": "Ask customer"}]
    batch = mapping.batch(source, "vf_compare", args(), AT)
    assert batch == mapping.batch(source, "vf_compare", args(), AT)
    options = [op for op in batch["operations"] if op.get("kind") == "option"]
    assert len(options) == 2
    for item in options:
        model.card({key: item[key] for key in model.CARD})
        content = json.loads(item["content"])
        assert content["risks"] == ["cross-tenant session"]
        assert content["hypotheses"] == source["digest"]["hypotheses"]
        assert item["verification"]["status"] == "inference"
        assert item["status"] == "open"
    links = [op for op in batch["operations"] if op.get("toId") == options[0]["id"]]
    assert {link["relation"] for link in links} == {"supports", "elaborates"}
    ids = {op["id"] for op in batch["operations"] if op["op"] == "card"}
    assert all(op["fromId"] in ids and op["toId"] in ids for op in batch["operations"] if op["op"] == "edge")
    assert json.loads(options[1]["content"])["option"]["facts"] == ["f1", "missing"]
