"""Routy Pletora přes skutečnou aplikaci s falešným runnerem: tvar odpovědi, jen člověk, 404 a 422."""
import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.heart.process import Outcome
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}


def fake_runner(command, *, cwd, env, stdin_text, timeout, on_line=None):
    reply = {"reply": "Zapsáno.", "actions": [{"type": "vault_note", "text": "Web má dvě stránky."}]}
    result = {"type": "result", "session_id": "s1", "is_error": False, "result": json.dumps(reply, ensure_ascii=False)}
    return Outcome(0, json.dumps(result), "")


def test_message_and_state(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        client.app.state.pletor.runner, client.app.state.pletor.find = fake_runner, lambda: "claude"
        client.app.state.pletor.transport = fake_ollama
        body = {**SCOPE, "text": "Rozhodli jsme: dvě stránky."}
        answer = client.post("/api/pletor/messages", headers=HEADERS, json=body)
        assert answer.status_code == 200
        assert answer.json() == {"reply": "Zapsáno.", "actions": [
            {"type": "vault_note", "text": "Web má dvě stránky.", "ok": True,
             "detail": "Zapsáno do brain/pletor_decisions.jsonl."}]}
        state = client.get("/api/pletor/state", headers=HEADERS, params=SCOPE).json()
        assert [m["role"] for m in state["messages"]] == ["human", "pletor"]
        assert state["heart"]["running"] is False and state["escalations"] == []
        assert state["brain"] == {"brain": "claude", "model": "sonnet", "available": ["qwen3:14b"]}


def test_message_stream_sends_deltas_then_done(tmp_path):
    from backend.pletor.test_service import stream_runner

    answer = '{"reply": "Ahoj, pane.", "actions": [{"type": "vault_note", "text": "Web má dvě stránky."}]}'
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        pletor = client.app.state.pletor
        pletor.runner, pletor.find = stream_runner(answer, [answer[:15], answer[15:]]), lambda: "claude"
        response = client.post("/api/pletor/messages/stream", headers=HEADERS, json={**SCOPE, "text": "Ahoj"})
        assert response.status_code == 200 and response.headers["content-type"] == "application/x-ndjson"
        lines = [json.loads(line) for line in response.text.splitlines()]
        assert {line["type"] for line in lines[:-1]} == {"delta"}
        assert "".join(line["text"] for line in lines[:-1]) == "Ahoj, pane."
        assert lines[-1] == {"type": "done", "reply": "Ahoj, pane.", "actions": [
            {"type": "vault_note", "text": "Web má dvě stránky.", "ok": True,
             "detail": "Zapsáno do brain/pletor_decisions.jsonl."}]}

        def broken(*args, **kwargs):
            raise ValueError("rozbito")

        pletor.runner = broken  # i neočekávaná výjimka tahu končí řádkem done
        lines = client.post("/api/pletor/messages/stream", headers=HEADERS, json={**SCOPE, "text": "x"}).text
        assert [json.loads(line) for line in lines.splitlines()] == [
            {"type": "done", "reply": "Pletor selhal: rozbito", "actions": []}]
        assert client.post("/api/pletor/messages/stream", headers=AGENT, json={**SCOPE, "text": "x"}
                           ).status_code == 403
        assert client.post("/api/pletor/messages/stream", headers=HEADERS, json={**SCOPE, "text": " "}
                           ).status_code == 422


def test_voice_flag_reaches_the_model(tmp_path):
    seen = []

    def runner(command, *, cwd, env, stdin_text, timeout, on_line=None):
        seen.append(stdin_text)
        return fake_runner(command, cwd=cwd, env=env, stdin_text=stdin_text, timeout=timeout)

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        client.app.state.pletor.runner, client.app.state.pletor.find = runner, lambda: "claude"
        assert client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "text": "x", "voice": True}
                           ).status_code == 200
        assert client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "text": "x"}).status_code == 200
        assert "REŽIM: HLAS" in seen[0] and "REŽIM: HLAS" not in seen[1]


def fake_ollama(method, path, body=None, timeout=None):
    return {"models": [{"name": "qwen3:14b"}]}


