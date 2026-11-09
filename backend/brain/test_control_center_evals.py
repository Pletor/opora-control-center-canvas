"""Frozen knowledge eval contract and native plugin manifest validation."""
import json
import re
import shutil
import subprocess
import pytest
from backend.brain import seed
import yaml

ROOT=seed.SEED_DIR/"opora-control-center"


def test_knowledge_cases_have_bounded_model_runs_and_valid_graders():
    cases=sorted((ROOT/"evals").glob("*/prompt.md"))
    assert len(cases)==2
    for prompt in cases:
        text=prompt.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        front=text.split("---",2)[1]
        assert "runs: 1" in front and "model: haiku" in front
        assert "max_turns: 4" in front and "timeout_seconds: 180" in front
        assert "OPORA_GATE_TOKEN" in text or "Credentials" in text
        assert "Inspect" in text and "Read" in text
        for path in (prompt.parent/"graders").glob("*.md"):
            grader=path.read_text(encoding="utf-8")
            assert "type: regex" in grader and "match: contains" in grader
            re.compile(yaml.safe_load(grader.split("---",2)[1])["pattern"])


def _accepts(case, command):
    graders=(ROOT/"evals"/case/"graders").glob("*.md")
    patterns=[yaml.safe_load(path.read_text(encoding="utf-8").split("---",2)[1])["pattern"]
              for path in graders]
    return all(re.search(pattern,command) for pattern in patterns)


@pytest.mark.parametrize("executable",["opora_read.py",'"C:/Program Files/opora_read.py"',"'C:/Program Files/opora_read.py'"])
def test_real_yaml_graders_accept_exact_commands_including_quoted_paths(executable):
    prefix=f"python {executable}"
    assert _accepts("knowledge-local-context",f"{prefix} research-context --project ample --workspace feature_login --node login")
    commands=(f"{prefix} knowledge-search --project ample --workspace feature_login --query Login --result-type solution\n"
              f"{prefix} research-card --project ample --workspace feature_login --id source_7 --revision 3 --raw")
    assert _accepts("knowledge-solution-and-pin",commands)


@pytest.mark.parametrize("old,new",[("research-context","research-list"),("--node login","--node tenant"),
                                  ("--workspace feature_login","--workspace feature_login_other"),
                                  ("--project ample","--project ample_other")])
def test_context_graders_reject_wrong_scope_or_command(old,new):
    command="python opora_read.py research-context --project ample --workspace feature_login --node login"
    assert not _accepts("knowledge-local-context",command.replace(old,new))


@pytest.mark.parametrize("old,new",[("knowledge-search","research-list"),("research-card","research-list"),
                                  ("source_7","source_8"),("--revision 3","--revision 30"),
                                  ("feature_login","feature_login_other"),("--query Login","--query LoginOther"),
                                  ("--result-type solution","--result-type research"),("--raw","--raw-other")])
def test_solution_graders_reject_wrong_command_source_revision_or_workspace(old,new):
    commands=("python opora_read.py knowledge-search --project ample --workspace feature_login --query Login --result-type solution\n"
              "python opora_read.py research-card --project ample --workspace feature_login --id source_7 --revision 3 --raw")
    assert not _accepts("knowledge-solution-and-pin",commands.replace(old,new))


def test_native_plugin_validation_accepts_knowledge_suite():
    binary=shutil.which("claude")
    if not binary:
        pytest.skip("Native Claude plugin validator is not installed")
    result=subprocess.run([binary,"plugin","validate",str(ROOT),"--json"],text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)["success"] is True
