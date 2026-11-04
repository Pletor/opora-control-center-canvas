import pytest

from backend.flow.graph_check import FlowInvalid, graph_errors
from backend.flow.node_types import catalog
from backend.flow.simulate import simulate

KIND = "library_flow"


def node(nid, type_, **params):
    return {"id": nid, "type": type_, "type_version": 1, "params": params, "position": {"x": 0, "y": 0}}


def link(eid, source, target, port="main", via=None):
    return {"id": eid, "source_node": source, "source_port": port, "target_node": target, "target_port": "main",
            "kind": "main", **({"via": via} if via else {})}


def bmi_graph(cases=()):
    """Uložit BMI: formulář → endpoint → validace výšky → (true) BMI → zápis → potvrzení → notifikace; (false) chyba."""
    nodes = [node("form", "fe.form"), node("endpoint", "be.endpoint", method="POST", path="/bmi"),
             node("validate", "be.validate", combinator="and", conditions=[
                 {"left": "$json.height", "operator": ">=", "right": 50},
                 {"left": "$json.height", "operator": "<=", "right": 250}]),
             node("bmi", "be.function", rule="round($json.weight / (($json.height / 100) ** 2), 1)",
                  outputName="bmi"),
             node("write", "db.write", table="measurements", columns=["height", "weight", "bmi"]),
             node("confirm", "be.function", rule="'BMI ' + text($json.inserted.bmi) + ' uloženo'",
                  outputName="message"),
             node("ok", "fe.notify", message="$json.message"),
             node("bad", "fe.notify", message="Neplatná výška")]
    edges = [link("e1", "form", "endpoint", via="http"), link("e2", "endpoint", "validate"),
             link("e3", "validate", "bmi", "true"), link("e4", "validate", "bad", "false", "http"),
             link("e5", "bmi", "write", via="sql"), link("e6", "write", "confirm", via="sql"),
             link("e7", "confirm", "ok", via="http")]
    return {"nodes": nodes, "edges": edges, "cases": list(cases)}


OK_CASE = {"id": "ok", "name": "V pořádku", "start": "form", "input": {"height": 180, "weight": 80},
           "env": {"tables": {"measurements": []}},
           "expect": {"path": ["form", "endpoint", "validate", "bmi", "write", "confirm", "ok"],
                      "rows": {"measurements": [{"height": 180, "weight": 80, "bmi": 24.7}]},
                      "notify": "BMI 24.7 uloženo"}}
BAD_CASE = {"id": "bad", "name": "Neplatná výška", "start": "form", "input": {"height": 20, "weight": 80},
            "expect": {"path": ["form", "endpoint", "validate", "bad"], "notify": "Neplatná výška",
                       "rows": {"measurements": []}}}
DOWN_CASE = {"id": "down", "name": "DB nedostupná", "start": "form", "input": {"height": 180, "weight": 80},
             "env": {"services": {"write": {"error": "DB nedostupná"}}},
             "expect": {"path": ["form", "endpoint", "validate", "bmi", "write"]}}


def test_bmi_graph_with_cases_passes_graph_check():
    graph = bmi_graph([OK_CASE, BAD_CASE, DOWN_CASE])
    assert graph_errors(graph, catalog(KIND), KIND) == []


def test_ok_case_computes_bmi_writes_row_and_notifies():
    out = simulate(bmi_graph([OK_CASE]), "ok")
    assert out["ok"] and out["expect"] == {"ok": True, "diffs": []}
    assert out["tables"] == {"measurements": [{"height": 180, "weight": 80, "bmi": 24.7}]}
    bmi = out["trace"][3]
    assert (bmi["nodeId"], bmi["layer"], bmi["edgeId"], bmi["out"]["bmi"]) == ("bmi", "be", "e3", 24.7)
    assert bmi["rule"].startswith("round(") and out["trace"][2]["branch"] == "true"
    assert out["result"]["message"] == "BMI 24.7 uloženo" and out["notify"] == "BMI 24.7 uloženo"
    assert [s["step"] for s in out["trace"]] == list(range(1, 8))


def test_invalid_height_takes_false_branch_with_error_notification():
    out = simulate(bmi_graph(), case=BAD_CASE)
    assert out["ok"] and out["expect"]["ok"] and out["trace"][2]["branch"] == "false"
    assert out["notify"] == "Neplatná výška" and out["tables"] == {}


def test_database_down_is_a_step_error_and_the_trace_stops():
    out = simulate(bmi_graph(), case=DOWN_CASE)
    assert not out["ok"] and out["expect"]["ok"] and out["result"] is None
    assert out["trace"][-1]["nodeId"] == "write" and out["trace"][-1]["error"] == "Služba selhala: DB nedostupná"


