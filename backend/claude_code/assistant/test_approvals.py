import json

import pytest

from backend.claude_code.assistant import approvals

WRITE = ('python x/opora_write.py /api/node-spec --project p --workspace w '
         """--json '{"node": "n1", "expected_revision": 3, "fields": {"goal": "Cíl", "acceptance": ["a", "b"]}}'""")


def bash(command, **extra):
    return {"subtype": "can_use_tool", "tool_name": "Bash", "input": {"command": command, **extra}}


def test_write_command_is_asked_with_parsed_target():
    kind, parsed = approvals.classify(bash(WRITE))
    assert kind == "ask"
    assert parsed["route"] == "/api/node-spec" and parsed["project"] == "p" and parsed["workspace"] == "w"
    assert parsed["node"] == "n1" and parsed["script"] == "x/opora_write.py"
    assert parsed["payloadSummary"] == 'node: "n1" · expected_revision: 3 · fields: objekt {goal, acceptance}'


@pytest.mark.parametrize("command", [
    'python3 .claude/skills/opora-control-center/scripts/opora_write.py /api/graph --project p --workspace w --json "{}"',
    'python "P:/0. OSVC/repo/.claude/skills/opora-control-center/scripts/opora_write.py" /api/desktop-v3/state '
    "--workspace w --project p --json-file payload.json",
    "python opora_write.py /api/desktop-v3/agent-output --project p --workspace w --json '{\"nodeId\": \"n2\"}'",
])
def test_accepted_shapes(command):
    kind, parsed = approvals.classify(bash(command))
    assert kind == "ask", command
    assert parsed["route"].startswith("/api/")


@pytest.mark.parametrize("command", [
    WRITE + " ; rm -rf .",
    WRITE + " && echo x",
    WRITE + " | tee out",
    WRITE + " > out.txt",
    "python x/opora_write.py /api/node-spec --project p --workspace w --json \"$(cat secret)\"",
    "python x/opora_write.py /api/node-spec --project `whoami` --workspace w --json '{}'",
    "python x/opora_write.py /api/node-spec --project p --workspace w --json '{}'\nrm x",
    "python x/opora_write.py /api/remove --project p --workspace w --json '{}'",
    "python x/opora_write.py /api/graph/../remove --project p --workspace w --json '{}'",
    "python x/opora_write.py /api/graph --project p --json '{}'",
    "python x/opora_write.py /api/graph --project p --workspace w",
    "python x/opora_write.py /api/graph --project p --workspace w --json '{}' --json-file f",
    "python x/opora_write.py /api/graph --project p --workspace w --json '[1]'",
    "python x/opora_write.py /api/graph --project p --workspace w --json '{bad'",
    "python x/opora_write.py /api/graph --project p --workspace w --json '{}' --base-url http://evil:1",
    "python x/opora_write.py /api/graph --project p --project q --workspace w --json '{}'",
    "python x/evil_opora_write.py.sh /api/graph --project p --workspace w --json '{}'",
    "python x/notopora_write.py /api/graph --project p --workspace w --json '{}'",
    "node x/opora_write.py /api/graph --project p --workspace w --json '{}'",
    "echo hi",
])
def test_everything_else_is_denied_without_ui(command):
    assert approvals.classify(bash(command)) == ("auto_deny", approvals.AUTO_DENY_MESSAGE)


def test_other_tools_are_denied_without_ui():
    for tool in ("Edit", "Write", "NotebookEdit", "PowerShell", "WebFetch"):
        request = {"subtype": "can_use_tool", "tool_name": tool, "input": {"command": WRITE}}
        assert approvals.classify(request) == ("auto_deny", approvals.AUTO_DENY_MESSAGE)
    assert approvals.classify(None)[0] == "auto_deny"
    assert approvals.classify({"tool_name": "Bash", "input": "x"})[0] == "auto_deny"


def test_summary_hides_long_texts_and_stays_short():
    long_text = "tajný " * 400
    summary = approvals.payload_summary({"project": "p", "text": long_text, "items": list(range(5)), "ok": True})
    assert "tajný" not in summary and summary == "text: text 2400 zn. · items: seznam 5 pol. · ok: true"
    huge = approvals.payload_summary({f"k{i}": "x" * 50 for i in range(200)})
    assert len(huge) <= approvals.SUMMARY_LIMIT and huge.endswith("…")
    assert approvals.payload_summary({}) == "prázdný payload"


def test_response_shapes():
    original = {"command": WRITE, "description": "Zapíše spec"}
    allow = approvals.response("r1", "allow", original)
    assert allow == {"type": "control_response", "response": {"subtype": "success", "request_id": "r1",
                                                              "response": {"behavior": "allow", "updatedInput": original}}}
    deny = approvals.response("r2", "deny", original, "  Ne, jinak.  ")
    assert deny["response"]["response"] == {"behavior": "deny", "message": "Ne, jinak."}
    assert approvals.response("r3", "deny")["response"]["response"]["message"] == approvals.DENY_MESSAGE
    with pytest.raises(ValueError):
        approvals.response("r4", "maybe")
    json.dumps(allow)


def test_reason_prefers_command_description():
    assert approvals.reason_of(bash(WRITE, description="Zapíše  spec karty")) == "Zapíše spec karty"
    assert approvals.reason_of({"description": "CLI popis"}) == "CLI popis"
    assert approvals.reason_of({}) == "Zápis na plátno přes opora_write.py."


@pytest.mark.parametrize("command", [
    'python "C:/Users/x y/.claude/skills/opora-control-center/scripts/opora_read.py" view --project p',
    "python3 .claude/skills/opora-control-center/scripts/opora_read.py search --query login",
    "python opora_read.py index --project p --workspace main",
    'graphify query "auth flow"',
])
def test_read_commands_pass_without_asking(command):
    assert approvals.classify(bash(command)) == ("auto_allow", None)


@pytest.mark.parametrize("command", [
    'python -c "import os; os.remove(1)" x/opora_read.py',
    "python evil.py opora_read.py",
    "python x/opora_read.py view; rm -rf .",
    "python x/opora_read.py view && del y",
    "python x/opora_read.py $(whoami)",
    "python x/opora_reader.py view",
    "graphify query x | tee out.txt",
    "graphify update .",
])
def test_lookalike_read_commands_are_not_auto_allowed(command):
    assert approvals.classify(bash(command))[0] == "auto_deny"
