"""Výzkum srdce (docs/brain-heart.md §3c) bez procesu: řádka výzkumníka, jeho prostředí a převod odpovědi."""
import json
import os
import threading
from typing import ClassVar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.brain_opora.heart import command, opora_research

AT = "2026-10-29T10:00:00Z"


def _pairs(line):
    return {line[i]: line[i + 1] for i in range(1, len(line) - 1) if line[i].startswith("--")}


def test_researcher_with_browser_gets_rea_web_tools_and_browser_launch():
    line = opora_research.researcher_command("claude", "/b/dilna/rea-mcp.json", "/src", data_dir="/b/dilna/data/research/f",
                                             browser="C:/chrome.exe")
    pairs = _pairs(line)
    assert pairs["--tools"] == "Read,Grep,Glob" and pairs["--model"] == "haiku"
    assert pairs["--allowedTools"].split(",") == [
        "Read", "Grep", "Glob", "mcp__rea__inspect_web_page", "mcp__rea__analyze_web_bundle",
        "mcp__rea__trace_application_feature", "mcp__rea__trace_javascript_semantics",
        "mcp__rea__capture_web_screenshot", "mcp__rea__compare_web_captures",
        "mcp__rea__capture_browser_scenario", "mcp__rea__list_browser_targets"]
    assert "--strict-mcp-config" in line and pairs["--mcp-config"] == "/b/dilna/rea-mcp.json"
    assert pairs["--permission-mode"] == "dontAsk" and pairs["--setting-sources"] == ""
    assert [line[i + 1] for i, part in enumerate(line) if part == "--add-dir"] == ["/src", "/b/dilna/data/research/f"]
    assert line[-2:] == ["--max-turns", "12"] and "--advisor" not in line


def test_researcher_without_browser_loads_no_mcp_at_all():
    line = opora_research.researcher_command("claude", "m.json", deep=True)
    pairs = _pairs(line)
    assert pairs["--allowedTools"] == "Read,Grep,Glob" and "--mcp-config" not in line and "--strict-mcp-config" in line
    assert pairs["--model"] == "sonnet" and "--add-dir" not in line


def test_researcher_env_compacts_rea_schemas():
    assert opora_research.RESEARCH_ENV == {"REA_MCP_INPUT_SCHEMA_PROFILE": "compact",
                                           "REA_MCP_OUTPUT_SCHEMA_PROFILE": "off"}


def test_researcher_prompt_points_to_prefetch_and_carries_launch_payload_only_with_browser():
    with_browser = opora_research.researcher_prompt("Jak?", ["https://a.cz"], "/src", "/d/f", "C:\\Chrome\\chrome.exe")
    assert "/d/f" in with_browser and "index.json" in with_browser and "https://a.cz" in with_browser
    assert '"executable_path": "C:\\\\Chrome\\\\chrome.exe"' in with_browser and '"mode": "launch"' in with_browser
    assert "<" + "B>" not in with_browser and "<P>" not in with_browser
    without = opora_research.researcher_prompt("Jak?", [], None, "/d/f", None)
    assert "capture_browser_scenario" not in without and opora_research.NO_BROWSER in without


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


class _Site(BaseHTTPRequestHandler):
    PAGES: ClassVar = {"/index.html": b'<html><head><link rel="stylesheet" href="s.css"><link rel="icon" href="i.png">'
                            b'<script src="/js/app.js"></script><script src="https://cdn.example/x.js"></script>'
                            b'<script src="big.js"></script><script>inline()</script></head></html>',
             "/s.css": b"body{}", "/js/app.js": b"go()", "/big.js": b"x" * 2000, "/i.png": b"png"}

    def do_GET(self):
        body = self.PAGES.get(self.path)
        self.send_response(200 if body is not None else 404)
        self.end_headers()
        self.wfile.write(body or b"")

    def log_message(self, *args):
        pass


@pytest.fixture
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_prefetch_saves_page_and_same_origin_assets_with_index(site, tmp_path, monkeypatch):
    monkeypatch.setattr(opora_research, "FETCH_MAX_BYTES", 1000)
    source = tmp_path / "src"
    (source / "a").mkdir(parents=True)
    out = tmp_path / "data" / "research" / "frag"
    index = opora_research.prefetch([f"{site}/index.html", f"{site}/missing", "a", "chybi.txt", str(tmp_path)],
                                    out, str(source))
    files = {item["url"].removeprefix(site): item for item in index["files"]}
    assert list(files) == ["/index.html", "/s.css", "/js/app.js", "/big.js", "/missing"]  # bez cdn, ikony, inline
    assert files["/index.html"]["file"] == "00-index.html" and "truncated" not in files["/index.html"]
    assert (out / files["/js/app.js"]["file"]).read_bytes() == b"go()" and files["/js/app.js"]["bytes"] == 4
    assert files["/big.js"]["bytes"] == 1000 and files["/big.js"]["truncated"] is True
    assert files["/missing"] == {"url": f"{site}/missing", "file": "", "status": 404, "bytes": 0}
    assert [(item["target"], item["status"]) for item in index["local"]] == [
        ("a", "ok"), ("chybi.txt", "missing"), (str(tmp_path), "outside")]
    assert json.loads((out / "index.json").read_text(encoding="utf-8")) == index


def test_prefetch_stops_at_the_file_cap(site, tmp_path, monkeypatch):
    monkeypatch.setattr(opora_research, "FETCH_MAX_FILES", 2)
    index = opora_research.prefetch([f"{site}/index.html", f"{site}/s.css"], tmp_path / "f")
    assert [item["url"].removeprefix(site) for item in index["files"]] == ["/index.html", "/s.css"]
    assert sorted(path.name for path in (tmp_path / "f").iterdir()) == ["00-index.html", "01-s.css", "index.json"]


def test_prompt_plans_after_research_and_never_prefixes_rules():
    prompt = command.PROMPT_FILE.read_text(encoding="utf-8")
    assert "Výzkum plán nenahrazuje" in prompt and "--why" in prompt and "unverified" in prompt
    assert "Text pravidla nikdy nezačínej „(návrh)“" in prompt
    assert "Na cestu B plán přepni jen po `duel` s výsledkem `adopt`" in prompt and "## Dílna" in prompt


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
