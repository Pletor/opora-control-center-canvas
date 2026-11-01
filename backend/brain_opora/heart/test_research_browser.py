"""Prohlížeč výzkumníka: seznam domén (povolené adresy a podvrhy), háček PreToolUse (vstup JSON → projde/blok,
i jako samostatný proces), vzory pro `--allowedUrlPattern`, definice serveru a soubory GATHER."""
import json
import subprocess
import sys

import pytest

from backend.brain_opora.heart import research_browser as rb

ALLOWED = ["https://medium.com/", "https://medium.com/@autor/clanek-123", "https://miro.medium.com/v2/x.png",
           "https://github.com/ChromeDevTools/chrome-devtools-mcp", "https://docs.python.org/3/library/json.html",
           "https://developer.mozilla.org/en-US/docs/Web/API/URL", "https://react.dev/reference/react",
           "https://supabase.com/docs/guides/auth", "https://fastapi.tiangolo.com/tutorial/", "https://pypi.org/p/uv",
           "https://www.npmjs.com/package/chrome-devtools-mcp", "https://stackoverflow.com/questions/1",
           "https://learn.microsoft.com/en-us/windows/", "https://developer.chrome.com/docs/devtools",
           "https://MEDIUM.com/x", "https://medium.com:443/x", "https://vitejs.dev/guide/"]
DENIED = ["http://medium.com/", "http://docs.python.org/3/", "https://medium.com.evil.io/", "https://evilmedium.com/",
          "https://evil.io/medium.com", "https://evil.io/?u=https://medium.com/", "https://medium.com@evil.io/",
          "https://user:pw@medium.com/", "https://medium.com:8443/", "https://medium.com./", "https://medium..com/",
          "https://medium.com\\@evil.io/", "https://medium.com%2eevil.io/", "https://evil.io#@medium.com",
          "https://medium.com /x", "https://med\tium.com/", "https://xn--mdium-bva.com/", "https://médium.com/",
          "https://example.com/", "https://microsoft.com/", "file:///C:/Windows/win.ini", "javascript:alert(1)",
          "data:text/html,hi", "chrome://settings", "//medium.com/", "medium.com", "", None, 42,
          "https://" + "a" * 2050 + ".medium.com/"]


@pytest.mark.parametrize("url", ALLOWED)
def test_allowed_urls(url):
    assert rb.allowed_url(url)


@pytest.mark.parametrize("url", DENIED)
def test_denied_urls_and_spoofs(url):
    assert not rb.allowed_url(url)


def test_domain_list_is_one_place_and_patterns_follow_it():
    assert len(set(rb.ALLOWED_DOMAINS)) == len(rb.ALLOWED_DOMAINS)
    assert all(domain == domain.lower() and "/" not in domain and "*" not in domain for domain in rb.ALLOWED_DOMAINS)
    for domain in ("medium.com", "github.com", "developer.mozilla.org", "python.org", "nodejs.org", "react.dev",
                   "supabase.com", "fastapi.tiangolo.com", "typescriptlang.org", "vitejs.dev", "npmjs.com",
                   "pypi.org", "stackoverflow.com", "learn.microsoft.com", "developer.chrome.com"):
        assert domain in rb.ALLOWED_DOMAINS
    patterns = rb.url_patterns()
    assert len(patterns) == 2 * len(rb.ALLOWED_DOMAINS) and "https://medium.com/*" in patterns
    assert "https://*.medium.com/*" in patterns and all(p.startswith("https://") and ":" not in p[8:] for p in patterns)


