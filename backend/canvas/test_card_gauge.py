from backend.canvas import card_gauge as g

CONFIG = {"sensitive": ["**/migrations/**", "pyproject.toml"], "security": {"paths": ["**/auth/**"]}, "mediumFiles": 10}


def step(index, kind="code", files=()):
    return {"id": f"s{index}", "order": index, "title": "t", "acceptance": ["a"], "dependsOn": [], "kind": kind,
            "files": list(files)}


def node(identifier, parent=None, card=None):
    value = {"id": identifier, "kind": "node", "parentId": parent, "name": identifier}
    return {**value, "card": card} if card else value


def graph(nodes, pairs=()):
    return {"nodes": nodes, "edges": [{"id": f"e{a}{b}", "source": a, "target": b} for a, b in pairs]}


def test_small_ample_card_is_s_with_sonnet_and_opus_advisor():
    steps = [step(1, files=["a.py"]), step(2, files=["b.py"]), step(3, kind="test")]
    run = g.profile(node("c"), graph([node("c")]), steps, config=CONFIG)
    assert run["points"] == 4.0
    assert (run["label"], run["effort"], run["model"], run["advisor"]) == ("S", "medium", "sonnet", "opus")
    assert run["source"] == "recommended" and run["handout"] is True and run["humanReview"] is False
    assert g.tag(run) == "[S · sonnet+opus]"


def test_big_card_with_design_and_migration_is_xl_and_not_handed_out():
    steps = [step(i) for i in range(1, 14)] + [step(14, kind="design", files=["db/migrations/001.sql"])]
    run = g.profile(node("c"), graph([node("c")]), steps, config=CONFIG)
    assert run["label"] == "XL" and run["handout"] is False and run["effort"] is None
    assert run["advisor"] == "opus" and run["humanReview"] is True  # critical risk forces both
    assert g.tag(run) == "[XL – nepředávat, rozděl]"


def test_points_are_capped_per_item_and_thresholds_inclusive():
    plan = {"steps": 30, "files": [f"f{i}" for i in range(40)], "kinds": {"research": 1}}
    total, parts = g.points_of(plan, "elevated", 9)
    assert parts == {"steps": 12, "files": 10, "heavyKinds": 2.0, "risk": 3.0, "fanIn": 3}
    assert total == 30
    assert [g.label_of(value) for value in (0, 3, 3.5, 6, 10, 15, 15.5)] == ["XS", "XS", "S", "S", "M", "L", "XL"]


def test_xs_has_no_advisor_and_label_mapping_follows_o10():
    assert g.run_of(1, "standard")["advisor"] is None
    assert g.run_of(8, "standard")["effort"] == "high"
    assert g.run_of(12, "standard")["effort"] == "xhigh"


def test_card_effort_wins_and_reports_mismatch_over_one_step():
    run = g.run_of(14, "standard", {"effort": "low"})  # L recommended, low chosen = 3 steps apart
    assert run["source"] == "card" and run["effort"] == "low" and run["advisor"] is None
    assert run["recommended"] == {"label": "L", "effort": "xhigh", "model": "sonnet", "advisor": "opus"}
    assert run["mismatch"] is True and "ODCHYLKA" in g.tag(run)
    near = g.run_of(5, "standard", {"effort": "high", "model": "opus"})  # S vs high = 1 step
    assert near["mismatch"] is False and near["model"] == "opus"
    assert g.run_of(30, "standard", {"effort": "max"})["handout"] is True  # human/heart decided


def test_critical_risk_forces_advisor_even_on_card_effort():
    run = g.run_of(1, "critical", {"effort": "max"})
    assert run["model"] == "opus" and run["advisor"] == "opus" and run["humanReview"] is True


def test_risk_from_files():
    assert g.risk_of(["a.py"], CONFIG)["level"] == "standard"
    assert g.risk_of(["x/auth/login.py"], CONFIG) == {"level": "elevated", "reasons": ["security_path:**/auth/**"]}
    assert g.risk_of([f"f{i}" for i in range(10)], CONFIG)["reasons"] == ["many_files"]
    assert g.risk_of(["pyproject.toml"], CONFIG)["level"] == "critical"


