"""Ověření zjištění proti zdrojům (docs/brain-heart.md §3d krok 4) bez sítě mimo localhost."""
import json

from backend.brain_opora.heart import research_verify
from backend.brain_opora.heart.conftest import _Site


def test_verify_findings_checks_urls_once_and_files_inside_the_root(site, tmp_path):
    source = tmp_path / "src"
    (source / "app").mkdir(parents=True)
    lines = [f"radek {number}" for number in range(1, 101)]
    lines[49] = "LIMIT = 100  # požadavků za minutu"
    (source / "app" / "limits.py").write_text("\n".join(lines), encoding="utf-8")
    (tmp_path / "tajne.py").write_text("LIMIT = 100", encoding="utf-8")
    findings = [
        {"id": "f1", "source": f"{site}/doc", "quote": "the INCR command is atomic"},
        {"id": "f2", "source": f"{site}/doc#limits", "quote": "INCR is not atomic"},
        {"id": "f3", "source": f"{site}/short", "quote": "root"},
        {"id": "f4", "source": f"{site}/gone", "quote": "cokoli"},
        {"id": "f5", "source": f"{site}/plain", "quote": "version 5.0 drops Node 16"},
        {"id": "f6", "source": "app/limits.py:45", "quote": "LIMIT = 100"},
        {"id": "f7", "source": "app/limits.py:10", "quote": "LIMIT = 100"},
        {"id": "f8", "source": "app/limits.py", "quote": "LIMIT = 100"},
        {"id": "f9", "source": str(tmp_path / "tajne.py") + ":1", "quote": "LIMIT = 100"},
        {"id": "f10", "source": "../tajne.py:1", "quote": "LIMIT = 100"},
        {"id": "f11", "source": "React docs", "quote": "LIMIT"}]
    cache = tmp_path / "cache"
    facts = research_verify.verify_findings(findings, cache, str(source))
    assert [fact["verified"] for fact in facts] == [
        "verified", "false", "verified", "unreachable", "verified", "verified", "false", "verified",
        "unreachable", "unreachable", "unreachable"]
    # f3: stránka bez textu (JS), ale citace je v jejím zdroji (`<div id=root>`)
    assert facts[0]["id"] == "f1" and facts[0]["source"] == f"{site}/doc"
    assert sorted(_Site.hits) == ["/doc", "/gone", "/plain", "/short"]  # každé URL jednou, kotva se nestahuje
    research_verify.verify_findings(findings[:1], cache, str(source))
    assert _Site.hits.count("/doc") == 1  # podruhé z cache
    assert research_verify.verify_findings(findings[5:6], cache, None)[0]["verified"] == "unreachable"


def test_verify_findings_fetches_at_most_the_url_cap(site, tmp_path, monkeypatch):
    monkeypatch.setattr(research_verify, "VERIFY_MAX_URLS", 2)
    findings = [{"source": f"{site}/doc?{index}", "quote": "the INCR command is atomic"} for index in range(4)]
    facts = research_verify.verify_findings(findings, tmp_path / "cache", None)
    assert [fact["verified"] for fact in facts] == ["verified", "verified", "unreachable", "unreachable"]
    assert len(_Site.hits) == 2


def test_prefetched_file_sources_become_their_original_urls(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps({"files": [{"url": "http://ref.cz/", "file": "00-index.html"}]}),
                                         encoding="utf-8")
    findings = [{"source": str(tmp_path / "00-index.html") + ":12"}, {"source": "src/a.py:3"},
                {"source": "https://b.cz/"}]
    out = research_verify.prefetched_urls(findings, tmp_path)
    assert [item["source"] for item in out] == ["http://ref.cz/", "src/a.py:3", "https://b.cz/"]
    assert research_verify.prefetched_urls(findings, tmp_path / "chybi") == findings


def test_prefetched_target_is_checked_against_the_saved_file_even_when_short(tmp_path):
    (tmp_path / "00-index.html").write_text("<html><body><form novalidate>Jméno je povinné.</form></body></html>",
                                            encoding="utf-8")
    (tmp_path / "index.json").write_text(json.dumps({"files": [{"url": "http://ref.cz/", "file": "00-index.html"}]}),
                                         encoding="utf-8")
    never = lambda *a, **k: (_ for _ in ()).throw(AssertionError("stahovat se nemá"))
    out = research_verify.verify_findings([{"source": "http://ref.cz/", "quote": "Jméno je povinné."}],
                                         tmp_path / "cache", None, never, tmp_path)
    assert out[0]["verified"] == "verified"


