"""Snímky skenu webu (`docs/navrhy/2026-11-10-platno-2.md`, verze 6): celá stránka v šířce 1440 a výřezy boxů.

REA tu nestačí: `capture_web_screenshot` snímá jen viditelný výřez a PNG vrací modelu, ne do souboru; Pillow ani
klient websocketů v prostředí nejsou. Proto bezhlavý Chrome/Edge (`opora_research.find_browser`) přes DevTools
protokol s nejmenším websocketem ze standardní knihovny; ořez dělá sám prohlížeč (`Page.captureScreenshot` s `clip`)
podle obdélníků prvků, které změří na stránce podle `selector` boxu. Selhání sken neshodí: vrátí `None` a důvod.
"""
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

WIDTH, VIEW_HEIGHT, PAGE_MAX, BOX_MAX, MIN_SIDE = 1440, 900, 12000, 4000, 8
START_TIMEOUT, LOAD_TIMEOUT, CALL_TIMEOUT = 20, 30, 60
PAGE_FILE = "page.png"
# Projede stránku dolů (líně načítané obrázky), vrátí výšku dokumentu a obdélníky prvků v souřadnicích dokumentu.
MEASURE = """(async (selectors, limit) => {
  const height = () => document.documentElement.scrollHeight;
  for (let y = 0; y < Math.min(height(), limit); y += 800) { scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); }
  scrollTo(0, 0); await new Promise(r => setTimeout(r, 400));
  const rects = {};
  for (const [id, selector] of Object.entries(selectors)) {
    let element = null;
    try { element = document.querySelector(selector); } catch (error) { continue; }
    if (element) { const r = element.getBoundingClientRect(); rects[id] = [r.left, r.top, r.width, r.height]; }
  }
  return {height: height(), rects};
})"""

# Překryvné vrstvy pryč, než se měří: fixed/sticky lišta souhlasu s cookies (GDPR, newsletter, modální dialog nebo
# clona přes celé okno) dostane `display:none`, neviditelná nebo mimo okno fixed vrstva (zavřené menu) taky; text se
# čte jen u fixed, sticky prvek v toku (formulář se „souhlasím“) zůstane. Ostatní fixed/sticky
# (hlavička) přejde na `static`, aby ve snímku nezakrývala obsah a zůstala na svém místě v toku. Vrací počty.
OVERLAYS = """(() => {
  const consent = /cookie|consent|gdpr|souhlas|newsletter/i, area = innerWidth * innerHeight;
  let hidden = 0, flowed = 0;
  for (const element of document.querySelectorAll("body *")) {
    const style = getComputedStyle(element);
    if (style.position !== "fixed" && style.position !== "sticky") continue;
    const fixed = style.position === "fixed", r = element.getBoundingClientRect();
    const label = [element.id, element.className?.baseVal ?? element.className, element.getAttribute("aria-label"),
      element.getAttribute("role")].join(" ");
    const text = (element.textContent || "").slice(0, 2000);
    const dialog = /dialog/i.test(element.getAttribute("role") || "") || element.getAttribute("aria-modal") === "true";
    const offscreen = fixed && (r.width < 1 || r.height < 1 || r.bottom <= 0 || r.right <= 0 || r.top >= innerHeight
      || r.left >= innerWidth || style.visibility === "hidden" || Number(style.opacity) === 0);
    if (consent.test(label) || (fixed && consent.test(text)) || (dialog && Number(style.zIndex) >= 100) || offscreen
        || (fixed && r.width * r.height >= area * 0.8)) {
      element.style.setProperty("display", "none", "important"); hidden++;
    } else { element.style.setProperty("position", "static", "important"); flowed++; }
  }
  for (const root of [document.documentElement, document.body]) root.style.setProperty("overflow", "visible", "important");
  return {hidden, flowed};
})()"""


class CaptureError(Exception):
    """Prohlížeč nebo DevTools selhaly; zpráva jde do poznámek návrhu."""


class Socket:
    """Websocket klienta (RFC 6455) jen pro DevTools na loopbacku: textové rámce, maska od klienta."""

    def __init__(self, url, timeout=CALL_TIMEOUT):
        parts = urlsplit(url)
        self.sock = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
        self.buffer = bytearray()
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {parts.netloc}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        while b"\r\n\r\n" not in self.buffer:
            self._fill()
        end = self.buffer.index(b"\r\n\r\n")
        if b" 101 " not in bytes(self.buffer[:end]).split(b"\r\n")[0]:
            raise CaptureError("Prohlížeč odmítl websocket DevTools.")
        del self.buffer[:end + 4]

    def _fill(self):
        chunk = self.sock.recv(1 << 16)
        if not chunk:
            raise CaptureError("Prohlížeč zavřel spojení DevTools.")
        self.buffer += chunk

    def _take(self, size):
        while len(self.buffer) < size:
            self._fill()
        out = bytes(self.buffer[:size])
        del self.buffer[:size]
        return out

    def send(self, text):
        data, mask = text.encode(), os.urandom(4)
        size = len(data)
        length = bytes([0x80 | size]) if size < 126 else (
            bytes([0x80 | 126]) + size.to_bytes(2, "big") if size < 1 << 16 else bytes([0x80 | 127]) + size.to_bytes(8, "big"))
        self.sock.sendall(b"\x81" + length + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(data)))

    def recv(self):
        message = bytearray()
        while True:
            first, second = self._take(2)
            size = second & 0x7F
            if size >= 126:
                size = int.from_bytes(self._take(2 if size == 126 else 8), "big")
            mask = self._take(4) if second & 0x80 else None
            payload = self._take(size)
            if mask:
                payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
            if first & 0x0F == 8:
                raise CaptureError("Prohlížeč zavřel websocket DevTools.")
            if first & 0x0F in (0, 1, 2):
                message += payload
                if first & 0x80:
                    return message.decode("utf-8")

    def close(self):
        self.sock.close()


