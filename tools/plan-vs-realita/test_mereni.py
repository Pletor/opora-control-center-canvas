import importlib.util
import os
import pathlib

_spec = importlib.util.spec_from_file_location("mereni", pathlib.Path(__file__).with_name("mereni.py"))
assert _spec and _spec.loader
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def N(id, x=0, y=0, kind="node", ref=None, **kw):
    d = {"id": id, "kind": kind, "name": id, "parentId": None, "x": x, "y": y}
    if ref:
        d["sourceRef"] = ref
    d.update(kw)
    return d


def A(id, x, y, w, h):
    return N(id, x, y, kind="area", size={"w": w, "h": h})


def test_area_smallest_wins_and_centre():
    big, small = A("big", 0, 0, 1000, 1000), A("small", 0, 0, 400, 300)
    card = N("c", 0, 0)  # centre 180,120 -> in both
    assert m.area_of(card, [big, small, card])["id"] == "small"
    far = N("f", 500, 0)  # centre 680,120 -> only big
    assert m.area_of(far, [big, small, far])["id"] == "big"
    com = N("k", 0, 0, kind="comment")
    assert m.area_of(com, [small, com])["id"] == "small"
    assert m.area_of(big, [big, small]) is None


def test_area_parent_must_match():
    ar = A("a", 0, 0, 1000, 1000)
    card = N("c", 0, 0, parentId="p")
    assert m.area_of(card, [ar, card]) is None


def test_units_steps_blocks_card():
    assert m.card_units({"steps": [{"id": "1", "done": True}, {"id": "2", "done": False}]})[0] == "step"
    blocks = [
        {"id": "p", "state": {"status": "open"}},
        {"id": "l1", "parentBlockId": "p", "state": {"status": "met"}},
        {"id": "l2", "parentBlockId": "p", "state": {"status": "open"}},
    ]
    kind, units = m.card_units({"blocks": blocks})
    assert kind == "block" and [u["id"] for u in units] == ["l1", "l2"]
    kind, units = m.card_units({"done": {"by": "agent", "at": "2026", "confirmed": False}})
    assert kind == "card" and units[0]["done"]
    assert not m.card_units({"done": {"by": "human", "at": "", "confirmed": False}})[1][0]["done"]


def test_nested_children_blocks():
    _, units = m.card_units({"blocks": [{"id": "p", "children": [{"id": "c", "state": {"status": "met"}}]}]})
    assert [u["id"] for u in units] == ["c"] and units[0]["done"]


def view(nodes, edges=()):
    return {"graph": {"nodes": nodes, "edges": list(edges)}}


def test_three_levels_separate(tmp_path):
    (tmp_path / "src").mkdir()
    nodes = [A("ar", -10, -10, 800, 800),
             N("a", ref={"origin": "existing", "path": "src", "kind": "directory"}),
             N("b", ref={"origin": "planned", "path": "nope", "kind": "directory"})]
    state = {"nodes": {
        "a": {"steps": [{"id": "1", "done": True}, {"id": "2", "done": False}], "done": {"confirmed": True}},
        "b": {"done": {"by": "agent", "at": "x", "confirmed": False}},
    }}
    r = m.analyse(view(nodes), state, str(tmp_path), None)
    ar = r["areas"]["ar"]
    assert ar["units"] == 3
    assert (ar["tvrdi"], ar["kod"], ar["potvrzeno"]) == (2, 2, 2)
    assert r["project"]["tvrdiPct"] == 66.7


def test_no_checkout_kod_na():
    r = m.analyse(view([N("a")]), {"nodes": {}}, None, None)
    assert r["project"]["kod"] is None and r["project"]["kodPct"] is None
    assert r["coverage"] is None


def test_no_area_bucket():
    r = m.analyse(view([N("a")]), {"nodes": {}}, None, None)
    assert m.NO_AREA in r["areas"]


def types(r, t):
    return [f for f in r["findings"] if f["type"] == t]


