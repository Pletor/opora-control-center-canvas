from backend.canvas.protected_fields import protected_changes


def node(node_id, kind="node", **extra):
    return {"id": node_id, "kind": kind, "parentId": None, **extra}


def graph(nodes, edges=()):
    return {"nodes": list(nodes), "edges": [{"id": f"e{i}", "source": s, "target": t, **({"port": p} if p else {})}
                                             for i, (s, t, p) in enumerate(edges)]}


def test_existing_gate_checks_and_goal_mode_are_protected():
    old = graph([node("s1", "sector", gateNodeId="g"), node("g"), node("c", checks=[{"id": "t", "command": "pytest"}])])
    new = graph([node("s1", "sector"), node("g"), node("c", checks=[{"id": "t", "command": "true"}], goal_mode="until_checks_pass")])
    assert protected_changes(old, new) == ["s1.gateNodeId", "c.checks", "c.goal_mode"]


def test_new_cards_may_carry_checks_and_gate_when_planned():
    old = graph([node("s1", "sector")])
    new = graph([node("s1", "sector"), node("s2", "sector", gateNodeId="g"), node("g", checks=[{"id": "t", "command": "pytest"}])],
                [("s1", "s2", None)])
    assert protected_changes(old, new) == []


def test_next_link_between_existing_sectors_is_protected_both_ways():
    sectors = [node("s1", "sector"), node("s2", "sector")]
    linked = graph(sectors, [("s1", "s2", None)])
    unlinked = graph(sectors)
    assert protected_changes(linked, unlinked) == ["next s1→s2"]
    assert protected_changes(unlinked, linked) == ["next s1→s2"]
    # Jiný port mezi sektory ani vazba karty bránou neotevírají.
    assert protected_changes(unlinked, graph(sectors, [("s1", "s2", "rule")])) == []


def test_sector_cannot_be_turned_into_card_to_drop_its_gate():
    old = graph([node("s1", "sector")])
    new = graph([node("s1", "node")])
    assert protected_changes(old, new) == ["s1.kind"]


def test_unchanged_graph_and_ordinary_edits_are_free():
    old = graph([node("c", checks=[{"id": "t", "command": "pytest"}], name="A")])
    new = graph([node("c", checks=[{"id": "t", "command": "pytest"}], name="B")])
    assert protected_changes(old, new) == []