def test_brain_switch(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        client.app.state.pletor.transport = fake_ollama
        on = client.post("/api/pletor/brain", headers=HEADERS, json={"brain": "ollama"}).json()
        assert on["ok"] is True and on["brain"] == {"brain": "ollama", "model": "qwen3:14b", "available": ["qwen3:14b"]}
        missing = client.post("/api/pletor/brain", headers=HEADERS, json={"brain": "ollama", "model": "nic"}).json()
        assert missing["ok"] is False and missing["brain"]["model"] == "qwen3:14b"
        back = client.post("/api/pletor/brain", headers=HEADERS, json={"brain": "claude"}).json()
        assert back["ok"] is True and back["brain"]["brain"] == "claude"
        assert client.post("/api/pletor/brain", headers=AGENT, json={"brain": "claude"}).status_code == 403
        assert client.post("/api/pletor/brain", headers=HEADERS, json={"brain": "gpt"}).status_code == 422


def test_refusals(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.post("/api/pletor/messages", headers=AGENT, json={**SCOPE, "text": "x"}).status_code == 403
        assert client.get("/api/pletor/state", headers=AGENT, params=SCOPE).status_code == 403
        missing = client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "project": "nikde", "text": "x"})
        assert missing.status_code == 404 and missing.json()["code"] == "project_not_found"
        assert client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "text": "  "}).status_code == 422
        assert client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "text": "x", "via": "y"}
                           ).status_code == 422
        assert client.get("/api/pletor/state", headers=HEADERS, params={"project": "draft"}).status_code == 422


def available(client):
    voices = client.get("/api/pletor/voices", headers=HEADERS).json()["voices"]
    return [voice["id"] for voice in voices if voice["available"]]


