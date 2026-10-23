"""Strop předávky v zadání: pořadí, 8 kB, deterministické zkracování a ukazatele na úplná data."""
from backend.canvas.opora_execution_handoff_cap import CAP_BYTES, build, size

PARAMS = {"method": "GET", "params": {"project": "p", "workspace": "w"}, "executions": "/api/oporahub/executions?nodeId={id}"}


def entry(card, words=10, steps=3, decisions=2):
    text = " ".join(f"{card}-slovo{i}" for i in range(words))
    return {"cardId": card, "title": f"Karta {card}", "executionId": f"run-{card}", "resultStatus": "reported",
            "resultAt": "2026-10-23T10:00:00+00:00",
            "result": {"summary": text, "checks": [{"name": "tests", "status": "passed", "summary": f"KONTROLA-{card}"}],
                       "stepResults": [{"stepId": f"s{i}", "status": "done",
                                        "evidence": {"notes": text, "checks": [f"KONTROLA-{card}"] * 5,
                                                     "commits": ["a" * 40] * 5}} for i in range(steps)]},
            "decisions": [{"text": f"{card} rozhodnutí {i}", "why": text, "alternatives": ["x", "y"], "evidence": ["PR #1"]}
                          for i in range(decisions)],
            "pr": {"number": 7, "state": "merged", "mergeSha": "b" * 40, "url": "https://github.com/o/r/pull/7"},
            "lens": {"endpoint": f"/api/oporahub/review-lens?nodeId={card}", "stored": False},
            "full": {"results": f"/api/oporahub/executions/run-{card}/results"}}


def flow(edge, words=10):
    return {"edgeId": edge, "fromArea": {"id": "area-1", "title": "Příjem"}, "handoff": "předávám " * words,
            "summary": "souhrn " * words, "sentAt": "2026-10-22T08:00:00+00:00", "full": {"state": "/api/desktop-v3/state"}}


def test_small_handoff_is_complete_and_says_nothing_was_trimmed():
    value = build([entry("a", steps=2)], [flow("f1")], PARAMS)
    assert value["bytes"] == size(value) <= CAP_BYTES
    assert [item["cardId"] for item in value["predecessors"]] == ["a"]
    assert value["predecessors"][0]["stepResults"][0] == {
        "id": "s0", "status": "done", "evidence": {"notes": value["predecessors"][0]["summary"],
                                                    "checks": ["KONTROLA-a"] * 3, "commits": ["a" * 12] * 3}}
    assert value["predecessors"][0]["decisions"][0]["why"]
    assert value["predecessors"][0]["pr"]["mergeSha"] == "b" * 40
    assert value["areaFlows"][0]["edgeId"] == "f1"
    # Pět kontrol a pět commitů v důkazu kroku se zkrátilo na tři: řekne to `trimmed` a ukáže kam pro zbytek.
    assert value["trimmed"] == [{"id": "a", "fields": ["stepResults"], "full": {"results": "/api/oporahub/executions/run-a/results"}}]
    assert value["omitted"] == []


def test_empty_handoff_has_shape_and_fits():
    value = build([], [], PARAMS)
    assert value["predecessors"] == value["areaFlows"] == value["trimmed"] == value["omitted"] == []
    assert value["capBytes"] == CAP_BYTES and value["bytes"] == size(value)


def test_cap_holds_and_closest_entries_keep_the_most_detail():
    cards = [entry(f"c{i}", words=60, steps=12, decisions=8) for i in range(6)]
    value = build(cards, [flow("f1", 200)], PARAMS)
    assert value["bytes"] == size(value) <= CAP_BYTES
    kept = [item["cardId"] for item in value["predecessors"]]
    assert kept == [f"c{i}" for i in range(len(kept))]  # pořadí vstupu, žádné přeskupení
    first, last = value["predecessors"][0], value["predecessors"][-1]
    assert size(first) >= size(last)
    assert "stepResults" in first
    # Nic se neztratí: co se nevešlo celé, má ukazatel; vynechané položky jsou v `omitted`.
    everything = {item["cardId"] for item in cards} | {"f1"}
    shown = set(kept) | {item["edgeId"] for item in value["areaFlows"]}
    assert everything == shown | {item["id"] for item in value["omitted"]}
    assert all(item["full"] for item in value["trimmed"])
    assert {item["id"] for item in value["trimmed"]} <= shown


def test_trim_order_is_from_the_end():
    cards = [entry(f"c{i}", words=150, steps=10, decisions=8) for i in range(3)]
    value = build(cards, [], PARAMS)
    levels = [len(item.get("stepResults", [{}])[0].get("evidence", {}).get("notes", "")) if item.get("stepResults") else -1
              for item in value["predecessors"]]
    assert levels == sorted(levels, reverse=True)


def test_many_predecessors_still_fit_and_stay_addressable():
    cards = [entry(f"karta-{i:03d}", words=30) for i in range(200)]
    value = build(cards, [], PARAMS)
    assert value["bytes"] <= CAP_BYTES
    ids = [item["cardId"] for item in value["predecessors"]] + [item["id"] for item in value["omitted"]]
    assert ids == [item["cardId"] for item in cards]
    assert value["fullParams"]["executions"].endswith("{id}")


def test_build_is_deterministic():
    cards = [entry(f"c{i}", words=80, steps=8) for i in range(5)]
    assert build(cards, [flow("f1", 50)], PARAMS) == build([dict(item) for item in cards], [flow("f1", 50)], PARAMS)


def test_hundreds_of_predecessors_end_as_a_count():
    value = build([entry(f"karta-{i:03d}", words=30) for i in range(400)], [], PARAMS)
    assert value["bytes"] == size(value) <= CAP_BYTES
    assert len(value["predecessors"]) + len(value["omitted"]) + value["omittedMore"] == 400