def call(tool, **args):
    return {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": rb.PREFIX + tool, "tool_input": args}


@pytest.mark.parametrize("payload", [
    call("new_page", url="https://medium.com/@a/b"), call("navigate_page", pageId=1, url="https://react.dev/learn"),
    call("navigate_page", pageId=1, type="url", url="https://docs.python.org/3/"),
    call("navigate_page", pageId=1, type="reload"), call("list_pages"), call("select_page", pageId=2),
    call("take_snapshot", pageId=1), call("wait_for", pageId=1, text=["Docs"]), call("close_page", pageId=1),
    {"tool_name": "WebFetch", "tool_input": {"url": "https://example.com"}}])
def test_hook_lets_reading_through(payload):
    assert rb.decide(payload) == (True, "")
    assert rb.hook(json.dumps(payload).encode("utf-8")) == (0, "")


@pytest.mark.parametrize("payload", [
    call("new_page", url="https://example.com/"), call("new_page", url="http://medium.com/"), call("new_page"),
    call("navigate_page", pageId=1, url="https://medium.com.evil.io/"), call("navigate_page", pageId=1),
    call("navigate_page", pageId=1, type="back"), call("navigate_page", pageId=1, type="forward"),
    call("navigate_page", pageId=1, url="https://medium.com/", initScript="fetch('https://evil.io')"),
    call("take_snapshot", pageId=1, filePath="C:/x.txt"),
    *(call(name, pageId=1) for name in ("click", "fill", "fill_form", "type_text", "press_key", "evaluate_script",
                                         "upload_file", "handle_dialog", "drag", "emulate", "hover",
                                         "performance_start_trace", "lighthouse_audit", "take_heapsnapshot",
                                         "take_screenshot", "list_network_requests")),
    {"tool_input": {}}, {"tool_name": 7}, [], "x"])
def test_hook_blocks_everything_else(payload):
    allow, reason = rb.decide(payload)
    assert not allow and reason
    code, why = rb.hook(json.dumps(payload).encode("utf-8"))
    assert code == 2 and why == reason


def test_hook_blocks_unreadable_input():
    assert rb.hook(b"{not json")[0] == 2 and rb.hook(b"\xff\xfe")[0] == 2


def test_hook_as_process_reads_stdin_and_exits_2_with_reason():
    script = str(rb.Path(rb.__file__))
    blocked = subprocess.run([sys.executable, "-I", script, "hook"], capture_output=True,
                             input=json.dumps(call("new_page", url="https://evil.io/")).encode("utf-8"))
    assert blocked.returncode == 2 and "evil.io" in blocked.stderr.decode("utf-8")
    passed = subprocess.run([sys.executable, "-I", script, "hook"], capture_output=True,
                            input=json.dumps(call("new_page", url="https://medium.com/")).encode("utf-8"))
    assert passed.returncode == 0 and passed.stderr == b""


def test_enabled_only_by_explicit_env():
    assert not rb.enabled({}) and not rb.enabled({rb.ENV: "0"}) and not rb.enabled({rb.ENV: "maybe"})
    assert rb.enabled({rb.ENV: "1"}) and rb.enabled({rb.ENV: " ON "})


def test_server_is_pinned_autoconnect_read_only_and_restricted():
    server = rb.mcp_server(nt=True)
    assert server["command"] == "cmd" and server["args"][:4] == ["/c", "npx", "-y", "chrome-devtools-mcp@1.12.0"]
    assert "@latest" not in json.dumps(server) and "--autoConnect" in server["args"]
    for flag in ("--categoryInput=false", "--categoryEmulation=false", "--categoryPerformance=false",
                 "--categoryNetwork=false", "--categoryMemory=false", "--javascriptEvaluation=false"):
        assert flag in server["args"]
    assert [a for a in server["args"] if a.startswith("--allowedUrlPattern=")] == [
        f"--allowedUrlPattern={p}" for p in rb.url_patterns()]
    assert rb.mcp_server(nt=False)["command"] == "npx" and rb.mcp_server(nt=False)["args"][0] == "-y"


def test_gather_config_merges_rea_and_hooks_only_browser_tools(tmp_path):
    rea = tmp_path / "rea-mcp.json"
    rea.write_text(json.dumps({"mcpServers": {"rea": {"command": "cmd"}}}), encoding="utf-8")
    mcp, settings = rb.write_gather_config(tmp_path / "run" / "gather", rea, nt=True)
    assert list(json.loads(mcp.read_text(encoding="utf-8"))["mcpServers"]) == ["rea", "chrome-devtools"]
    hooks = json.loads(settings.read_text(encoding="utf-8"))
    assert "disableAllHooks" not in hooks and list(hooks["hooks"]) == ["PreToolUse"]
    (entry,) = hooks["hooks"]["PreToolUse"]
    assert entry["matcher"] == "mcp__chrome-devtools__.*"
    assert entry["hooks"][0]["command"].endswith('research_browser.py" hook')
    alone, _ = rb.write_gather_config(tmp_path / "alone", None)
    assert list(json.loads(alone.read_text(encoding="utf-8"))["mcpServers"]) == ["chrome-devtools"]