def test_voices_and_tts(tmp_path, monkeypatch):
    from backend.pletor import test_tts, test_tts_edge, tts, tts_edge, tts_xtts
    from backend.pletor.elevenlabs import client as eleven
    from backend.pletor.elevenlabs import test_client as fake_eleven

    for name in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(eleven, "ENV_FILE", tmp_path / "bez.env")  # skutečný klíč z .env se do testu nedostane
    eleven.reset()
    monkeypatch.setattr(tts, "_load", lambda path: test_tts.FakeVoice())
    monkeypatch.setattr(tts_xtts, "python", lambda: tmp_path / "bez-prostredi.exe")
    monkeypatch.setattr(tts_xtts, "free_vram_mb", lambda: 400)
    cloud, seen = test_tts_edge.fake_cloud([{"type": "audio", "data": b"ID3mp3"}])
    monkeypatch.setattr(tts_edge, "_communicate", cloud)
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        folder = client.app.state.pletor.folder
        voices = client.get("/api/pletor/voices", headers=HEADERS).json()["voices"]
        assert [voice["engine"] for voice in voices] == ["xtts", "xtts", "elevenlabs", "elevenlabs", "edge", "edge",
                                                         "piper", "piper"]
        assert "uv sync --project tools/xtts_server" in voices[0]["reason"]
        assert [(voice["id"], voice["label"]) for voice in voices[2:4]] == [
            ("elevenlabs:brian", "Brian · hluboký, konejšivý"), ("elevenlabs:bill", "Bill · moudrý, vyrovnaný")]
        assert voices[2]["reason"].startswith("chybí ELEVENLABS")
        # Profesionální vlastní hlas na tarifu free: jen on nedostupný s důvodem, Brian a Bill hrají; kvóta u všech,
        # syntéza vlastním hlasem 503 (nikdy 500), neznámý hlas 404, klíč nikde.
        (tmp_path / "bez.env").write_text(f"ELEVENLABS_API_KEY={fake_eleven.KEY}\nELEVENLABS_VOICE=Pletor_MH\n",
                                          encoding="utf-8")
        eleven.reset()
        urlopen, _ = fake_eleven.fake_api(speak=(403, json.dumps(fake_eleven.DENIED).encode()), refuse=("v-pletor",))
        monkeypatch.setattr(eleven.urllib.request, "urlopen", urlopen)
        paid = client.get("/api/pletor/voices", headers=HEADERS)
        cloud = [voice for voice in paid.json()["voices"] if voice["engine"] == "elevenlabs"]
        assert [(voice["id"], voice["label"], voice["available"]) for voice in cloud] == [
            ("elevenlabs:brian", "Brian · hluboký, konejšivý", True), ("elevenlabs:bill", "Bill · moudrý, vyrovnaný", True),
            ("elevenlabs:custom", "Pletor_MH", False)]
        assert cloud[2]["reason"] == "hlas Pletor_MH vyžaduje tarif Creator"
        assert all(voice["quota"] == {"tier": "free", "character_count": 1600, "character_limit": 10000}
                   for voice in cloud)
        denied = client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj.", "voice": "elevenlabs:voice"})
        assert denied.status_code == 503 and "tarif Creator" in denied.json()["error"]
        brian = client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj.", "voice": "elevenlabs:brian"})
        assert brian.status_code == 200 and brian.headers["content-type"] == "audio/mpeg" and brian.content == b"ID3mp3"
        unknown = client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj.", "voice": "elevenlabs:rachel"})
        assert unknown.status_code == 404
        assert fake_eleven.KEY not in paid.text + denied.text + unknown.text
        (tmp_path / "bez.env").unlink()
        eleven.reset()
        assert available(client) == list(tts_edge.VOICES)  # Edge je nainstalovaný (skupina tts), Piper nestažený
        edge = client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj.", "voice": "edge:cs-CZ-VlastaNeural"})
        assert edge.status_code == 200 and edge.headers["content-type"] == "audio/mpeg" and edge.content == b"ID3mp3"
        assert seen == [("Ahoj.", "cs-CZ-VlastaNeural")]
        monkeypatch.setattr(tts_edge, "_communicate", test_tts_edge.fake_cloud([], ConnectionError("offline"))[0])
        offline = client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj.", "voice": "edge:cs-CZ-VlastaNeural"})
        assert offline.status_code == 503 and "offline" in offline.json()["error"]
        xtts = client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj.", "voice": "xtts:default"})
        assert xtts.status_code == 404 and "tts_fetch xtts" in xtts.json()["hint"]
        missing = client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj."})
        assert missing.status_code == 404 and missing.json()["error"] == "Hlas není stažen."
        test_tts.seed(folder, tts.DEFAULT)
        assert available(client) == [*tts_edge.VOICES, tts.DEFAULT]
        audio = client.post("/api/pletor/tts", headers=HEADERS, json={"text": " Ahoj. "})
        assert audio.status_code == 200 and audio.headers["content-type"] == "audio/wav"
        assert audio.content[:4] == b"RIFF"
        assert client.post("/api/pletor/tts", headers=HEADERS, json={"text": "Ahoj.", "voice": "cs_CZ-kasandra-medium"}
                           ).status_code == 404
        for bad in ({"text": "   "}, {"text": "x" * (tts.TEXT_LIMIT + 1)}, {"text": "a", "extra": 1}):
            assert client.post("/api/pletor/tts", headers=HEADERS, json=bad).status_code == 422
        assert client.post("/api/pletor/tts", headers=AGENT, json={"text": "Ahoj."}).status_code == 403
        assert client.get("/api/pletor/voices", headers=AGENT).status_code == 403


def test_llm_settings_read_only(tmp_path, monkeypatch):
    from backend.pletor import llm_settings

    def broken():
        raise OSError("disk")

    sections = {"claude": broken, "codex": lambda: {"available": True}, "ollama": lambda: {"available": True},
                "cswap": lambda: {"available": False, "installHint": "uv tool install claude-swap"}}
    monkeypatch.setattr(llm_settings, "SECTIONS", sections)
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        answer = client.get("/api/pletor/llm", headers=HEADERS)
        assert answer.status_code == 200
        assert answer.json()["claude"] == {"available": False, "reason": "OSError: disk"}
        assert answer.json()["cswap"]["installHint"] == "uv tool install claude-swap"
        assert client.get("/api/pletor/llm", headers=AGENT).status_code == 403
