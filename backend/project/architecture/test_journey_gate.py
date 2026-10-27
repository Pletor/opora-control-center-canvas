"""Brána uzavření karty na cestě (`docs/brana-cesty.md` §5): kdo blokuje a proč."""

from backend.project.architecture.journey_gate import blocking_by_node, journeys_blocking, refusal
from backend.project.architecture.journey_plan import journey_plan
from backend.project.architecture.test_journey_runs import make_graph, node, run


def graph_with_component():
    graph = make_graph()
    graph["nodes"] += [node("form", "novinky"), node("button", "form"), node("loose", "web")]
    return graph


def latest(graph, **kwargs):
    digest = journey_plan(graph, "kampan")["digest"]
    record = run(digest, **kwargs)
    record["passed"] = all(segment["ok"] for segment in record["segments"])
    return {("web", "kampan"): record}


def reasons(graph, node_id, runs):
    return [(item["journeyId"], item["reason"]) for item in journeys_blocking(graph, node_id, runs)]


def test_card_on_journey_is_blocked_without_run():
    graph = graph_with_component()
    blocking = journeys_blocking(graph, "button", {})
    assert blocking == [{"journeyId": "kampan", "applicationId": "web", "name": "Kampaň", "reason": "chybí ověření"}]
    assert refusal(blocking) == "cesta Kampaň: chybí ověření"


def test_page_itself_is_on_journey():
    graph = graph_with_component()
    assert reasons(graph, "novinky", {}) == [("kampan", "chybí ověření")]


def test_stale_run_blocks():
    graph = graph_with_component()
    runs = latest(graph)
    runs[("web", "kampan")]["planDigest"] = "sha256:" + "0" * 64
    assert reasons(graph, "form", runs) == [("kampan", "zastaralé")]


def test_failed_run_names_first_failed_segment():
    graph = graph_with_component()
    assert reasons(graph, "form", latest(graph, s3=False)) == [("kampan", "neprošel přechod s2 → s3")]


def test_incomplete_run_blocks():
    graph = graph_with_component()
    runs = latest(graph)
    record = runs[("web", "kampan")]
    record["segments"] = record["segments"][:1]
    record["passed"] = False
    assert reasons(graph, "form", runs) == [("kampan", "nepokrývá všechny přechody")]


def test_fresh_passed_run_opens_the_gate():
    graph = graph_with_component()
    assert journeys_blocking(graph, "button", latest(graph)) == []


def test_card_off_journey_is_not_affected():
    graph = graph_with_component()
    assert journeys_blocking(graph, "loose", {}) == []
    assert journeys_blocking(graph, "web", {}) == []
    assert journeys_blocking(graph, "missing", {}) == []


def test_broken_journey_does_not_block():
    graph = graph_with_component()
    # Rozbitá cesta (chybí stránka „smazana“) dostane krok i na home; home pak blokuje jen nerozbitá cesta.
    graph["nodes"][0]["site"]["journeys"][1]["steps"].insert(0, {"id": "z", "page": "home"})
    assert [item["journeyId"] for item in journeys_blocking(graph, "home", {})] == ["kampan"]


def test_blocking_by_node_skips_free_cards():
    graph = graph_with_component()
    assert set(blocking_by_node(graph, {}, ["form", "loose", "home"])) == {"form", "home"}
    assert blocking_by_node({"nodes": [], "edges": []}, {}, ["x"]) == {}