class Cdp:
    """Volání DevTools: pošle příkaz a počká na odpověď se stejným id; události mezi tím zahodí."""

    def __init__(self, ws):
        self.ws, self.last = ws, 0

    def call(self, method, params=None):
        self.last += 1
        self.ws.send(json.dumps({"id": self.last, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == self.last:
                if "error" in message:
                    raise CaptureError(f"{method}: {message['error'].get('message')}")
                return message.get("result", {})


def _value(cdp, expression, wait=False):
    result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": wait})
    return result.get("result", {}).get("value")


def _shot(cdp, path, x, y, width, height):
    clip = {"x": x, "y": y, "width": width, "height": height, "scale": 1}
    data = cdp.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True, "clip": clip})["data"]
    path.write_bytes(base64.b64decode(data))


def shoot(cdp, url, selectors, folder):
    """Otevře stránku v šířce 1440, uloží `page.png` a `box-<id>.png`; `({page, sections}, poznámky)`."""
    notes = []
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": WIDTH, "height": VIEW_HEIGHT, "deviceScaleFactor": 1,
                                                     "mobile": False})
    cdp.call("Page.navigate", {"url": url})
    deadline = time.monotonic() + LOAD_TIMEOUT
    while _value(cdp, 'location.href === "about:blank" ? "" : document.readyState') != "complete":
        if time.monotonic() > deadline:
            notes.append(f"Snímek: stránka se nenačetla do {LOAD_TIMEOUT} s, snímek je z rozpracovaného stavu.")
            break
        time.sleep(0.5)
    _value(cdp, OVERLAYS)
    measured = _value(cdp, f"{MEASURE}({json.dumps(selectors)}, {PAGE_MAX})", wait=True) or {}
    height = min(int(measured.get("height") or VIEW_HEIGHT), PAGE_MAX)
    if (measured.get("height") or 0) > PAGE_MAX:
        notes.append(f"Snímek celé stránky je oříznutý na výšku {PAGE_MAX} px.")
    _shot(cdp, Path(folder) / PAGE_FILE, 0, 0, WIDTH, height)
    boxes, rects = {}, measured.get("rects") or {}
    for section_id in selectors:
        if section_id not in rects:
            notes.append(f"Výřez boxu {section_id}: selektor na stránce nic nenašel.")
            continue
        x, y, width, high = (max(0, value) for value in rects[section_id])
        width = min(width, WIDTH - x)
        if width < MIN_SIDE or high < MIN_SIDE:
            notes.append(f"Výřez boxu {section_id}: prvek je neviditelný nebo menší než {MIN_SIDE} px.")
            continue
        boxes[section_id] = f"box-{section_id}.png"
        _shot(cdp, Path(folder) / boxes[section_id], x, y, width, min(high, BOX_MAX))
    return {"page": PAGE_FILE, "sections": boxes}, notes


def _port(profile, process):
    """Port DevTools ze souboru `DevToolsActivePort`, který prohlížeč zapíše po startu."""
    deadline, marker = time.monotonic() + START_TIMEOUT, Path(profile) / "DevToolsActivePort"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise CaptureError(f"Prohlížeč skončil hned po startu (exit {process.returncode}).")
        if marker.is_file() and marker.read_text(encoding="utf-8").strip():
            return int(marker.read_text(encoding="utf-8").split()[0])
        time.sleep(0.2)
    raise CaptureError(f"Prohlížeč neotevřel DevTools do {START_TIMEOUT} s.")


def capture(url, selectors, folder, browser=None):
    """`(captures | None, poznámky)`: bez prohlížeče nebo při chybě None a v poznámce proč."""
    from backend.brain_opora.heart import opora_heart, opora_research

    browser = browser or opora_research.find_browser()
    if not browser:
        return None, ["Snímky chybí: na tomto počítači není Chrome ani Edge (OPORA_RESEARCH_BROWSER)."]
    profile, process, ws = tempfile.mkdtemp(prefix="opora-scan-"), None, None
    try:
        process = subprocess.Popen([browser, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={profile}",
                                    "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--mute-audio",
                                    "--disable-extensions", "about:blank"], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **opora_heart._group())
        port = _port(profile, process)
        with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
            targets = json.loads(response.read())
        ws = Socket(next(item["webSocketDebuggerUrl"] for item in targets if item.get("type") == "page"))
        return shoot(Cdp(ws), url, selectors, folder)
    except Exception as error:  # noqa: BLE001 - snímek z cizí stránky nesmí shodit hotový návrh
        return None, [f"Snímky chybí: {type(error).__name__}: {error}"[:300]]
    finally:
        if ws:
            ws.close()
        if process:
            opora_heart.kill_tree(process)
        shutil.rmtree(profile, ignore_errors=True)
