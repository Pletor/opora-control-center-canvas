"""Stažení a ověření pro výzkum srdce (docs/brain-heart.md §3c, §3d), jen standardní knihovna, bez modelu.

- `prefetch`: cíle výzkumu (`http(s)` stránka a její skripty a styly ze stejného původu) do složky výzkumu.
- `html_text`, `normalize`, `check_quote`: text stránky bez `script`/`style` a kontrola doslovné citace
  (podřetězec, nebo ≥ 80 % pětislovných šindelů; stránka pod 500 znaků textu je `unreachable`).
- `verify_findings`: každé zjištění výzkumníka proti jeho zdroji (URL jednou, ≤ 30 URL, 6 vláken, cache;
  `cesta:řádek` jen uvnitř kořene zdroje, ± 20 řádků). Fakt je jen `verified`.
Supervisor soubor kopíruje do `brain/` vedle `opora_heart.py`.
"""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

# Prefetch (§3c): cíle stáhne nástroj sám a výzkumník je jen čte; strop času, velikosti a počtu souborů.
FETCH_TIMEOUT, FETCH_MAX_BYTES, FETCH_MAX_FILES = 10, 1_000_000, 20
# Ověření (§3d krok 4).
VERIFY_MAX_URLS, VERIFY_THREADS, MIN_TEXT, SHINGLE, SHINGLE_SHARE, LINE_WINDOW = 30, 6, 500, 5, 0.8, 20
SKIPPED_TAGS = {"script", "style"}
QUOTES = str.maketrans({ch: "" for ch in "\"'“”„‟″‘’‚‛′«»`"})
MARKS = re.compile(r"[*_#>~|]+|\[|\]\([^)]*\)|\]")
DASHES = re.compile(r"[‐‑‒–—―]")
PATH_LINE = re.compile(r"(?P<path>.+?)(?::(?P<start>\d+)(?:[-–](?P<end>\d+))?)?\Z")
HTML_HINT = re.compile(rb"<(?:!doctype|html|head|body|div|p|article|main)\b", re.IGNORECASE)