def test_rea_observation_makes_a_target_quote_observed_but_not_other_tools_or_urls(tmp_path):
    stream = "\n".join(json.dumps(event) for event in [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "mcp__rea__capture_browser_scenario"},
                                                      {"type": "tool_use", "id": "t2", "name": "WebFetch"}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": 'status: "Formulář má 2 chyby."'}]},
            {"type": "tool_result", "tool_use_id": "t2", "content": "Shrnutí: Vyplň jméno."}]}},
        {"type": "result", "result": "{}", "total_cost_usd": 0.01}])
    observed = research_verify.observed_text(stream)
    assert "Formulář má 2 chyby." in observed and "Shrnutí" not in observed
    (tmp_path / "index.json").write_text(json.dumps({"files": [{"url": "http://ref.cz/", "file": "p.html"}]}), encoding="utf-8")
    (tmp_path / "p.html").write_text("<html><body>Kurz</body></html>", encoding="utf-8")
    findings = [{"source": "http://ref.cz", "quote": "Formulář má 2 chyby."},
                {"source": "http://ref.cz/", "quote": "Vyplň jméno."}]
    out = research_verify.verify_findings(findings, tmp_path / "c", None, None, tmp_path, observed=observed,
                                         observed_urls=["http://ref.cz/"])
    assert [item["verified"] for item in out] == ["observed", "false"]


def test_quote_from_markup_or_inline_script_of_a_saved_target_is_verified(tmp_path):
    (tmp_path / "p.html").write_text('<html><body><form id="f" novalidate></form><script>if (bad.length) bad[0].focus();'
                                     "</script></body></html>", encoding="utf-8")
    (tmp_path / "index.json").write_text(json.dumps({"files": [{"url": "http://ref.cz/", "file": "p.html"}]}), encoding="utf-8")
    findings = [{"source": "http://ref.cz/", "quote": '<form id="f" novalidate>'},
                {"source": "http://ref.cz/", "quote": "if (bad.length) bad[0].focus();"},
                {"source": "http://ref.cz/", "quote": "validate on blur"}]
    out = research_verify.verify_findings(findings, tmp_path / "c", None, None, tmp_path)
    assert [item["verified"] for item in out] == ["verified", "verified", "false"]


def test_youtube_quote_is_checked_against_the_transcript_not_the_page(tmp_path, monkeypatch):
    asked = []

    def transcript(url, cache_dir):
        asked.append(url)
        return {"status": "ok", "text": "so the event loop\npushes the callback onto the stack"} if "8aGh" in url else {
            "status": "unavailable", "reason": "bez titulků"}
    monkeypatch.setattr(research_verify.research_youtube, "transcript", transcript)
    (tmp_path / "p.html").write_text("<html><body>the page says something else</body></html>", encoding="utf-8")
    (tmp_path / "index.json").write_text(json.dumps({"files": [{"url": "https://youtu.be/8aGhZQkoFbQ", "file": "p.html"}]}),
                                         encoding="utf-8")
    never = lambda *a, **k: (_ for _ in ()).throw(AssertionError("video se nestahuje jako stránka"))
    findings = [{"source": "https://youtu.be/8aGhZQkoFbQ", "quote": "the event loop pushes the callback onto the stack"},
                {"source": "https://youtu.be/8aGhZQkoFbQ", "quote": "the page says something else"},
                {"source": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "quote": "elephants"}]
    out = research_verify.verify_findings(findings, tmp_path / "c", None, never, tmp_path,
                                         observed="the page says something else elephants",
                                         observed_urls=["https://youtu.be/8aGhZQkoFbQ",
                                                        "https://www.youtube.com/watch?v=jNQXAC9IVRw"])
    assert [item["verified"] for item in out] == ["verified", "false", "unreachable"]  # stránka v REA video nedokládá
    assert asked == ["https://youtu.be/8aGhZQkoFbQ", "https://www.youtube.com/watch?v=jNQXAC9IVRw"]


def test_observed_text_ignores_string_status_messages_and_retains_rea_results():
    """Live stream-json carries status records whose message is plain text, not a chat message."""
    events = [{"type": "system", "message": "Research provider status"},
              {"type": "system", "message": ["not a message object"]},
              {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "rea1", "name": "mcp__rea__capture"}]}},
              {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "rea1", "content": "Tenant picker is visible."}]}},
              {"type": "result", "message": "Done", "result": "{}"}]
    assert research_verify.observed_text("\n".join(json.dumps(item) for item in events)) == "Tenant picker is visible."
