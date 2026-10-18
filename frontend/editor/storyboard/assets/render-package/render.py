"""Render storyboardu do videa: Playwright volá seek(t) nad modulem animation.js snímek po snímku, ffmpeg slepí final.mp4.

Modul animation.js exportuje fields, layers a paint(ctx, W, H, state, t, board, visible); index.html z něj skládá window.seek(t).
Stránka běží přes lokální HTTP server (ES moduly se z file:// nenačtou).
Webová scéna (storyboard.json: "animation": "scena"): index.html je dokument scény s runtime; po window.seek(t) se fotí
celý viewport (size, případně --size) místo plátna a podklady dostane jako window.STORYBOARD_ASSETS (data URL).

    python render.py                       # frames/ → final.mp4 (fps a rozměr ze storyboard.json)
    python render.py --stills              # navíc stills/s00.png … jeden snímek za sekundu
    python render.py --only-stills         # jen stilly, bez videa (rychlá kontrola)
    python render.py --fps 30 --size 1080x1920 --out final-9x16.mp4

Síť: stránka smí načítat jen soubory balíčku z vlastního serveru (Playwright route + CSP); jakýkoli jiný požadavek
se zablokuje a render skončí kódem 3 (kód animace nesmí sahat mimo balíček).
"""
from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOARD = ROOT / "storyboard.json"
FRAMES = ROOT / "frames"
STILLS = ROOT / "stills"


def parse_size(value: str | None, board: dict) -> tuple[int, int]:
    if value:
        w, h = value.lower().split("x")
        return int(w), int(h)
    size = board.get("size") or {}
    return int(size.get("w", 1920)), int(size.get("h", 1080))


# Stránka smí načíst jen soubory balíčku: žádný externí skript, obrázek ani spojení (chrání i ruční otevření v prohlížeči).
PAGE_CSP = "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'none'"


class PackageHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Content-Security-Policy", PAGE_CSP)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args) -> None:  # noqa: D102
        return None


def serve_folder() -> http.server.ThreadingHTTPServer:
    """Statický server nad složkou balíčku na volném portu (jen 127.0.0.1)."""
    handler = functools.partial(PackageHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows konzole bývá cp1250; české hlášky nesmí shodit render
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--size", help="např. 1920x1080 nebo 1080x1920")
    parser.add_argument("--out", default="final.mp4")
    parser.add_argument("--stills", action="store_true", help="navíc jeden snímek za sekundu do stills/")
    parser.add_argument("--only-stills", action="store_true", help="jen stilly, bez videa")
    parser.add_argument("--board", default=str(BOARD))
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Chybí Playwright: pip install playwright && python -m playwright install chromium", file=sys.stderr)
        return 2
    if not args.only_stills and not shutil.which("ffmpeg"):
        print("Chybí ffmpeg v PATH.", file=sys.stderr)
        return 2

    board = json.loads(Path(args.board).read_text(encoding="utf-8"))
    missing = [a.get("file") or a.get("id") for a in board.get("assets", []) if not a.get("file") or not (ROOT / a["file"]).is_file()]
    if missing:
        print("Chybí soubory podkladů vedle index.html: " + ", ".join(map(str, missing)) + " (stáhni celý balíček znovu).", file=sys.stderr)
        return 2
    fps = args.fps or int(board.get("fps", 60))
    width, height = parse_size(args.size, board)
    duration = float(board["duration"])
    total = int(round(duration * fps))
    board["size"] = {"w": width, "h": height}
    is_scene = board.get("animation") == "scena"
    scene_assets = {}
    if is_scene:  # scéna podklady nenačítá sama: dostane je jako data URL před prvním seek(t)
        for asset in board.get("assets", []):
            encoded = base64.b64encode((ROOT / asset["file"]).read_bytes()).decode("ascii")
            scene_assets[asset.get("id") or asset["file"]] = f"data:{asset.get('mimeType', 'image/png')};base64,{encoded}"

    FRAMES.mkdir(exist_ok=True)
    for old in FRAMES.glob("*.png"):
        old.unlink()
    want_stills = args.stills or args.only_stills
    if want_stills:
        STILLS.mkdir(exist_ok=True)
        for old in STILLS.glob("*.png"):
            old.unlink()

    started = time.time()
    server = serve_folder()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        blocked: list[str] = []

        def gate(route, request):  # kód animace nesmí na síť: jen přesný origin balíčku (ne jiné porty, ne jiné hosty)
            url = request.url
            if url.startswith(origin + "/") or url.startswith(("data:", "blob:")):
                route.continue_()
            else:
                blocked.append(url)
                route.abort()

        context.route("**/*", gate)
        page = context.new_page()
        page.add_init_script(f"window.STORYBOARD_DATA = {json.dumps(board, ensure_ascii=False)};")
        if is_scene:
            page.add_init_script(f"window.STORYBOARD_ASSETS = {json.dumps(scene_assets)};")
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{origin}/index.html")
        try:
            page.wait_for_function("window.STORYBOARD_READY === true", timeout=15000)
        except Exception:  # noqa: BLE001 - chyba stránky je čitelnější než timeout Playwrightu
            print("Stránka se nepřipravila: " + ("; ".join(errors) or "timeout"), file=sys.stderr)
            browser.close()
            server.shutdown()
            return 2

        def grab(t: float, target: Path) -> None:
            if is_scene:  # scéna je stránka: snímek = viewport po seek(t)
                page.evaluate("(t) => window.seek(t)", t)
                page.screenshot(path=str(target), full_page=False)
                return
            data_url = page.evaluate(
                "(t) => { window.seek(t); return document.getElementById('stage').toDataURL('image/png'); }", t
            )
            target.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))

        if want_stills:
            for sec in range(int(duration) + 1):
                grab(min(sec, duration), STILLS / f"s{sec:02d}.png")
            print(f"stills: {int(duration) + 1} snimku -> {STILLS}")
        if not args.only_stills:
            for i in range(total):
                grab(i / fps, FRAMES / f"f{i:05d}.png")
                if i % fps == 0:
                    print(f"\r{i}/{total} snímků", end="", flush=True)
            print(f"\r{total}/{total} snímků za {time.time() - started:.1f} s")
        browser.close()
    server.shutdown()
    if blocked:
        print("Kód animace sahal mimo balíček (zablokováno, render je neplatný): " + ", ".join(sorted(set(blocked))[:5]), file=sys.stderr)
        return 3

    if args.only_stills:
        return 0

    out = ROOT / args.out
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(FRAMES / "f%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True)
    print(f"hotovo: {out} ({duration:g} s, {fps} fps, {width}x{height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
