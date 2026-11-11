import base64
import json
import socket
import threading

from backend.brain_opora.heart import opora_research
from backend.project.architecture import page_plan_capture as capture


def test_socket_round_trip_with_large_fragmented_reply():
    """Handshake, maskovaný rámec klienta a odpověď > 64 KiB ve dvou fragmentech (jako PNG v base64)."""
    server = socket.create_server(("127.0.0.1", 0))
    reply = json.dumps({"id": 1, "result": {"data": "x" * 70000}}).encode()
    seen = {}

    def serve():
        peer, _ = server.accept()
        request = b""
        while b"\r\n\r\n" not in request:
            request += peer.recv(1024)
        peer.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
        head = peer.recv(2)
        mask, size = peer.recv(4) if head[1] & 0x80 else b"", head[1] & 0x7F
        data = b""
        while len(data) < size:
            data += peer.recv(size - len(data))
        seen["sent"] = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data)).decode()
        first, second = reply[:10], reply[10:]
        peer.sendall(bytes([0x01, len(first)]) + first + bytes([0x80, 127]) + len(second).to_bytes(8, "big") + second)
        peer.close()

    threading.Thread(target=serve, daemon=True).start()
    ws = capture.Socket(f"ws://127.0.0.1:{server.getsockname()[1]}/devtools/page/1")
    cdp = capture.Cdp(ws)
    assert cdp.call("Page.captureScreenshot")["data"] == "x" * 70000
    assert json.loads(seen["sent"]) == {"id": 1, "method": "Page.captureScreenshot", "params": {}}
    ws.close()
    server.close()


class FakeCdp:
    def __init__(self, height, rects):
        self.height, self.rects, self.clips, self.expressions = height, rects, [], []

    def call(self, method, params=None):
        if method == "Runtime.evaluate":
            self.expressions.append(params["expression"])
            value = {"height": self.height, "rects": self.rects} if params["awaitPromise"] else "complete"
            return {"result": {"value": value}}
        if method == "Page.captureScreenshot":
            self.clips.append(params["clip"])
            return {"data": base64.b64encode(b"png").decode()}
        return {}


def test_shoot_writes_page_and_box_crops(tmp_path):
    cdp = FakeCdp(20000, {"hero": [0, 100, 1500, 6000], "tiny": [0, 0, 2, 2]})
    captures, notes = capture.shoot(cdp, "https://example.com", {"hero": "#hero", "tiny": "i", "nic": ".x"}, tmp_path)
    assert captures == {"page": "page.png", "sections": {"hero": "box-hero.png"}}
    assert cdp.clips[0]["height"] == capture.PAGE_MAX and cdp.clips[1] == {
        "x": 0, "y": 100, "width": capture.WIDTH, "height": capture.BOX_MAX, "scale": 1}
    assert (tmp_path / "box-hero.png").read_bytes() == b"png"
    assert len(notes) == 3  # oříznutá stránka, malý prvek, nenalezený selektor


def test_shoot_hides_overlays_before_measuring(tmp_path):
    """Cookie lišta a fixed hlavička se vyřeší jedním skriptem před měřením obdélníků, ne až po snímku."""
    cdp = FakeCdp(900, {})
    capture.shoot(cdp, "https://example.com", {}, tmp_path)
    overlays = cdp.expressions.index(capture.OVERLAYS)
    measure = next(i for i, expression in enumerate(cdp.expressions) if expression.startswith(capture.MEASURE))
    assert overlays < measure and "display" in capture.OVERLAYS and "static" in capture.OVERLAYS


def test_capture_without_browser_is_none_with_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(opora_research, "find_browser", lambda: None)
    captures, notes = capture.capture("https://example.com", {}, tmp_path)
    assert captures is None and "Chrome" in notes[0]
