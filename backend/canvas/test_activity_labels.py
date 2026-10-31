"""Popisky a dotčené uzly zápisů, které mění karty (docs/zaznam-cinnosti.md, „Stopa karty“)."""
import json

from backend.canvas.activity_labels import (
    architecture_trace,
    body_label,
    changeset_label,
    clean,
    graph_label,
    plan_nodes,
    proposal_trace,
    task_label,
)
from backend.canvas.activity_log import describe, entry_label

ORDER = {"updateNodes": [{"id": f"n{index}", "fields": {"order": 100 + index}} for index in range(12)]}


def test_graph_labels_say_what_changes():
    assert graph_label(ORDER) == "Pořadí 12 karet"
    assert graph_label({"updateNodes": [{"id": "a", "fields": {"memberOf": "area"}}]}) == "Členství v oblasti u 1 karty"
    assert graph_label({"nodes": [{"ref": "a"}, {"ref": "b"}, {"ref": "c"}], "removeEdges": ["e1"]}) == \
        "Návrh grafu: +3 karty, −1 vazba"
    assert graph_label({"removeNodes": ["a"], "adoptArchitectureContext": True}) == \
        "Návrh grafu: −1 karta, převzetí architektury"
    assert graph_label({"adoptArchitectureContext": True}) == "Návrh grafu: převzetí architektury"


def test_plan_nodes_are_existing_ids_only():
    plan = {"updateNodes": [{"id": "a", "fields": {}}], "removeNodes": ["b", "a"], "nodes": [{"ref": "new"}],
            "edges": [{"source": "@c", "target": "new"}]}
    assert plan_nodes(plan) == ["a", "b", "c"]
    assert plan_nodes("nonsense") == []


def test_changeset_task_and_clean():
    assert changeset_label([{"nodeId": "a", "fields": {"steps": [{}, {}, {}, {}]}}]) == "Kroky karty: 4 kroky"
    assert changeset_label([{"nodeId": "a", "fields": {}}, {"nodeId": "b", "fields": {}}]) == "Návrh zadání: 2 karty"
    assert task_label("  Hero\n sekce ") == "Úkol do fronty: Hero sekce" and task_label(None) == "Úkol do fronty"
    long = clean("x" * 300)
    assert len(long) == 120 and long.endswith("…") and "|" not in clean("a | b")


def test_proposal_trace_reads_stored_records():
    assert proposal_trace({"plan": ORDER}) == ("Přijetí: Pořadí 12 karet", [f"n{index}" for index in range(12)])
    assert proposal_trace({"additions": {"nodes": [{"id": "x"}], "edges": []}}) == ("Přijetí: Návrh grafu: +1 karta", ["x"])
    assert proposal_trace({"changes": [{"nodeId": "k", "fields": {}}]}) == ("Přijetí: Návrh zadání: 1 karta", ["k"])


def test_architecture_trace_compares_with_stored_revision():
    old = {"nodes": [{"id": "p1", "name": "A"}, {"id": "p2", "name": "B"}], "edges": []}
    ordered = {"nodes": [{"id": "p1", "name": "A", "order": 101}, {"id": "p2", "name": "B"}], "edges": []}
    assert architecture_trace(old, ordered) == ("Architektura: pořadí 1 stránky", ["p1"])
    renamed = {"nodes": [{"id": "p1", "name": "C"}, {"id": "p3"}], "edges": []}
    assert architecture_trace(old, renamed) == ("Architektura: změna u 3 uzlů", ["p1", "p3", "p2"])
    assert architecture_trace(old, {**old, "edges": [{"id": "e"}]}) == ("Architektura: vazby", [])


def test_describe_puts_label_first_and_merges_route_hint():
    body = json.dumps({"project": "p", "workspace": "w", "subject": "s", "plan": ORDER}).encode()
    described = describe(body, {}, "/api/oporahub/graph-proposals", {"nodeIds": ["n0", "z"], "label": ""})
    assert described["summary"].startswith("Pořadí 12 karet | plan,subject")
    assert described["nodeIds"][-1] == "z" and described["nodeIds"].count("n0") == 1
    hinted = describe(b"{}", {}, "/api/x", {"nodeIds": ["a"], "label": "Architektura: pořadí 1 stránky"})
    assert (hinted["summary"], hinted["nodeIds"]) == ("Architektura: pořadí 1 stránky", ["a"])
    # Klíč těla s oddělovačem nesmí vyrobit falešný popisek.
    spoof = describe(json.dumps({"Pořadí 99 karet | x": 1}).encode(), {}, "/api/y")
    assert entry_label(spoof["summary"]) == "Pořadí 99 karet / x"
    assert body_label("/api/other", {"title": "t"}) == ("", [])


def test_created_nodes_skip_dry_run():
    from backend.canvas.activity_labels import created_nodes
    assert created_nodes({"dryRun": False, "refs": {"a": "id-a"}}) == ["id-a"]
    assert created_nodes({"dryRun": True, "refs": {"a": "id-a"}}) == []
    assert created_nodes({"additions": {"nodes": [{"id": "x"}]}, "refs": {"r": "x"}}) == ["x"]
