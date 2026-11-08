"""Přepis videa YouTube (docs/brain-heart.md §3d) bez sítě: `yt-dlp` je podvržený proces."""
import json
import subprocess
from pathlib import Path

from backend.brain_opora.heart import research_youtube as yt

VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000 align:start position:0%
the<00:00:00.500><c> event</c><00:00:01.000><c> loop</c>

00:00:02.000 --> 00:00:02.010 align:start position:0%
the event loop

00:00:02.010 --> 00:00:04.000 align:start position:0%
the event loop
pushes&nbsp;callbacks to the stack

1
00:00:04,000 --> 00:00:05,000
pushes callbacks to the stack
yes
yes
"""


def test_video_id_normalizes_every_url_form():
    for url in ("https://www.youtube.com/watch?v=8aGhZQkoFbQ", "https://youtube.com/watch?list=PL1&v=8aGhZQkoFbQ&t=30s",
                "https://m.youtube.com/watch?v=8aGhZQkoFbQ", "https://youtu.be/8aGhZQkoFbQ?si=abc",
                "https://www.youtube.com/shorts/8aGhZQkoFbQ"):
        assert yt.video_id(url) == "8aGhZQkoFbQ", url
    for url in ("https://www.youtube.com/watch?v=kratke", "https://www.youtube.com/channel/UC123",
                "https://example.com/watch?v=8aGhZQkoFbQ", "https://youtu.be/8aGhZQkoFbQ--x", "", None):
        assert yt.video_id(url) is None, url


def test_clean_vtt_drops_timings_tags_and_rolling_duplicates():
    # opakování za sebou je rolování titulků, „yes yes“ z jedné cue se taky sloučí (shodné řádky za sebou)
    assert yt.clean_vtt(VTT) == "the event loop\npushes callbacks to the stack\nyes"


def _info(**extra):
    return {"title": "Event loop", "duration": 1612, "language": "en", "subtitles": {},
            "automatic_captions": {"en-orig": [], "en": [], "cs": []}, **extra}


def fake_ytdlp(info, vtt=VTT, calls=None):
    """Podvržený `yt-dlp`: `-J` vrátí informace, jinak zapíše jednu stopu `.vtt` do složky `-P`."""
    def run(argv, **kwargs):
        if calls is not None:
            calls.append(argv)
        if "-J" in argv:
            return subprocess.CompletedProcess(argv, 0, json.dumps(info), "")
        folder = Path(argv[argv.index("-P") + 1])
        (folder / f"x.{argv[argv.index('--sub-langs') + 1]}.vtt").write_text(vtt, encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")
    return run


def test_transcript_uses_the_original_auto_track_and_caches(tmp_path):
    calls = []
    out = yt.transcript("https://youtu.be/8aGhZQkoFbQ", tmp_path, fake_ytdlp(_info(), calls=calls), lambda _: "yt-dlp")
    assert (out["status"], out["title"], out["duration"], out["lang"], out["kind"]) == ("ok", "Event loop", 1612, "en", "auto")
    assert out["text"].startswith("the event loop") and Path(out["file"]).read_text(encoding="utf-8") == out["text"]
    download = calls[1]
    assert download[download.index("--sub-langs") + 1] == "en-orig" and "--write-auto-subs" in download
    assert download[-1] == "https://www.youtube.com/watch?v=8aGhZQkoFbQ"  # kanonická adresa, žádný playlist
    never = lambda *a, **k: (_ for _ in ()).throw(AssertionError("má jít z cache"))
    assert yt.transcript("https://www.youtube.com/shorts/8aGhZQkoFbQ", tmp_path, never, lambda _: "yt-dlp") == out


def test_manual_track_wins_and_translated_auto_track_is_never_used(tmp_path):
    calls = []
    out = yt.transcript("https://youtu.be/8aGhZQkoFbQ", tmp_path / "a",
                        fake_ytdlp(_info(subtitles={"en-US": []}), calls=calls), lambda _: "yt-dlp")
    assert (out["lang"], out["kind"]) == ("en", "manual") and "--write-subs" in calls[1]
    # video v němčině má jen automatické stopy cs/en = strojový překlad: přepis není k dispozici
    german = _info(language="de", automatic_captions={"de-orig": [], "cs": [], "en": []})
    out = yt.transcript("https://youtu.be/8aGhZQkoFbQ", tmp_path / "b", fake_ytdlp(german), lambda _: "yt-dlp")
    assert out["status"] == "unavailable" and "původním jazyce" in out["reason"]


def test_without_ytdlp_timeout_or_error_is_unavailable_and_not_cached(tmp_path):
    url = "https://youtu.be/8aGhZQkoFbQ"
    assert yt.transcript(url, tmp_path, which=lambda _: None) == {"status": "unavailable",
                                                                  "reason": "yt-dlp není nainstalovaný"}
    def slow(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
    assert "nedoběhl" in yt.transcript(url, tmp_path, slow, lambda _: "yt-dlp")["reason"]
    failed = lambda argv, **k: subprocess.CompletedProcess(argv, 1, "", "WARNING: x\nERROR: Video unavailable")
    assert yt.transcript(url, tmp_path, failed, lambda _: "yt-dlp")["reason"].endswith("ERROR: Video unavailable")
    assert yt.transcript(url, tmp_path, fake_ytdlp(_info(), vtt="WEBVTT\n\n"), lambda _: "yt-dlp")["reason"] == (
        "titulky jsou prázdné")
    assert yt.transcript("https://example.com/v", tmp_path)["status"] == "unavailable"
    assert not list(tmp_path.iterdir())
