"""Výzkum srdce (docs/brain-heart.md §3c) bez procesu: řádka výzkumníka, jeho prostředí a převod odpovědi."""
import json

from backend.brain_opora.heart import command, opora_research

AT = "2026-10-29T10:00:00Z"


def test_researcher_command_allows_exactly_read_tools_and_six_rea_web_tools():
    line = opora_research.researcher_command("claude", "/b/dilna/rea-mcp.json", "/src")
    pairs = {line[i]: line[i + 1] for i in range(1, len(line) - 1) if line[i].startswith("--")}
    assert pairs["--tools"] == "Read,Grep,Glob" and pairs["--model"] == "haiku"
    assert pairs["--allowedTools"].split(",") == [
        "Read", "Grep", "Glob", "mcp__rea__inspect_web_page", "mcp__rea__analyze_web_bundle",
        "mcp__rea__trace_application_feature", "mcp__rea__trace_javascript_semantics",
        "mcp__rea__capture_web_screenshot", "mcp__rea__compare_web_captures"]
    assert "--strict-mcp-config" in line and pairs["--mcp-config"] == "/b/dilna/rea-mcp.json"
    assert pairs["--permission-mode"] == "dontAsk" and pairs["--add-dir"] == "/src" and pairs["--setting-sources"] == ""
    assert line[-2:] == ["--max-turns", "20"] and "--advisor" not in line
    deep = opora_research.researcher_command("claude", "m.json", deep=True)
    assert deep[deep.index("--model") + 1] == "sonnet" and "--add-dir" not in deep


def test_researcher_env_has_no_heart_token_address_or_api_keys(monkeypatch):
    for key in ("OPORA_HEART_TOKEN", "OPORA_BASE_URL", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.setenv(key, "x")
    monkeypatch.setenv("OPORA_SOURCE_ROOT", "/src")
    env = opora_research.child_env()
    assert not {"OPORA_HEART_TOKEN", "OPORA_BASE_URL", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY"} & set(env)
    assert env["OPORA_SOURCE_ROOT"] == "/src"


def test_rea_config_is_the_repo_definition_and_lands_in_the_workshop(tmp_path):
    repo = command.HEART_DIR.parents[2] / ".agent-office" / "rea-mcp.json"
    assert command.REA_MCP == json.loads(repo.read_text(encoding="utf-8"))
    command.write_config(tmp_path / "brain")
    written = json.loads((tmp_path / "brain" / "dilna" / "rea-mcp.json").read_text(encoding="utf-8"))
    assert written == command.REA_MCP and list(written["mcpServers"]) == ["rea"]
    assert (tmp_path / "brain" / "opora_research.py").read_bytes() == command.RESEARCH_FILE.read_bytes()


def test_last_top_level_object_wins_over_nested_and_prose():
    text = 'Nejdřív {"x": 1}. Výsledek:\n```json\n{"verdict": "feasible", "evidence": [{"source": "a"}]}\n```'
    assert opora_research.last_object(text) == {"verdict": "feasible", "evidence": [{"source": "a"}]}
    assert opora_research.last_object("bez JSON {nedokončené") is None


def test_url_evidence_is_kept_and_source_paths_go_to_the_approach():
    found = {"verdict": "feasible", "confidence": "high", "approach": "Použij existující Hero.",
             "evidence": [{"source": "https://example.com/a", "quote": "  funguje   tady "},
                          {"source": "src/Hero.tsx:12", "quote": "export function Hero"}, {"source": "x"}, "nic"],
             "alternatives": [{"approach": "Statická stránka", "why": "rychlejší"}, {"why": "bez cesty"}]}
    fields, claimed, alternatives = opora_research.research_fields(found, "", AT)
    assert claimed == "feasible" and fields["verdict"] == "feasible" and fields["confidence"] == "high"
    assert fields["evidence"] == [{"url": "https://example.com/a", "title": "https://example.com/a",
                                   "quote": "funguje tady", "accessedAt": AT}]
    assert "- src/Hero.tsx:12: export function Hero" in fields["approach"] and "- Statická stránka: rychlejší" in fields["approach"]
    assert alternatives == ["Statická stránka"] and fields["status"] == "done"


def test_verdict_without_url_evidence_is_stored_unverified_with_the_claim_in_the_approach():
    found = {"verdict": "dead_end", "confidence": "jistě", "approach": "Nejde.",
             "evidence": [{"source": "src/a.py:3", "quote": "raise"}]}
    fields, claimed, _ = opora_research.research_fields(found, "", AT)
    assert (claimed, fields["verdict"], fields["confidence"], fields["evidence"]) == ("dead_end", "unverified", "", [])
    assert fields["approach"].startswith("Verdikt výzkumníka: dead_end")


def test_parse_failure_is_unverified_with_the_raw_head():
    fields, claimed, alternatives = opora_research.research_fields(None, "Nevím\n  přesně " + "x" * 2000, AT)
    assert (fields["verdict"], claimed, alternatives, fields["evidence"]) == ("unverified", "unverified", [], [])
    assert fields["approach"].startswith("Výzkumník nevrátil platný JSON: Nevím přesně x")
    assert len(fields["approach"]) < 1100
    assert opora_research.research_fields(None, "", AT)[0]["approach"].endswith("(prázdná odpověď)")


def test_outcome_rule_mirrors_the_server():
    assert opora_research.outcome_of(0.8, 3) == "adopt" and opora_research.outcome_of(0.8, 2) == "synthesis"
    assert opora_research.outcome_of(0.4, 5) == "keep" and opora_research.outcome_of(0.5, 5) == "synthesis"
