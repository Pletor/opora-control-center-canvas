"""Stažení a ověření výzkumu (docs/brain-heart.md §3c, §3d krok 4) bez modelu: prefetch, text HTML, kontrola
citace a ověření zjištění proti místnímu serveru a souboru ve zdroji."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from backend.brain_opora.heart import research_fetch

DOC = ("<html><head><title>Doc</title><style>.x{color:red}</style><script>var secret = 'skryto';</script></head>"
       "<body><h1>Rate limiting</h1><p>Redis &amp; Lua: the INCR command is atomic, so a counter per user and "
       "window works across many instances.</p>" + "<p>Výplň dokumentace o limitech a oknech. </p>" * 12
       + "</body></html>").encode("utf-8")


class _Site(BaseHTTPRequestHandler):
    PAGES: ClassVar = {"/index.html": b'<html><head><link rel="stylesheet" href="s.css"><link rel="icon" href="i.png">'
                            b'<script src="/js/app.js"></script><script src="https://cdn.example/x.js"></script>'
                            b'<script src="big.js"></script><script>inline()</script></head></html>',
             "/s.css": b"body{}", "/js/app.js": b"go()", "/big.js": b"x" * 2000, "/i.png": b"png",
             "/doc": DOC, "/short": b"<html><body><div id=root></div></body></html>",
             "/plain": ("Plain text release notes: version 5.0 drops Node 16. " * 12).encode()}
    hits: ClassVar = []

    def do_GET(self):
        self.hits.append(self.path)
        body = self.PAGES.get(self.path.split("?")[0])
        self.send_response(200 if body is not None else 404)
        self.end_headers()
        self.wfile.write(body or b"")

    def log_message(self, *args):
        pass


@pytest.fixture
def site():
    _Site.hits.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_prefetch_saves_page_and_same_origin_assets_with_index(site, tmp_path, monkeypatch):
    monkeypatch.setattr(research_fetch, "FETCH_MAX_BYTES", 1000)
    source = tmp_path / "src"
    (source / "a").mkdir(parents=True)
    out = tmp_path / "data" / "research" / "frag"
    index = research_fetch.prefetch([f"{site}/index.html", f"{site}/missing", "a", "chybi.txt", str(tmp_path)],
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
    monkeypatch.setattr(research_fetch, "FETCH_MAX_FILES", 2)
    index = research_fetch.prefetch([f"{site}/index.html", f"{site}/s.css"], tmp_path / "f")
    assert [item["url"].removeprefix(site) for item in index["files"]] == ["/index.html", "/s.css"]
    assert sorted(path.name for path in (tmp_path / "f").iterdir()) == ["00-index.html", "01-s.css", "index.json"]


def test_html_text_drops_script_and_style_and_collapses_whitespace():
    text = research_fetch.html_text(DOC.decode("utf-8"))
    assert text.startswith("Doc Rate limiting Redis & Lua: the INCR command is atomic")
    assert "skryto" not in text and "color:red" not in text and "  " not in text
    assert research_fetch.html_text("<p>rozbité <b>html") == "rozbité html"


def test_normalize_ignores_case_quotes_markdown_and_dashes():
    assert research_fetch.normalize("**The** `INCR`  command — “atomic”\n") == "the incr command - atomic"
    assert research_fetch.normalize("[docs](https://x.cz) a _b_") == "docs a b"


def test_check_quote_substring_shingles_false_and_unreachable():
    page = research_fetch.html_text(DOC.decode("utf-8"))
    check = research_fetch.check_quote
    assert check("the INCR command is “atomic”", page) == "verified"
    # parafráze s jedním slovem navíc na konci: ≥ 80 % pětislovných šindelů sedí
    quote = "Redis Lua: the INCR command is atomic, so a counter per user and window works everywhere"
    assert check(quote, page) == "verified"
    assert check("the DECR command is never atomic in clusters of any size", page) == "false"
    assert check("krátké", page) == "false" and check("", page) == "false"
    assert check("the INCR command", "<div id=root></div>") == "unreachable"  # stránka jen z JavaScriptu
    assert check("the INCR command", None) == "unreachable"
    assert check("def x", "def x(): pass", min_text=1) == "verified"


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
    facts = research_fetch.verify_findings(findings, cache, str(source))
    assert [fact["verified"] for fact in facts] == [
        "verified", "false", "unreachable", "unreachable", "verified", "verified", "false", "verified",
        "unreachable", "unreachable", "unreachable"]
    assert facts[0]["id"] == "f1" and facts[0]["source"] == f"{site}/doc"
    assert sorted(_Site.hits) == ["/doc", "/gone", "/plain", "/short"]  # každé URL jednou, kotva se nestahuje
    research_fetch.verify_findings(findings[:1], cache, str(source))
    assert _Site.hits.count("/doc") == 1  # podruhé z cache
    assert research_fetch.verify_findings(findings[5:6], cache, None)[0]["verified"] == "unreachable"


def test_verify_findings_fetches_at_most_the_url_cap(site, tmp_path, monkeypatch):
    monkeypatch.setattr(research_fetch, "VERIFY_MAX_URLS", 2)
    findings = [{"source": f"{site}/doc?{index}", "quote": "the INCR command is atomic"} for index in range(4)]
    facts = research_fetch.verify_findings(findings, tmp_path / "cache", None)
    assert [fact["verified"] for fact in facts] == ["verified", "verified", "unreachable", "unreachable"]
    assert len(_Site.hits) == 2


def test_clean_source_keeps_only_the_url_or_the_path():
    clean = research_fetch.clean_source
    assert clean("https://www.sqlite.org/wal.html (sekce 2.2 Co)") == "https://www.sqlite.org/wal.html"
    assert clean("viz https://a.cz/x.") == "https://a.cz/x"
    assert clean(" src/a.py:12 ") == "src/a.py:12"
