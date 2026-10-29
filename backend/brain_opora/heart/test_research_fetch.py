"""Stažení výzkumu a kontrola citace (docs/brain-heart.md §3c, §3d krok 4) bez modelu: prefetch, text HTML, kontrola
citace a čištění zdroje."""
import json

from backend.brain_opora.heart import research_fetch
from backend.brain_opora.heart.conftest import DOC


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


def test_clean_source_keeps_only_the_url_or_the_path():
    clean = research_fetch.clean_source
    assert clean("https://www.sqlite.org/wal.html (sekce 2.2 Co)") == "https://www.sqlite.org/wal.html"
    assert clean("viz https://a.cz/x.") == "https://a.cz/x"
    assert clean(" src/a.py:12 ") == "src/a.py:12"
