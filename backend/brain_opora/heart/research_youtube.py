"""Přepis videa YouTube jako doložený zdroj výzkumu (docs/brain-heart.md §3d), jen standardní knihovna a `yt-dlp`.

- `video_id`: ID videa z `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/` (jinak None).
- `clean_vtt`: text titulků VTT/SRT bez časových značek, značek a opakovaných řádků.
- `transcript`: přepis přes `yt-dlp` (ruční titulky cs/en, jinak automatické v původním jazyce videa), cache
  v `cache_dir`; vždy slovník, nikdy výjimka: `{"status": "ok", ...}` nebo `{"status": "unavailable", "reason"}`.
Jako skript (`python yt_transcript.py URL`) vypíše přepis nebo `unavailable: důvod`; výzkumný stůl ho kopíruje do
složky výzkumu (cwd výzkumníka), dávka srdce (`command.py`) do `brain/` vedle `opora_heart.py`.
"""
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

YT_TIMEOUT, LANGS, PRINT_MAX = 50, ("cs", "en"), 30_000  # dva běhy yt-dlp pod 2 min Bashe výzkumníka
ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
TIMING = re.compile(r"^\s*(\d+:)?\d+:\d+[.,]\d+\s*-->")
TAG = re.compile(r"<[^>]*>")


def video_id(url):
    """ID videa (11 znaků) nebo None; různé tvary téhož videa dají totéž ID."""
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return None
    host, path = parts.netloc.lower().split(":")[0], parts.path
    if host == "youtu.be":
        found = path.strip("/").split("/")[0]
    elif host in HOSTS and path == "/watch":
        found = (parse_qs(parts.query).get("v") or [""])[0]
    elif host in HOSTS and path.startswith("/shorts/"):
        found = path.split("/")[2]
    else:
        return None
    return found if ID.match(found) else None


def clean_vtt(text):
    """Řádky titulků bez hlavičky, čísel a časů cue, vložených značek (`<00:00:01.000>`, `<c>`) a bez řádku shodného
    s předchozím: automatické titulky opakují každý řádek v další cue (globální odstranění by smazalo skutečná
    opakování)."""
    lines, last = [], None
    for raw in (text or "").splitlines():
        line = " ".join(html.unescape(TAG.sub("", raw)).split())
        if (not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")) or line.isdigit()
                or TIMING.match(raw)):
            continue
        if line != last:
            lines.append(line)
            last = line
    return "\n".join(lines)


def _unavailable(reason):
    return {"status": "unavailable", "reason": reason}


def _pick(info):
    """`(klíč stopy, jazyk, druh)` titulků podle informací o videu, jinak None. Pořadí: ruční v původním jazyce,
    automatické v původním jazyce, ruční cs/en; strojově přeložené automatické stopy nikdy."""
    # OP-FB0522.yt: automatická stopa v jiném jazyce je strojový překlad, citace z ní by nebyla doslovná
    manual, auto = info.get("subtitles") or {}, info.get("automatic_captions") or {}
    original = (info.get("language") or next((key[:-5] for key in auto if key.endswith("-orig")), "")).split("-")[0]

    def track(tracks, lang):
        return next((key for key in tracks if key.split("-")[0] == lang and key != "live_chat"), None)

    candidates = [(manual, original, "manual"), (auto, original, "auto")] if original in LANGS else []
    candidates += [(manual, lang, "manual") for lang in LANGS]
    for tracks, lang, kind in candidates:
        # automatická stopa původního jazyka: `xx-orig` je přepis řeči, holé `xx` může být překlad z jiné varianty
        key = (f"{lang}-orig" if kind == "auto" and f"{lang}-orig" in tracks else track(tracks, lang)) if lang else None
        if key:
            return key, lang, kind
    return None


def _yt(tool, args, run):
    """Jeden běh `yt-dlp` s časovým stropem; výjimky jdou volajícímu (`transcript` je převede na `unavailable`)."""
    return run([tool, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=YT_TIMEOUT)


def _failed(done):
    return _unavailable(f"yt-dlp skončil kódem {done.returncode}: "
                        + ((done.stderr or "").strip().splitlines() or ["bez výstupu"])[-1][:300])


def transcript(url, cache_dir, run=subprocess.run, which=shutil.which):
    """Čistý přepis videa `{status: ok, id, url, title, duration, lang, kind, text, file}` (cache `yt-<id>.json`
    a text `yt-<id>.txt` v `cache_dir`), jinak `{status: unavailable, reason}`; nikdy nevyhodí výjimku.
    Dva běhy `yt-dlp`: informace o videu (`-J`), pak jen vybraná stopa (víc stop najednou YouTube odmítá 429)."""
    vid = video_id(url)
    if not vid:
        return _unavailable("není to odkaz na video YouTube")
    cache = Path(cache_dir)
    cached = cache / f"yt-{vid}.json"
    try:
        return json.loads(cached.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    tool = which("yt-dlp")
    if not tool:
        return _unavailable("yt-dlp není nainstalovaný")
    canonical = f"https://www.youtube.com/watch?v={vid}"  # z ověřeného ID: žádný playlist ani argument navíc
    try:
        done = _yt(tool, ["-J", "--skip-download", "--no-playlist", canonical], run)
        if done.returncode != 0:
            return _failed(done)
        info = json.loads(done.stdout)
        picked = _pick(info)
        if not picked:
            return _unavailable("video nemá ruční titulky ani automatické v původním jazyce (cs/en)")
        key, lang, kind = picked
        with tempfile.TemporaryDirectory() as tmp:
            done = _yt(tool, ["--skip-download", "--no-playlist", "--write-subs" if kind == "manual" else "--write-auto-subs",
                              "--sub-langs", key, "--sub-format", "vtt", "-o", "%(id)s.%(ext)s", "-P", tmp, canonical], run)
            files = sorted(Path(tmp).glob("*.vtt"))
            if not files:
                return _failed(done)
            text = clean_vtt(files[0].read_text(encoding="utf-8", errors="replace"))
    except subprocess.TimeoutExpired:
        return _unavailable(f"yt-dlp nedoběhl do {YT_TIMEOUT} s")
    except (OSError, ValueError, AttributeError) as error:
        return _unavailable(f"{type(error).__name__}: {error}"[:300])
    if not text:
        return _unavailable("titulky jsou prázdné")
    result = {"status": "ok", "id": vid, "url": canonical, "title": info.get("title") or "",
              "duration": info.get("duration"), "lang": lang, "kind": kind, "text": text,
              "file": str(cache / f"yt-{vid}.txt")}
    try:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"yt-{vid}.txt").write_text(text, encoding="utf-8")
        cached.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # bez cache se jen stáhne znovu
    return result


def main(argv):
    """Výpis pro výzkumníka: hlavička a přepis (nejvýš `PRINT_MAX` znaků, celý je v souboru), nebo `unavailable`."""
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 1:
        print("unavailable: použití python yt_transcript.py URL")
        return 2
    result = transcript(argv[0], Path("cache"))
    if result["status"] != "ok":
        print(f"unavailable: {result['reason']}")
        return 1
    print(f"title: {result['title']}\nduration: {result['duration']} s\nsource: {result['url']}\n"
          f"titulky: {result['lang']} ({result['kind']})\nfile: {result['file']}\n")
    print(result["text"][:PRINT_MAX] + ("\n… zkráceno, celý přepis je v `file`" if len(result["text"]) > PRINT_MAX else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
