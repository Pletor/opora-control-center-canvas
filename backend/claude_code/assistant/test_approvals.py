import json

import pytest

from backend.canvas.canvas_plan_summary import plan_summary as canvas_plan_summary
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
    'python x/opora_write.py /api/desktop-v3/lease --project p --workspace w --json "{}"',
    'python x/opora_write.py /api/desktop-v3/assignment-snapshot --project p --workspace w --json "{}"',
])
def test_lease_and_snapshot_need_no_prompt(command):
    """Kritika #35: převzetí a snímek nemění obsah karty; heartbeat nesmí zahltit člověka dotazy."""
    assert approvals.classify(bash(command)) == ("auto_allow", None)


def test_state_write_summary_shows_closures_and_rules():
    """Kritika #42: člověk neschvaluje celý stav naslepo."""
    command = ("python x/opora_write.py /api/desktop-v3/state --project p --workspace w --json "
               "'{\"state\": {\"nodes\": {\"a\": {\"done\": {\"confirmed\": true}}}, \"rules\": [{}]}}'")
    kind, parsed = approvals.classify(bash(command))
    assert kind == "ask"
    assert "1 karet · 1 pravidel · uzavřeno 1" in parsed["payloadSummary"]


@pytest.mark.parametrize("command", [
    'python x/opora_write.py /api/canvas-versions --project p --workspace w --json "{}"',
    'python3 .claude/skills/opora-control-center/scripts/opora_write.py /api/graph --project p --workspace w --json "{}"',
    'python "P:/0. OSVC/repo/.claude/skills/opora-control-center/scripts/opora_write.py" /api/desktop-v3/state '
    "--workspace w --project p --json '{\"layers\": []}'",
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
    # Připnuto ke složce skillu (upgrade-opora #42): podstrčený skript jinde neprojde.
    "python opora_read.py index --project p --workspace main",
    "python C:/tmp/opora_read.py view",
    "graphify query x | tee out.txt",
    "graphify update .",
])
def test_lookalike_read_commands_are_not_auto_allowed(command):
    assert approvals.classify(bash(command))[0] == "auto_deny"


# --- koncept zápisu (docs/davka-planu.md §2) ---------------------------------------------
PLAN = {
    "project": "p", "workspace": "w", "digest": "d1", "dryRun": True,
    "plan": {
        "nodes": [
            {"ref": "a", "kind": "area", "name": "Pilot", "text": "Celé zadání " * 50},
            {"ref": "s", "kind": "sector", "parent": "a", "name": "Vlna 2"},
            {"ref": "k1", "parent": "s", "name": "[task] Ingest", "text": "Výňatek",
             "blocks": [{"ref": "f", "ports": [{"ref": "ok"}, {"ref": "ocr"}]}, {"ref": "g"}],
             "rules": [{"kind": "must", "text": "x"}, {"kind": "must_not", "text": "y"}]},
            {"ref": "k2", "parent": "s", "name": "[task] Chunking", "blocks": [{"ref": "h", "ports": [{"ref": "ok"}]}]},
            {"ref": "c", "kind": "comment", "text": "  "},
        ],
        "edges": [{"from": "k1", "to": "k2", "port": "next"},
                  {"from": "k1", "to": "k2", "port": "block", "block": "f", "blockPort": "ok"},
                  {"from": "@n1", "to": "a", "port": "flow"}],
        "decisions": [{"node": "k1", "text": "docling"}],
    },
}


@pytest.fixture
def drafts(tmp_path):
    root = tmp_path / "assistant-drafts"
    (root / "s1").mkdir(parents=True)
    (root / "s2").mkdir()
    return root


def write(path, content='{"plan": {}}'):
    return {"subtype": "can_use_tool", "tool_name": "Write", "input": {"file_path": str(path), "content": content}}


def plan_command(path, route="/api/canvas-plan"):
    slashed = str(path).replace("\\", "/")
    return f'python x/opora_write.py {route} --project p --workspace w --json-file "{slashed}"'


def deny_write(path, drafts_dir, content="{}"):
    return approvals.classify(write(path, content), drafts_dir) == ("auto_deny", approvals.AUTO_DENY_MESSAGE)