def test_expect_diffs_are_czech():
    wrong = {**OK_CASE, "input": {"height": 180, "weight": 90}}
    out = simulate(bmi_graph(), case=wrong)
    assert out["expect"]["ok"] is False
    assert len(out["expect"]["diffs"]) == 2 and out["expect"]["diffs"][0].startswith("Tabulka measurements: čekáno")
    assert "Notifikace: čekáno 'BMI 24.7 uloženo', vyšlo 'BMI 27.8 uloženo'." in out["expect"]["diffs"]
    shorter = simulate(bmi_graph(), case={**OK_CASE, "expect": {"path": ["form"], "result": {"x": 1}}})
    assert [d.split(":")[0] for d in shorter["expect"]["diffs"]] == ["Výsledek", "Cesta"]


def test_validate_false_without_edge_ends_with_validation_error_result():
    graph = bmi_graph()
    graph["edges"] = [e for e in graph["edges"] if e["id"] != "e4"]
    out = simulate(graph, case=BAD_CASE)
    assert not out["ok"] and out["trace"][-1]["error"] == "validace neprošla" and out["trace"][-1]["branch"] == "false"


def test_missing_field_and_zero_division_are_step_errors_not_crashes():
    graph = {"nodes": [node("a", "be.function", rule="$json.nope + 1"), node("b", "be.function", rule="1 / $json.z")],
             "edges": [link("e", "a", "b")]}
    assert simulate(graph, case={"id": "c", "name": "c", "start": "a", "input": {}})["trace"][0]["error"] \
        == "Pole $json.nope v datech chybí."
    out = simulate(graph, case={"id": "c", "name": "c", "start": "b", "input": {"z": 0}})
    assert out["trace"][0]["error"] == "Dělení nulou." and not out["ok"]


def run_one(type_, input_=None, params=None, env=None, **extra):
    graph = {"nodes": [{**node("n", type_, **(params or {})), **extra}], "edges": []}
    out = simulate(graph, case={"id": "c", "name": "c", "start": "n", "input": input_ or {}, "env": env or {}})
    return out, out["trace"][0]


@pytest.mark.parametrize("type_", ["fe.click", "fe.form", "fe.state", "fe.navigate", "be.endpoint", "be.middleware",
                                   "be.auth", "db.transaction", "trigger.manual"])
def test_pass_through_types(type_):
    _, step = run_one(type_, {"a": 1})
    assert step["out"] == {"a": 1} and step["layer"] == type_.split(".")[0].replace("trigger", "neutral")


def test_transform_set_applies_assignments():
    _, step = run_one("transform.set", {"a": 2}, {"assignments": [{"name": "b", "value": "$json.a * 2"},
                                                                  {"name": "c", "value": 7}]})
    assert step["out"] == {"a": 2, "b": 4, "c": 7}
    _, only = run_one("transform.set", {"a": 2}, {"assignments": [{"name": "b", "value": "1"}],
                                                  "includeOtherFields": False})
    assert only["out"] == {"b": 1}


def test_function_without_rule_passes_with_note_and_custom_step_branches():
    _, step = run_one("be.function", {"a": 1})
    assert step["out"] == {"a": 1} and step["note"] == "bez pravidla" and "rule" not in step
    graph = {"nodes": [node("c", "custom.step", title="Třídění", rule="$json.n * 2", branches=["velke", "male"],
                            branchRule="'velke' if $json.n > 5 else 'male'"), node("v", "fe.show"), node("m", "fe.show")],
             "edges": [link("e1", "c", "v", "velke"), link("e2", "c", "m", "male")]}
    out = simulate(graph, case={"id": "c", "name": "c", "start": "c", "input": {"n": 9}})
    assert [s["nodeId"] for s in out["trace"]] == ["c", "v"] and out["trace"][0]["branch"] == "velke"
    assert out["trace"][0]["out"] == {"n": 9, "result": 18}


def test_flow_if_operators_and_combinators():
    def branch(conditions, combinator="and", data=None):
        return run_one("flow.if", data or {"a": 5, "s": "abc"}, {"conditions": conditions, "combinator": combinator})[1]["branch"]
    assert branch([{"left": "$json.a", "operator": "==", "right": 5}, {"left": "$json.s", "operator": "contains",
                                                                          "right": "'b'"}]) == "true"
    assert branch([{"left": "$json.a", "operator": "!=", "right": 5}, {"left": "$json.a", "operator": "<",
                                                                          "right": 9}], "or") == "true"
    assert branch([{"left": "$json.a", "operator": ">", "right": 5}]) == "false"
    assert branch([{"left": "$json.missing", "operator": "exists"}]) == "false"
    assert branch([{"left": "$json.a", "operator": "exists"}]) == "true"
    assert branch([]) == "true"
    assert run_one("flow.if", {}, {"conditions": [{"left": "$json.q", "operator": "=="}]})[1]["error"].startswith("Pole")


def test_db_read_filters_rows_and_tables_are_copies():
    case = {"id": "c", "name": "c", "start": "n", "input": {}, "env": {"tables": {"t": [{"v": 1}, {"v": 5}, {"v": 9}]}}}
    graph = {"nodes": [node("n", "db.read", table="t", where="$json.v > 3")], "edges": []}
    assert simulate(graph, case=case)["trace"][0]["out"] == {"rows": [{"v": 5}, {"v": 9}]}
    assert case["env"]["tables"]["t"] == [{"v": 1}, {"v": 5}, {"v": 9}]
    assert run_one("db.read", {}, {"table": "t"})[1]["out"] == {"rows": []}


