"""Behavioral grading rejects wrong authority/pins and never executes model Python."""
import json

import pytest

from backend.brain import evaluate, operational_eval, seed
from backend.brain.command_argv import commands

ROOT = seed.SEED_DIR / "opora-control-center"
SCRIPT = ROOT / "skills/opora-control-center/scripts/opora_read.py"


def grade(case, text):
    return operational_eval.grade(text, operational_eval.contract(ROOT,"opora-control-center")["cases"][case], SCRIPT)


def test_shell_and_python_literal_argv_have_same_actual_parser_routes():
    shell = 'python "C:/Program Files/opora_read.py" research-context --workspace feature_login --node login --project ample'
    python = 'import subprocess, sys\nsys.exit(subprocess.call([sys.executable, "-I", r"C:\\Program Files\\opora_read.py", "research-context", "--project", "ample", "--workspace", "feature_login", "--node", "login"]))'
    for text in (shell, python):
        [check] = grade("knowledge-local-context", text)
        assert check["route"] == "/api/research/context"
        assert check["arguments"] == {"project":"ample","workspace":"feature_login","scopeNodeId":"login"}
    result = grade("knowledge-solution-and-pin", '```python\nimport subprocess, sys\nsubprocess.call([sys.executable,"opora_read.py","knowledge-search","--project","ample","--workspace","feature_login","--query","login","--result-type","solution"])\n```\n```sh\npython opora_read.py research-card --project ample --workspace feature_login --id source_7 --revision 3 --raw\n```')
    assert [item["capability"] for item in result] == ["solution_identity","canonical_revision"]


def test_harmless_raw_and_explicit_same_scope_match_actual_dispatch():
    assert grade("node-execution-packet","python opora_read.py node-brief --project ample --workspace feature_login --node login --raw")
    text=r'''```python
import subprocess, sys
SCRIPT = r"C:\Program Files\opora_read.py"
subprocess.run([sys.executable, SCRIPT, "knowledge-search", "--project", "ample", "--workspace", "feature_login", "--search-scope", "ample:feature_login", "--result-type", "solution", "--query", "login"], check=False)
```
```python
import subprocess, sys
SCRIPT = "opora_read.py"
subprocess.run([sys.executable, SCRIPT, "research-card", "--project", "ample", "--workspace", "feature_login", "--id", "source_7", "--revision", "3", "--raw"], check=True)
```'''
    assert len(grade("knowledge-solution-and-pin",text))==2
    with pytest.raises(ValueError,match="scope"):
        grade("knowledge-solution-and-pin",text.replace("ample:feature_login","foreign:private"))


@pytest.mark.parametrize("change", ["--node tenant", "--workspace other", "--project foreign", "--search-scope other:space", "--api-base=https://host", "--out=forbidden"])
def test_wrong_scope_and_overrides_fail_closed(change):
    text = "python opora_read.py research-context --project ample --workspace feature_login --node login"
    key = change.split()[0]
    if key in ("--node", "--workspace", "--project"):
        parts = text.split(); offset = parts.index(key); parts[offset:offset+2] = change.split(); text = " ".join(parts)
    else:
        text += " " + change
    with pytest.raises(ValueError):
        grade("knowledge-local-context", text)


def test_generic_node_packet_is_distinct_from_research_and_does_not_change_process_env(monkeypatch):
    monkeypatch.setenv("OPORA_GATE_TOKEN","private-test-value")
    text = "python opora_read.py node-brief --project ample --workspace feature_login --node login"
    assert grade("node-execution-packet",text)[0]["route"] == "/api/desktop-v3/node-brief"
    with pytest.raises(ValueError): grade("knowledge-local-context",text)
    import os
    assert os.environ["OPORA_GATE_TOKEN"] == "private-test-value"


@pytest.mark.parametrize("text", ['import os\nos.system("echo unsafe")', 'import subprocess\nsubprocess.call(make_argv())', 'python opora_read.py research-context --project ample && echo unsafe'])
def test_untrusted_code_is_data_and_never_executed(text):
    with pytest.raises((ValueError,SyntaxError)): commands(text)


def test_contract_missing_malformed_or_missing_capability_rejected(tmp_path):
    with pytest.raises(ValueError): operational_eval.contract(tmp_path,"opora-control-center")
    assert operational_eval.contract(tmp_path,"other") is None
    folder=tmp_path/"evals"; folder.mkdir()
    contract=json.loads((ROOT/"evals/operational-contract.json").read_text())
    for value in ({"schemaVersion":1,"cases":{}}, {"schemaVersion":1,"cases":{"x":[None]}},
                  {**contract,"cases":{key:items for key,items in contract["cases"].items() if key!="node-execution-packet"}}):
        (folder/"operational-contract.json").write_text(json.dumps(value))
        with pytest.raises(ValueError): operational_eval.contract(tmp_path,"opora-control-center")


def test_equal_failing_operational_scores_cannot_activate_and_missing_runs_fail_closed():
    run={"status":"ok","score":0,"baseline_score":0,"report":{"candidate":{"operational":{"passed":False}}}}
    assert not evaluate.passed(run)
    run["score"]=run["baseline_score"]=1
    run["report"]["candidate"]["operational"]["passed"]=True
    assert evaluate.passed(run)
    result=operational_eval.apply({"cases":[],"aggregates":{"overallScore":1}},operational_eval.contract(ROOT,"opora-control-center"),ROOT)
    assert result["operational"]["passed"] is False and result["aggregates"]["overallScore"] == 0


def test_preserved_native_traces_grade_all_four_capabilities_and_reject_wrong_pin(tmp_path):
    specification=operational_eval.contract(ROOT,"opora-control-center")
    messages={"node-execution-packet":"python opora_read.py node-brief --project ample --workspace feature_login --node login",
              "knowledge-local-context":"python opora_read.py research-context --project ample --workspace feature_login --node login",
              "knowledge-solution-and-pin":"python opora_read.py knowledge-search --project ample --workspace feature_login --query login --result-type solution\npython opora_read.py research-card --project ample --workspace feature_login --id source_7 --revision 3 --raw"}
    report={"aggregates":{"overallScore":0},"cases":[]}
    for name,text in messages.items():
        trace=tmp_path/(name+".jsonl")
        trace.write_text(json.dumps({"type":"result","result":text}),encoding="utf-8")
        report["cases"].append({"name":name,"arms":{"with":[{"tracePath":str(trace),"error":None}]}})
    result=operational_eval.apply(report,specification,ROOT)
    assert result["operational"]["passed"] and result["aggregates"]["overallScore"]==1
    assert sum(len(case["capabilities"]) for case in result["operational"]["cases"])==4
    trace.write_text(json.dumps({"type":"result","result":text.replace("--revision 3","--revision 8")}),encoding="utf-8")
    result=operational_eval.apply(report,specification,ROOT)
    assert result["operational"]["passed"] is False
