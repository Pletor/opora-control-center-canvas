"""Ověření zjištění výzkumníka proti zdrojům (docs/brain-heart.md §3d krok 4), jen standardní knihovna, bez modelu.

- `verify_findings`: každé zjištění proti jeho zdroji (URL jednou, ≤ 30 URL, 6 vláken, cache; stažený cíl proti
  uloženému souboru; `cesta:řádek` jen uvnitř kořene zdroje, ± 20 řádků). Fakt je `verified` nebo `observed`.
- `prefetched_urls`: zdroj ukazující na stažený soubor nahradí původní URL.
- Video YouTube se ověří proti přepisu (`research_youtube.transcript`, cache s výzkumníkem); bez přepisu `unreachable`.
- `observed_text`: výstupy nástrojů REA ze `stream-json` výzkumníka (chování stránky v prohlížeči).
Dávka srdce (`command.py`) soubor kopíruje do `brain/` vedle `opora_heart.py`.
"""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from urllib.request import urlopen

try:
    import research_fetch
    import research_youtube
except ImportError:  # v testech moduly balíčku
    from backend.brain_opora.heart import research_fetch, research_youtube

(FETCH_MAX_BYTES, HTML_HINT, PATH_LINE, _fetch, check_quote, html_text, is_url) = (
    getattr(research_fetch, name) for name in ("FETCH_MAX_BYTES", "HTML_HINT", "PATH_LINE", "_fetch", "check_quote",
                                                "html_text", "is_url"))
VERIFY_MAX_URLS, VERIFY_THREADS, LINE_WINDOW = 30, 6, 20
FACT = ("verified", "observed")  # stavy, na kterých smí stát plán
OBSERVED_MAX = 2_000_000
SOURCE_MARK = "\n<<<zdroj stránky>>>\n"  # viditelný text | zdroj stránky (značky a vložené skripty jsou doklad také)


def _texts(raw, html):
    """Viditelný text a za `SOURCE_MARK` zdroj stránky se sraženými mezerami (u ne-HTML jen text)."""
    flat = " ".join(raw.split())
    return html_text(raw) + SOURCE_MARK + flat if html else flat


def _check(quote, page, min_text):
    """Citace proti viditelnému textu (pravidlo `min_text`), jinak proti zdroji stránky."""
    if page is None:
        return check_quote(quote, None)
    visible, _, source = page.partition(SOURCE_MARK)
    status = check_quote(quote, visible, min_text)
    if status == "verified" or not source:
        return status
    in_source = check_quote(quote, source, 1)
    return in_source if in_source == "verified" or min_text <= 1 else status  # stažený cíl: zdroj máme celý


def _page_text(url, cache_dir, opener):
    """Text stránky (cache v `cache_dir`, klíč = hash URL); None, když stažení selhalo."""
    cached = Path(cache_dir) / (hashlib.sha1(url.encode("utf-8")).hexdigest()[:20] + ".txt")
    if cached.is_file():
        return cached.read_text(encoding="utf-8")
    _, body, _ = _fetch(url, opener)
    if body is None:
        return None
    text = _texts(body.decode("utf-8", errors="replace"), bool(HTML_HINT.search(body[:5000])))
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


def _saved_pages(data_dir):
    """`{url: text}` cílů stažených do `data_dir` (`index.json`); bez složky prázdné."""
    try:
        files = json.loads((Path(data_dir) / "index.json").read_text(encoding="utf-8")).get("files") or []
    except (OSError, ValueError, TypeError):
        return {}
    pages = {}
    for item in files:
        with suppress(OSError, KeyError, TypeError):
            if item.get("file"):
                raw = (Path(data_dir) / item["file"]).read_text(encoding="utf-8", errors="replace")
                pages[item["url"]] = _texts(raw, bool(HTML_HINT.search(raw[:5000].encode())))
    return pages


def prefetched_urls(findings, data_dir):
    """Zdroj ukazující na stažený cíl (`data_dir/<soubor>[:řádek]`) nahradí jeho původní URL z `index.json`,
    aby ho ověření stáhlo a schránka vzala jako doklad; ostatní zjištění beze změny."""
    try:
        index = json.loads((Path(data_dir) / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return findings
    base = Path(data_dir).resolve()
    by_file = {(base / item["file"]).resolve(): item["url"] for item in index.get("files") or [] if item.get("file")}
    out = []
    for item in findings:
        match = PATH_LINE.match((item.get("source") or "").strip())
        url = None
        if match and not is_url(item.get("source")):
            with suppress(OSError, ValueError):
                url = by_file.get(Path(match["path"]).resolve())
        out.append({**item, "source": url} if url else item)
    return out


def observed_text(stream):
    """Text výsledků nástrojů REA z `claude -p --output-format stream-json` (co výzkumník v prohlížeči opravdu
    viděl); nejvýš 2 MB. Výsledky ostatních nástrojů ne: WebFetch vrací shrnutí modelu, ne stránku."""
    names, parts, size = {}, [], 0
    for raw in (stream or "").splitlines():
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        message = event.get("message") if isinstance(event, dict) else None
        content = message.get("content") if isinstance(message, dict) else []
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                names[block.get("id")] = block.get("name") or ""
            elif block.get("type") == "tool_result" and names.get(block.get("tool_use_id"), "").startswith("mcp__rea__"):
                body = block.get("content")
                text = body if isinstance(body, str) else " ".join(
                    item.get("text", "") for item in body or [] if isinstance(item, dict))
                parts.append(text)
                size += len(text)
                if size > OBSERVED_MAX:
                    return "\n".join(parts)[:OBSERVED_MAX]
    return "\n".join(parts)


def verify_findings(findings, cache_dir, source_root, opener=None, data_dir=None, observed="", observed_urls=()):
    """Kopie zjištění s polem `verified` (`verified|observed|false|unreachable`; `observed` = citace cíle je ve výstupu
    REA, který výzkumník viděl, ale ne ve statickém textu stránky); každé URL se stáhne jednou
    (nejvýš `VERIFY_MAX_URLS`, další jsou `unreachable`), soubory jen uvnitř kořene zdroje."""
    opener = opener or urlopen
    urls = list(dict.fromkeys(item.get("source", "").split("#")[0] for item in findings if is_url(item.get("source"))))
    fetched = urls[:VERIFY_MAX_URLS]
    seen = {target.rstrip("/") for target in observed_urls}
    saved = _saved_pages(data_dir)  # stažený cíl: ověří se proti tomu, co výzkumník četl (i krátká stránka)
    videos = {url for url in fetched if research_youtube.video_id(url)}

    def text(url):
        # OP-FB0522.yt: video je doklad jen přes přepis, nikdy přes HTML stránky (i když ji prefetch uložil)
        if url in videos:
            return research_youtube.transcript(url, cache_dir).get("text")
        return saved.get(url) or _page_text(url, cache_dir, opener)

    with ThreadPoolExecutor(max_workers=VERIFY_THREADS) as pool:
        texts = dict(zip(fetched, pool.map(text, fetched), strict=True))
    out = []
    for item in findings:
        source, quote = item.get("source") or "", item.get("quote") or ""
        if is_url(source):
            url = source.split("#")[0]
            status = _check(quote, texts.get(url), 1 if url in saved or url in videos else research_fetch.MIN_TEXT)
            if status != "verified" and observed and url not in videos and url.rstrip("/") in seen and check_quote(quote, observed, 1) == "verified":
                status = "observed"  # chování cíle v prohlížeči (REA), ne statický text stránky
        else:
            status = check_quote(quote, _file_text(source, source_root) if source else None, min_text=1)
        out.append({**item, "verified": status})
    return out