class _Assets(HTMLParser):
    """`<script src>` a `<link rel=stylesheet href>` stránky v pořadí výskytu."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = {key: value or "" for key, value in attrs}
        if tag == "script" and attrs.get("src"):
            self.links.append(attrs["src"])
        elif tag == "link" and "stylesheet" in attrs.get("rel", "").lower().split() and attrs.get("href"):
            self.links.append(attrs["href"])


def _origin(url):
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower()


def _fetch(url, opener):
    """`(status, obsah nebo None, oříznuto)`; čte nejvýš `FETCH_MAX_BYTES` + 1 bajt."""
    try:
        with opener(Request(url, headers={"User-Agent": "opora-research/1"}), timeout=FETCH_TIMEOUT) as reply:
            body = reply.read(FETCH_MAX_BYTES + 1)
            return getattr(reply, "status", 200), body[:FETCH_MAX_BYTES], len(body) > FETCH_MAX_BYTES
    except Exception as error:  # noqa: BLE001 – síť, HTTP chyba nebo časový limit jdou do indexu
        return getattr(error, "code", None) or type(error).__name__, None, False


def _local(target, source_root):
    """Místní cíl se jen vypíše (`ok` / `missing`); mimo kořen zdroje je `outside` a nečte se."""
    root = Path(source_root).resolve() if source_root else None
    path = (Path(target) if Path(target).is_absolute() or not root else root / target).resolve()
    if not root or (path != root and root not in path.parents):
        return {"target": target, "path": "", "status": "outside"}
    return {"target": target, "path": str(path), "status": "ok" if path.exists() else "missing"}


def prefetch(targets, out_dir, source_root=None, opener=None):
    """Deterministické stažení cílů (§3c): HTML každého `http(s)` cíle a jeho skripty a styly ze stejného původu,
    nejvýš `FETCH_MAX_FILES` souborů po `FETCH_MAX_BYTES`; místní cíle jen vypíše. Vrací zapsaný `index.json`."""
    opener, out_dir = opener or urlopen, Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files, local, seen = [], [], set()

    def save(url, page):
        if url in seen or len(files) >= FETCH_MAX_FILES:
            return None
        seen.add(url)
        status, body, truncated = _fetch(url, opener)
        name = ""
        if body is not None:
            base = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(urlsplit(url).path).name)[:60] or "index"
            name = f"{len(files):02d}-{base}" + (".html" if page and not base.endswith((".html", ".htm")) else "")
            (out_dir / name).write_bytes(body)
        files.append({"url": url, "file": name, "status": status, "bytes": len(body or b""),
                      **({"truncated": True} if truncated else {})})
        return body

    for target in targets:
        if urlsplit(target).scheme not in ("http", "https"):
            local.append(_local(target, source_root))
            continue
        body = save(target, True)
        if body is None:
            continue
        parser = _Assets()
        with suppress(Exception):  # rozbité HTML: stačí, co se stihlo najít
            parser.feed(body.decode("utf-8", errors="replace"))
        for link in parser.links:
            url = urljoin(target, link).split("#")[0]
            if _origin(url) == _origin(target):
                save(url, False)
    index = {"files": files, "local": local}
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return index


class _Text(HTMLParser):
    """Viditelný text stránky: vše mimo `script` a `style`, entity už převedené."""

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in SKIPPED_TAGS

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(html):
    """Text HTML bez `script`/`style`, mezery sloučené do jedné."""
    parser = _Text()
    with suppress(Exception):  # rozbité HTML: stačí, co se stihlo přečíst
        parser.feed(html)
        parser.close()
    return " ".join(" ".join(parser.parts).split())


def normalize(text):
    """Pro porovnání citace: malá písmena, bez uvozovek a značek markdownu, pomlčky jako `-`, jedna mezera."""
    text = DASHES.sub("-", (text or "").lower().replace("…", "...").replace(" ", " "))
    return " ".join(MARKS.sub(" ", text.translate(QUOTES)).split())


def _shingles(words):
    return {tuple(words[index:index + SHINGLE]) for index in range(len(words) - SHINGLE + 1)}


def check_quote(quote, text, min_text=MIN_TEXT):
    """`verified` (citace je v textu, nebo ≥ 80 % jejích pětislovných šindelů), `false` (text je, citace ne),
    `unreachable` (zdroj selhal nebo má pod `min_text` znaků textu, např. stránka jen z JavaScriptu)."""
    if text is None or len(text.strip()) < min_text:
        return "unreachable"
    wanted, haystack = normalize(quote), normalize(text)
    if not wanted:
        return "false"
    if wanted in haystack:
        return "verified"
    words = wanted.split()
    if len(words) < SHINGLE:
        return "false"
    mine = _shingles(words)
    share = len(mine & _shingles(haystack.split())) / len(mine)
    return "verified" if share >= SHINGLE_SHARE else "false"


URL_IN = re.compile(r"https?://[^\s)\]>\"'`]+")


def clean_source(source):
    """Zdroj od modelu: když obsahuje URL, jen ta URL (bez „(sekce …)“ a koncové interpunkce); jinak beze změny."""
    match = URL_IN.search(source or "")
    return match.group(0).rstrip(".,;:") if match else (source or "").strip()


def is_url(source):
    parts = urlsplit(source or "")
    return parts.scheme in ("http", "https") and bool(parts.netloc) and not any(ch.isspace() for ch in source)


def _page_text(url, cache_dir, opener):
    """Text stránky (cache v `cache_dir`, klíč = hash URL); None, když stažení selhalo."""
    cached = Path(cache_dir) / (hashlib.sha1(url.encode("utf-8")).hexdigest()[:20] + ".txt")
    if cached.is_file():
        return cached.read_text(encoding="utf-8")
    _, body, _ = _fetch(url, opener)
    if body is None:
        return None
    raw = body.decode("utf-8", errors="replace")
    text = html_text(raw) if HTML_HINT.search(body[:5000]) else " ".join(raw.split())
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


def _file_text(source, source_root):
    """Okno ± `LINE_WINDOW` řádků kolem `cesta:řádek[-řádek]` (bez řádku celý soubor); None mimo kořen zdroje."""
    match = PATH_LINE.match(source.strip())
    if not match or not source_root:
        return None
    root = Path(source_root).resolve()
    path = Path(match["path"])
    path = (path if path.is_absolute() else root / path).resolve()
    if root not in path.parents or not path.is_file() or path.stat().st_size > FETCH_MAX_BYTES:
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if match["start"]:
        start = int(match["start"])
        end = int(match["end"] or start)
        lines = lines[max(start - 1 - LINE_WINDOW, 0):end + LINE_WINDOW]
    return "\n".join(lines)


def verify_findings(findings, cache_dir, source_root, opener=None):
    """Kopie zjištění s polem `verified` (`verified|false|unreachable`); každé URL se stáhne jednou
    (nejvýš `VERIFY_MAX_URLS`, další jsou `unreachable`), soubory jen uvnitř kořene zdroje."""
    opener = opener or urlopen
    urls = list(dict.fromkeys(item.get("source", "").split("#")[0] for item in findings if is_url(item.get("source"))))
    fetched = urls[:VERIFY_MAX_URLS]
    with ThreadPoolExecutor(max_workers=VERIFY_THREADS) as pool:
        texts = dict(zip(fetched, pool.map(lambda url: _page_text(url, cache_dir, opener), fetched), strict=True))
    out = []
    for item in findings:
        source, quote = item.get("source") or "", item.get("quote") or ""
        if is_url(source):
            status = check_quote(quote, texts.get(source.split("#")[0]))
        else:
            status = check_quote(quote, _file_text(source, source_root) if source else None, min_text=1)
        out.append({**item, "verified": status})
    return out