def test_fan_split_and_tally():
    nodes = [node("a"), node("b"), node("c"), node("a1", "a"), node("a2", "a"), node("a11", "a1")]
    index = g.graph_index(graph(nodes, [("a", "b"), ("c", "b"), ("b", "c")]))
    assert index["fanIn"]["b"] == 2 and index["fanOut"]["b"] == 1
    assert g.split_of(index, "a") == {"children": 2, "depth": 2} and g.split_of(index, "b") == {"children": 0, "depth": 0}
    history = [{"nodeId": "a", "executionId": "x3", "state": "running", "createdAt": "2026-10-30T10:00:00+00:00"},
               {"nodeId": "a", "executionId": "x2", "state": "released"},
               {"nodeId": "a", "executionId": "x1", "state": "released"}]
    tally = g.tally(history, [{"executionId": "x1", "state": "merged"}])
    assert tally == {"a": {"attempts": 3, "failures": 1, "claimedAt": "2026-10-30T10:00:00+00:00"}}


def test_gauge_combines_progress_dod_runs_and_age():
    nodes = [node("a", card={"effort": "medium"}), node("b")]
    index = g.graph_index(graph(nodes, [("b", "a")]))
    entry = {"nodeId": "a", "steps": {"total": 4, "done": 1},
             "dod": {"steps": False, "card_acceptance": True, "gate_ready": True, "merged": False,
                     "plan_written_back": False, "journeys": True, "human_close": False}}
    runs = {"attempts": 2, "failures": 1, "claimedAt": "2026-10-30T10:00:00+00:00"}
    claimed = 1793354400.0  # 2026-10-30T10:00:00Z
    latest = {"state": "running", "deadline": claimed + 900}
    value = g.gauge(entry, nodes[0], [step(1, files=["a.py"])], index, runs, latest, claimed + 120, CONFIG)
    assert value["steps"] == {"total": 4, "done": 1, "percent": 25}
    assert value["dod"] == {"met": 3, "total": 7, "percent": 43}
    assert (value["files"], value["kinds"], value["fanIn"], value["fanOut"]) == (1, {"code": 1}, 1, 0)
    assert (value["attempts"], value["failures"], value["age"], value["costUsd"]) == (2, 1, 120, None)
    assert value["run"]["source"] == "card" and value["run"]["label"] == "XS"
    stopped = g.gauge(entry, nodes[0], [], index, runs, {**latest, "deadline": claimed}, claimed + 120, CONFIG)
    assert stopped["age"] is None


def test_brief_is_the_stable_part():
    run = g.run_of(4, "standard")
    assert g.brief(run) == {"label": "S", "effort": "medium", "model": "sonnet", "advisor": "opus",
                            "handout": True, "humanReview": False}


def test_thin_card_gets_question_mark_and_run_from_card():
    card = node("c", card={"effort": "high", "model": "opus"})
    run = g.profile(card, graph([card]), [step(1)], config=CONFIG)
    assert (run["label"], run["evidence"], run["recommended"]) == ("?", "thin", None)
    assert (run["effort"], run["model"], run["advisor"], run["source"]) == ("high", "opus", "opus", "card")
    assert "mismatch" not in run and run["handout"] is True
    assert g.tag(run) == "[? – doplň kroky a soubory]"


def test_thin_card_without_effort_gets_safe_default():
    run = g.profile(node("c"), graph([node("c")]), [], config=CONFIG)
    assert (run["label"], run["effort"], run["model"], run["advisor"]) == ("?", "medium", "sonnet", "opus")
    assert run["source"] == "default" and run["reason"] == "málo podkladů – doplň kroky a soubory"


def test_text_signals_raise_risk_to_elevated_without_files():
    s1 = {**node("s1"), "name": "S.1 Tabulky entit (migrace 0045, RLS)"}
    config = {**CONFIG, "sensitive": ["**/migrations/**", "**/auth/**", "**/*secret*"]}
    assert g.risk_of([], config, g.text_of(s1, [step(1)])) == {"level": "elevated",
                                                                 "reasons": ["text: migrace", "text: RLS"]}
    assert g.risk_of([], config, "Napiš migraci a ulož secret")["level"] == "elevated"  # never critical from text
    assert g.risk_of([], config, "Seznam úkolů, autor a datum")["level"] == "standard"
    assert g.risk_of([], {**CONFIG, "sensitive": [], "security": {"paths": []}}, "migrace")["level"] == "standard"
    run = g.profile(s1, graph([s1]), [step(1)], config=config)
    assert run["label"] == "?" and run["evidence"] == "thin"
    files = g.risk_of(["db/migrations/0045.sql"], config, "migrace")
    assert files["level"] == "critical"  # real files decide, the text is ignored


def test_card_with_three_steps_and_two_files_stays_s():
    titled = {**node("c"), "name": "Migrace 0045"}
    steps = [step(1, files=["a.py"]), step(2, files=["b.py"]), step(3, kind="test")]
    run = g.profile(titled, graph([titled]), steps, config=CONFIG)
    assert (run["label"], run["evidence"], run["points"]) == ("S", "ok", 4.0)
