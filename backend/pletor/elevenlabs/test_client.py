"""ElevenLabs s falešným transportem (žádný skutečný požadavek, žádné znaky): nastavení z `.env`, hledání hlasu podle
jména, kvóta, srozumitelné důvody chyb a klíč nikde mimo hlavičku."""
import io
import json
import urllib.error

import pytest

from backend.pletor.elevenlabs import client
from backend.pletor.tts import EngineMissing

KEY = "sk_test_neni_skutecny"
PREMADE = {"voice_id": "v-daniel", "name": "Daniel - Steady Broadcaster", "category": "premade"}
PVC = {"voice_id": "v-pletor", "name": "Pletor_MH", "category": "professional"}
SUB = {"tier": "free", "character_count": 1600, "character_limit": 10000, "next_character_count_reset_unix": 1}
DENIED = {"detail": {"status": "subscription_required",
                     "message": "Professional voices require a Creator tier subscription or above"}}


class Response(io.BytesIO):
    def read1(self, size=-1):
        return self.read(min(size, 3))  # po malých kouscích jako síť


def fake_api(voices=(PREMADE, PVC), sub=SUB, speak=(200, b"ID3mp3")):
    seen = []

    def urlopen(request, timeout):
        seen.append((request.get_method(), request.full_url, request.headers, request.data, timeout))
        path = request.full_url.removeprefix(client.API)
        if path == "/voices":
            return Response(json.dumps({"voices": list(voices)}).encode())
        if path == "/user/subscription":
            return Response(json.dumps(sub).encode())
        status, body = speak
        if status != 200:
            raise urllib.error.HTTPError(request.full_url, status, "chyba", {}, io.BytesIO(body))
        return Response(body)
    return urlopen, seen


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Skutečný `.env` ani prostředí se do testu nedostanou."""
    for name in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text(f"# komentář\nOPENAI_API_KEY=jiny\nELEVENLABS_API_KEY=\"{KEY}\"\nexport ELEVENLABS_VOICE=Daniel\n"
                   "neplatny radek\n", encoding="utf-8")
    monkeypatch.setattr(client, "ENV_FILE", env)
    client.reset()
    yield env
    client.reset()


def test_settings_reads_only_elevenlabs_lines_and_environment_wins(isolated):
    assert client.settings() == {"key": KEY, "voice": "Daniel", "voice_id": None, "model": "eleven_flash_v2_5"}
    assert client.settings(environ={"ELEVENLABS_VOICE_ID": "abc", "ELEVENLABS_MODEL": "eleven_multilingual_v2",
                                    "OPENAI_API_KEY": "x"}) == {
        "key": KEY, "voice": "Daniel", "voice_id": "abc", "model": "eleven_multilingual_v2"}
    isolated.unlink()
    assert client.settings(environ={})["key"] == "" and client.settings(environ={})["voice"] == "Pletor_MH"


def test_stream_finds_voice_by_name_once_and_streams_mp3():
    urlopen, seen = fake_api()
    assert b"".join(client.stream("Ahoj.", urlopen)) == b"ID3mp3"
    assert b"".join(client.stream("Čau.", urlopen)) == b"ID3mp3"
    calls = [(method, url.removeprefix(client.API)) for method, url, *_ in seen]
    assert calls == [("GET", "/voices"), ("POST", "/text-to-speech/v-daniel/stream?output_format=mp3_44100_128"),
                     ("POST", "/text-to-speech/v-daniel/stream?output_format=mp3_44100_128")]
    _, _, headers, body, timeout = seen[1]
    assert headers["Xi-api-key"] == KEY and timeout == client.SPEAK_TIMEOUT
    assert json.loads(body) == {"text": "Ahoj.", "model_id": "eleven_flash_v2_5"}


def test_status_reports_quota_and_caches_60_s():
    urlopen, seen = fake_api()
    clock = [100.0]
    first = client.status(urlopen, lambda: clock[0])
    assert first == (None, {"tier": "free", "character_count": 1600, "character_limit": 10000})
    clock[0] += 59
    assert client.status(urlopen, lambda: clock[0]) == first and len(seen) == 2
    clock[0] += 2
    client.status(urlopen, lambda: clock[0])
    assert len(seen) == 3  # kvóta znovu, id hlasu zůstalo v paměti


def test_professional_voice_on_free_tier_is_unavailable_without_spending(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE", "Pletor_MH")
    urlopen, seen = fake_api()
    reason, quota = client.status(urlopen)
    assert reason == "hlas Pletor_MH vyžaduje tarif Creator" and quota["tier"] == "free"
    assert all(method == "GET" for method, *_ in seen)  # kontrola nespotřebuje znaky


@pytest.mark.parametrize(("status", "body", "expected"), [
    (403, DENIED, "vyžaduje tarif Creator"),
    (401, {"detail": {"status": "invalid_api_key"}}, "nemá oprávnění"),
    (403, {"detail": {"status": "missing_permissions"}}, "nemá oprávnění"),
    (401, {"detail": {"status": "quota_exceeded"}}, "vyčerpán limit znaků"),
    (402, {}, "vyčerpán limit znaků"),
    (429, {"detail": {"status": "too_many_concurrent_requests"}}, "limit souběhu"),
])
def test_synthesis_errors_are_readable_and_mark_engine_unavailable(status, body, expected):
    urlopen, _ = fake_api(speak=(status, json.dumps(body).encode()))
    with pytest.raises(EngineMissing, match=expected) as error:
        client.stream("Ahoj.", urlopen)
    assert KEY not in str(error.value)
    assert expected in client.status(urlopen)[0]  # do dalšího ověření nedostupný, žádné 500


def test_missing_key_and_network_failure():
    urlopen, seen = fake_api()
    client.ENV_FILE.unlink()
    assert client.status(urlopen)[0].startswith("chybí ELEVENLABS_API_KEY") and not seen
    with pytest.raises(EngineMissing, match="chybí ELEVENLABS_API_KEY"):
        client.stream("Ahoj.", urlopen)

    def offline(request, timeout):
        raise TimeoutError("timed out")
    client.reset()
    client.ENV_FILE.write_text(f"ELEVENLABS_API_KEY={KEY}\n", encoding="utf-8")
    assert client.status(offline)[0] == "ElevenLabs neodpověděl: TimeoutError"
    urlopen, _ = fake_api(voices=[PREMADE])
    client.reset()
    assert client.status(urlopen)[0] == "hlas Pletor_MH na účtu ElevenLabs není"