def test_db_write_inserts_whole_input_without_columns_and_needs_a_table():
    out, step = run_one("db.write", {"a": 1}, {"table": "t"})
    assert out["tables"] == {"t": [{"a": 1}]} and step["out"] == {"a": 1, "inserted": {"a": 1}}
    assert run_one("db.write", {"a": 1}, {})[1]["error"] == "Zápis nemá tabulku (params.table)."
    assert "chybí sloupce b" in run_one("db.write", {"a": 1}, {"table": "t", "columns": ["a", "b"]})[1]["error"]


def test_infra_answer_error_and_error_output():
    env = {"services": {"n": {"ok": True}}}
    assert run_one("infra.api", {"a": 1}, env=env)[1]["out"] == {"ok": True}
    assert run_one("infra.email", {"a": 1})[1]["note"] == "služba bez odpovědi v env.services"
    failing = {"services": {"n": {"error": "timeout"}}}
    assert run_one("infra.api", env=failing)[1]["error"] == "Služba selhala: timeout"
    graph = {"nodes": [node("n", "infra.api"), node("fine", "fe.notify", message="ok"),
                       node("oops", "fe.notify", message="'chyba: ' + $json.error")],
             "edges": [link("e1", "n", "fine"), link("e2", "n", "oops", "error")]}
    graph["nodes"][0]["onError"] = "errorOutput"
    out = simulate(graph, case={"id": "c", "name": "c", "start": "n", "input": {}, "env": failing})
    assert [s["nodeId"] for s in out["trace"]] == ["n", "oops"] and out["notify"] == "chyba: Služba selhala: timeout"
    graph["nodes"][0]["onError"] = "continue"
    out = simulate(graph, case={"id": "c", "name": "c", "start": "n", "input": {}, "env": failing})
    assert [s["nodeId"] for s in out["trace"]] == ["n", "fine"] and not out["ok"]


def test_show_notify_message_is_expression_or_plain_text():
    assert run_one("fe.notify", {"a": 2}, {"message": "'a=' + text($json.a)"})[1]["note"] == "a=2"
    assert run_one("fe.show", {}, {"message": "Hotovo, díky"})[1]["note"] == "Hotovo, díky"
    assert run_one("fe.notify", {}, {"message": "$json.x"})[1]["error"].startswith("Pole")


@pytest.mark.parametrize("type_", ["flow.merge", "flow.switch", "flow.loop", "flow.wait", "human.approval", "ai.chain",
                                   "mystery.type"])
def test_unsimulated_types_pass_with_note_or_use_example(type_):
    _, step = run_one(type_, {"a": 1})
    assert step["out"] == {"a": 1} and step["note"] == "nesimulováno"
    assert run_one(type_, {"a": 1}, example={"demo": True})[1]["out"] == {"demo": True}


def test_groups_are_ignored_and_loops_stop_at_the_step_limit():
    graph = {"nodes": [node("a", "be.function"), node("b", "be.function")], "edges": [link("1", "a", "b"), link("2", "b", "a")],
             "groups": [{"id": "g", "name": "g", "nodeIds": ["a"]}]}
    out = simulate(graph, case={"id": "c", "name": "c", "start": "a", "input": {}})
    assert len(out["trace"]) == 201 and out["trace"][-1]["error"] == "Překročen limit 200 kroků trasy." and not out["ok"]


def test_input_limits_and_errors_are_flow_invalid():
    graph = bmi_graph([OK_CASE])
    with pytest.raises(FlowInvalid, match="právě jedno"):
        simulate(graph)
    with pytest.raises(FlowInvalid, match="právě jedno"):
        simulate(graph, "ok", OK_CASE)
    with pytest.raises(FlowInvalid, match="nemá případ 'x'"):
        simulate(graph, "x")
    with pytest.raises(FlowInvalid, match="start 'nope' není uzel"):
        simulate(graph, case={**OK_CASE, "start": "nope"})
    many = {"env": {"tables": {f"t{i}": [] for i in range(21)}}}
    with pytest.raises(FlowInvalid, match="nejvýš 20 tabulek po 200"):
        simulate(graph, case={**OK_CASE, **many})
    rows = {"env": {"tables": {"t": [{"a": 1}] * 201}}}
    with pytest.raises(FlowInvalid, match="nejvýš 20 tabulek po 200"):
        simulate(graph, case={**OK_CASE, **rows})
    with pytest.raises(FlowInvalid, match="seznamy objektů"):
        simulate({"nodes": "x"}, "ok")


def test_long_expression_in_a_rule_is_a_step_error():
    out, step = run_one("be.function", {}, {"rule": "1 + " * 200 + "1"})
    assert "delší než 500" in step["error"] and not out["ok"]