def test_plan_summary_counts_what_the_batch_adds():
    assert approvals.plan_summary(PLAN) == (
        "Jen ověření (dryRun), nic nezapíše. Přidá 1 oblast, 1 sektor, 2 karty, 1 komentář, 3 bloky, 3 porty, "
        "3 vazby (next 1, block 1, flow 1), 2 pravidla, 1 rozhodnutí, text u 2 karet.")
    assert approvals.plan_summary({**PLAN, "dryRun": False}).startswith("Přidá 1 oblast")
    assert approvals.plan_summary({"plan": "x"}) == "Dávka nic nepřidá."
    many = {"plan": {"nodes": [{"ref": str(i), "text": "t"} for i in range(23)], "edges": [{"port": "zkratka"}]}}
    assert approvals.plan_summary(many) == "Přidá 23 karet, 1 vazbu (jiný 1), text u 23 karet."
    assert "Celé zadání" not in approvals.plan_summary(PLAN)
    # Vazba bez portu je `next` stejně jako v `/api/canvas-plan`; souhrn počítá `canvas_plan_summary`.
    assert approvals.plan_summary({"plan": {"edges": [{"from": "a", "to": "b"}]}}) == "Přidá 1 vazbu (next 1)."
    assert approvals.plan_summary({**PLAN, "dryRun": False}) == canvas_plan_summary(PLAN["plan"])


def test_write_into_own_drafts_passes_without_asking(drafts):
    own = drafts / "s1"
    assert approvals.classify(write(own / "plan.json"), own) == ("auto_allow", None)
    assert approvals.classify(write(own / "vlna" / "2.json"), own)[0] == "auto_allow"
    assert approvals.classify(write(own / "big.json", "x" * approvals.DRAFT_LIMIT), own)[0] == "auto_allow"


def test_write_anywhere_else_is_denied(drafts, tmp_path):
    own = drafts / "s1"
    assert deny_write(f"{own}/../s2/plan.json", own)  # cizí session přes ..
    assert deny_write(drafts / "s2" / "plan.json", own)  # cizí session přímo
    assert deny_write(f"{own}/../../escape.json", own)
    assert deny_write(f"{own}/sub/../../escape.json", own)
    assert deny_write(tmp_path / "projekt" / "src" / "app.json", own)
    assert deny_write(own / "plan.py", own)
    assert deny_write(own / "plan.json.txt", own)
    assert deny_write(own / ".json", own)
    assert deny_write(own, own)
    assert deny_write(f"{own}/x:y.json", own)  # alternativní datový proud NTFS
    assert deny_write("plan.json", own)  # relativní cesta
    assert deny_write(own / "plan.json", None)  # session bez adresáře konceptů
    assert deny_write(drafts / "s3" / "plan.json", drafts / "s3")  # adresář neexistuje
    assert deny_write(own / "big.json", own, "x" * (approvals.DRAFT_LIMIT + 1))
    assert deny_write(own / "big.json", own, "č" * (approvals.DRAFT_LIMIT // 2 + 1))  # limit je v bajtech UTF-8
    assert approvals.classify({"tool_name": "Write", "input": {"file_path": str(own / "a.json")}}, own)[0] == "auto_deny"
    bad_content = {"tool_name": "Write", "input": {"file_path": str(own / "a.json"), "content": 1}}
    assert approvals.classify(bad_content, own)[0] == "auto_deny"
    # Jiné zapisovací nástroje do konceptů neprojdou.
    for tool in ("Edit", "NotebookEdit", "MultiEdit"):
        request = {"tool_name": tool, "input": {"file_path": str(own / "plan.json"), "content": "{}"}}
        assert approvals.classify(request, own)[0] == "auto_deny"


def test_symlink_out_of_drafts_is_denied(drafts, tmp_path):
    own = drafts / "s1"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "target.json").write_text('{"plan": {}}', encoding="utf-8")
    try:
        (own / "link").symlink_to(outside, target_is_directory=True)
        (own / "file.json").symlink_to(outside / "target.json")
    except OSError:
        pytest.skip("Symlink na tomto systému nejde vytvořit (Windows bez vývojářského režimu).")
    assert deny_write(own / "link" / "plan.json", own)
    assert deny_write(own / "file.json", own)
    assert approvals.classify(bash(plan_command(own / "file.json")), own)[0] == "auto_deny"


def test_junction_out_of_drafts_is_denied(drafts, tmp_path):
    """Na Windows jde odkaz ven i bez práv na symlink: junction adresáře."""
    winapi = pytest.importorskip("_winapi")
    own = drafts / "s1"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "plan.json").write_text('{"plan": {}}', encoding="utf-8")
    winapi.CreateJunction(str(outside), str(own / "jump"))
    assert deny_write(own / "jump" / "plan.json", own)
    assert deny_write(own / "jump" / "new.json", own)
    assert approvals.classify(bash(plan_command(own / "jump" / "plan.json")), own)[0] == "auto_deny"