def test_slepa_ulicka():
    nodes = [N("a"), N("b", x=1000), N("c", x=2000)]
    st = {"nodes": {"a": {"blocks": [{"id": "bl", "ports": [{"id": "p1", "label": "L"}],
                                       "state": {"status": "unmet", "onUnmet": {"kind": "none"}}}]}}}
    edges = [{"id": "e", "source": "a", "target": "b"}]
    r = m.analyse(view(nodes, edges), st, None, None)
    reasons = [f["reason"] for f in types(r, "SLEPA_ULICKA")]
    assert any("onUnmet" in x for x in reasons)
    assert any("port bloku" in x for x in reasons)
    assert any("izolovan" in x for x in reasons)
    assert any("předchůdce" in x for x in reasons)  # b nasleduje po a s unmet blokem
    # port s hranou -> neni slepy
    edges.append({"id": "e2", "port": "block", "source": "a", "target": "c", "sourceBlockId": "bl", "sourcePortId": "p1"})
    r = m.analyse(view(nodes, edges), st, None, None)
    assert not [f for f in types(r, "SLEPA_ULICKA") if f["reason"] == "port bloku bez hrany"]


def test_dalsi_krok():
    nodes = [N("a"), N("b", x=1000)]
    st = {"nodes": {"a": {"done": {"confirmed": True}}, "b": {"steps": [{"id": "1", "done": False}]}}}
    r = m.analyse(view(nodes, [{"id": "e", "source": "a", "target": "b"}]), st, None, None)
    assert [f for f in types(r, "ZBYVA") if f.get("dalsi_krok")]


def test_doplnit_ubrat_vymenit(tmp_path):
    (tmp_path / "real").mkdir()
    ex = {"origin": "existing", "path": "real", "kind": "directory"}
    nodes = [N("a", ref=ex), N("b", ref=ex), N("c", ref={"origin": "planned", "path": "real", "kind": "directory"}),
             N("d", ref={"origin": "existing", "path": "gone", "kind": "directory"}), N("e"),
             A("empty", 5000, 5000, 100, 100)]
    st = {"nodes": {"a": {"steps": [{"id": "1", "done": False}]}}}
    r = m.analyse(view(nodes), st, str(tmp_path), None)
    assert len(types(r, "UBRAT")) == 1
    v = {f["propose"] for f in types(r, "VYMENIT")}
    assert v == {"existing", "replace"}
    d = [f["reason"] for f in types(r, "DOPLNIT")]
    assert "karta bez sourceRef" in d and "krok bez acceptance" in d and "oblast bez karet" in d
    assert "karta bez kroků, bloků i kritérií" in d


def test_graphify_coverage_orphans_new_paths(tmp_path):
    nodes = [A("A1", -10, -10, 500, 500), A("A2", 900, -10, 500, 500),
             N("a", ref={"origin": "existing", "path": "x", "kind": "directory"}),
             N("b", x=1000, ref={"origin": "existing", "path": "y/b.py", "kind": "file"})]
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    (tmp_path / "y" / "b.py").write_text("")
    g = {"nodes": [{"id": "n1", "source_file": "x/a.py"}, {"id": "n2", "source_file": "y/b.py"},
                   {"id": "n3", "source_file": "z/o.py"}],
         "links": [{"source": "n1", "target": "n2", "relation": "imports"},
                   {"source": "n3", "target": "n2", "relation": "calls"},
                   {"source": "n1", "target": "n1", "relation": "calls"},
                   {"source": "n1", "target": "n2", "relation": "contains"}]}
    for n in nodes:
        n["name"] = n["id"]
    r = m.analyse(view(nodes), {"nodes": {}}, str(tmp_path), g)
    assert r["coverage"]["covered"] == 2 and r["coverage"]["files"] == 3
    nc = types(r, "NOVA_CESTA")
    assert len(nc) == 1 and nc[0]["count"] == 1 and nc[0]["toArea"] == "A2"
    sir = types(r, "SIROTEK")
    assert sir[0]["file"] == "z/o.py" and sir[0]["suggestArea"] == "A2" and sir[0]["suggestScore"] == "1/1"
    # hrana mezi kartami potlaci NOVA_CESTA
    r = m.analyse(view(nodes, [{"id": "e", "source": "a", "target": "b"}]), {"nodes": {}}, str(tmp_path), g)
    assert not types(r, "NOVA_CESTA")


def test_markdown_runs():
    r = m.analyse(view([N("a")]), {"nodes": {}}, None, None)
    assert "ZBYVA" in m.markdown(r)
    assert os.path  # no network used
