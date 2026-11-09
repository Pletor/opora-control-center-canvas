"""Příkaz `research` srdce (docs/brain-heart.md §3d) bez procesu: prohlížeč pro REA, pole schránky z výsledku
stolu, výtah pro srdce, argumenty, prompt a kopie modulů do `brain/`."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.brain.seed import SEED_DIR
from backend.brain_opora.heart import command, opora_heart, opora_research

AT = "2026-10-29T10:00:00Z"
DIGEST = {"verdict": "feasible", "confidence": "high", "next": "plan", "nextWhy": "Fakta stačí.",
          "layers": {"be": {"essence": "Čítač v Redis", "recommended": "INCR + EXPIRE", "options": [], "risks": []}},
          "hypotheses": [{"claim": "Redis unese zátěž", "layer": "be", "check": "test 5k req/s"}],
          "slices": [{"layer": "be", "title": "Middleware limitu", "why": "jádro", "facts": ["f1"]}]}


def fact(fid, source, verified="verified"):
    return {"id": fid, "claim": f"tvrzení {fid}", "layer": "be", "kind": "fact", "source": source,
            "quote": f"citace {fid}", "verified": verified}


def test_browser_detection_env_override_program_files_and_which(tmp_path):
    exe = tmp_path / "chrome.exe"
    exe.write_text("")
    find = opora_research.find_browser
    assert find({"OPORA_RESEARCH_BROWSER": str(exe)}, nt=True) == str(exe)
    assert find({"OPORA_RESEARCH_BROWSER": str(tmp_path / "chybi.exe")}, nt=True) is None
    edge = os.path.join("D:\\PF", "Microsoft", "Edge", "Application", "msedge.exe")
    assert find({"ProgramFiles": "D:\\PF"}, nt=True, exists=lambda path: path == edge) == edge
    assert find({}, nt=True, exists=lambda path: False) is None
    assert find({}, nt=False, which=lambda name: "/usr/bin/chromium" if name == "chromium" else None) == "/usr/bin/chromium"
    assert find({}, nt=False, which=lambda name: None) is None


def test_vault_gets_verified_urls_only_and_the_digest_as_approach():
    facts = [fact("f1", "https://redis.io/a"), fact("f2", "https://redis.io/a"), fact("f3", "https://x.cz", "false"),
             fact("f4", "api/limits.py:3"), *(fact(f"u{index}", f"https://u{index}.cz") for index in range(8))]
    fields, digest = opora_research.vault_fields({"digest": DIGEST, "facts": facts}, AT)
    assert [item["url"] for item in fields["evidence"]] == ["https://redis.io/a", *(f"https://u{i}.cz" for i in range(5))]
    assert fields["evidence"][0] == {"url": "https://redis.io/a", "title": "tvrzení f1", "quote": "citace f1",
                                     "accessedAt": AT}
    assert (fields["verdict"], fields["confidence"], fields["status"]) == ("feasible", "high", "done")
    assert fields["approach"].startswith("Další krok: plan – Fakta stačí.\nVerdikt: feasible/high")
    assert digest == DIGEST


def test_verdict_without_a_verified_url_is_stored_unverified():
    fields, digest = opora_research.vault_fields({"digest": DIGEST, "facts": [fact("f1", "api/limits.py:3")]}, AT)
    assert (fields["verdict"], fields["evidence"], digest["claimed"]) == ("unverified", [], {"verdict": "feasible"})
    assert "syntéza tvrdila feasible" in fields["approach"].splitlines()[1]


def test_summary_prints_next_layers_slices_and_counts():
    stats = {"calls": 4, "costUsd": 0.12, "seconds": 80.5, "claimed": 5, "verified": 3, "skipped": ["gather q6: …"]}
    result = opora_research.summary("frag", {**DIGEST, "claimed": {"next": "plan"}}, stats, "dilna/out/research/frag.json")
    assert (result["verdict"], result["next"], result["nextWhy"], result["facts"]) == ("feasible", "plan", "Fakta stačí.",
                                                                                    "3/5")
    assert result["layers"] == ["be: Čítač v Redis → INCR + EXPIRE"] and result["slices"] == ["Middleware limitu"]
    assert result["hypotheses"] == ["Redis unese zátěž – ověřit: test 5k req/s"]
    assert result["claimed"] == {"next": "plan"} and result["skipped"] == ["gather q6: …"]
    assert result["out"] == "dilna/out/research/frag.json" and result["costUsd"] == 0.12


def test_research_accepts_layers_without_a_mode():
    args = opora_heart.parser().parse_args(["research", "--question", "Q", "--title", "T", "--layer", "db",
                                            "--layer", "cache"])
    assert (args.layer, args.deep, hasattr(args, "mode")) == (["db", "cache"], False, False)
    with pytest.raises(SystemExit):
        opora_heart.parser().parse_args(["research", "--question", "Q", "--title", "T", "--mode", "single"])


def test_prompt_acts_by_next_and_never_prefixes_rules():
    prompt = (SEED_DIR / "opora-heart" / "skills" / "heart" / "SKILL.md").read_text(encoding="utf-8")
    assert "Výzkum plán nenahrazuje" in prompt and "--why" in prompt and "unverified" in prompt
    assert "Text pravidla nikdy nezačínej „(návrh)“" in prompt
    assert "Na cestu B plán přepni jen po `duel` s výsledkem `adopt`" in prompt and "## Dílna" in prompt
    for step in ("`plan` → úkoly z `slices`", "`spike` → jeden malý úkol", "`ask` → `escalate`", "`stop` → `decide`"):
        assert step in prompt
    assert "--layer" in prompt


@pytest.fixture
def rea_mcp_config(tmp_path):
    """The expected provider contract is local to the test, not an untracked developer config."""
    config = tmp_path / ".agent-office" / "rea-mcp.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"mcpServers": {"rea": {"type": "stdio", "command": "cmd",
                                      "args": ["/c", "npx", "-y", "rea-agents@6.7.0", "mcp"]}}}), encoding="utf-8")
    return config


def test_rea_config_and_research_modules_land_in_brain(tmp_path, rea_mcp_config):
    assert command.REA_MCP == json.loads(rea_mcp_config.read_text(encoding="utf-8"))
    command.write_config(tmp_path / "brain", command.HeartSkills("P\n", {}, {}))
    written = json.loads((tmp_path / "brain" / "dilna" / "rea-mcp.json").read_text(encoding="utf-8"))
    assert written == command.REA_MCP and list(written["mcpServers"]) == ["rea"]
    assert set(command.RESEARCH_NAMES) == {"opora_research.py", "opora_research_map.py", "research_alternatives.py", "research_actions.py", "research_desk.py", "research_digest.py",
                                           "research_fetch.py", "research_verify.py", "research_browser.py", "research_youtube.py",
                                           "opora_duel.py", "opora_intent.py", "opora_site.py",
                                           "opora_library.py", "opora_library_nodes.py", "opora_canvas.py"}
    assert all((tmp_path / "brain" / name).is_file() for name in command.RESEARCH_NAMES)
    # kopie v `brain/` se načtou samy, bez balíčku backendu (`python -I`, jen cwd na cestě)
    probe = ("import sys; sys.path.insert(0, '.'); import opora_research, opora_duel, research_desk;"
             "print(research_desk.research_digest.__file__, opora_research.research_fetch.__file__,"
             " research_desk.research_browser.__file__)")
    done = subprocess.run([sys.executable, "-I", "-c", probe], cwd=tmp_path / "brain", capture_output=True, text=True,
                          check=True)
    assert all(Path(path).parent == tmp_path / "brain" for path in done.stdout.split())