def test_json_file_from_own_drafts_shows_real_content(drafts):
    own = drafts / "s1"
    path = own / "plan.json"
    path.write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
    kind, parsed = approvals.classify(bash(plan_command(path)), own)
    assert kind == "ask" and parsed["route"] == "/api/canvas-plan"
    assert parsed["payloadSummary"] == approvals.plan_summary(PLAN)
    assert parsed["jsonFile"] == str(path.resolve())
    assert parsed["fileDigest"] == approvals.draft_digest(str(path), own)
    # Jiná cesta než dávka plánu: obecný souhrn klíčů a `node` z obsahu souboru.
    path.write_text('{"nodeId": "n7", "text": "Č"}', encoding="utf-8")
    kind, parsed = approvals.classify(bash(plan_command(path, "/api/node-text")), own)
    assert kind == "ask" and parsed["node"] == "n7" and parsed["payloadSummary"] == 'nodeId: "n7" · text: "Č"'


def test_json_file_outside_drafts_or_unreadable_is_denied(drafts, tmp_path):
    own = drafts / "s1"
    good = json.dumps(PLAN)
    (drafts / "s2" / "plan.json").write_text(good, encoding="utf-8")
    (tmp_path / "plan.json").write_text(good, encoding="utf-8")
    (own / "list.json").write_text("[1, 2]", encoding="utf-8")
    (own / "bad.json").write_text("{nejson", encoding="utf-8")
    (own / "cp1250.json").write_bytes('{"t": "č"}'.encode("cp1250"))
    (own / "big.json").write_bytes(b'{"t": "' + b"x" * approvals.DRAFT_LIMIT + b'"}')
    (own / "plan.txt").write_text(good, encoding="utf-8")
    (own / "dir.json").mkdir()
    denied = [
        drafts / "s2" / "plan.json", f"{own}/../s2/plan.json", tmp_path / "plan.json", f"{own}/../../plan.json",
        own / "list.json", own / "bad.json", own / "cp1250.json", own / "big.json", own / "plan.txt",
        own / "missing.json", own / "dir.json",
    ]
    for path in denied:
        assert approvals.classify(bash(plan_command(path)), own) == ("auto_deny", approvals.AUTO_DENY_MESSAGE), path
    (own / "ok.json").write_text(good, encoding="utf-8")
    assert approvals.classify(bash(plan_command(own / "ok.json")), own)[0] == "ask"
    assert approvals.classify(bash(plan_command(own / "ok.json")), None)[0] == "auto_deny"
    assert approvals.classify(bash(plan_command(own / "ok.json")), drafts / "s2")[0] == "auto_deny"
    assert approvals.classify(bash(plan_command("ok.json")), own)[0] == "auto_deny"  # relativní cesta


def test_canvas_plan_route_is_allowed_like_in_the_script():
    assert "/api/canvas-plan" in approvals.WRITE_ROUTES
    kind, parsed = approvals.classify(bash(
        """python x/opora_write.py /api/canvas-plan --project p --workspace w --json '{"plan": {"nodes": [{"ref": "a"}]}}'"""))
    assert kind == "ask" and parsed["payloadSummary"] == "Přidá 1 kartu."


def test_dry_run_of_own_draft_passes_without_asking(drafts):
    own = drafts / "s1"
    path = own / "plan.json"
    path.write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
    command = plan_command(path) + " --dry-run"
    assert approvals.classify(bash(command), own) == ("auto_allow", None)
    parsed = approvals.parse_write(command, own)
    assert parsed["dryRun"] is True and parsed["payloadSummary"].startswith("Jen ověření (dryRun)")
    # Bez příznaku se dál ptá.
    kind, parsed = approvals.classify(bash(plan_command(path)), own)
    assert kind == "ask" and "dryRun" not in parsed


def test_dry_run_outside_own_drafts_or_wrong_route_or_twice_is_denied(drafts, tmp_path):
    own = drafts / "s1"
    path = own / "plan.json"
    path.write_text(json.dumps(PLAN), encoding="utf-8")
    (drafts / "s2" / "plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    deny = ("auto_deny", approvals.AUTO_DENY_MESSAGE)
    assert approvals.classify(bash(plan_command(drafts / "s2" / "plan.json") + " --dry-run"), own) == deny
    assert approvals.classify(bash(plan_command(path, "/api/graph") + " --dry-run"), own) == deny
    assert approvals.classify(bash(plan_command(path) + " --dry-run --dry-run"), own) == deny
