"""ElevenLabs s falešným transportem (žádný skutečný požadavek, žádné znaky): nastavení z `.env`, víc hlasů (Brian,
Bill, `custom`), hledání hlasu podle jména, izolace selhání mezi hlasy, kvóta, srozumitelné důvody chyb a klíč nikde
mimo hlavičku."""
import io
import json
import urllib.error

import pytest

from backend.pletor.elevenlabs import client
from backend.pletor.tts import EngineMissing, VoiceMissing

KEY = "sk_test_neni_skutecny"
BRIAN = {"voice_id": "v-brian", "name": "Brian - Deep, Resonant and Comforting", "category": "premade"}
BILL = {"voice_id": "v-bill", "name": "Bill - Wise, Mature, Balanced", "category": "premade"}
PREMADE = {"voice_id": "v-daniel", "name": "Daniel - Steady Broadcaster", "category": "premade"}
PVC = {"voice_id": "v-pletor", "name": "Pletor_MH", "category": "professional"}
SUB = {"tier": "free", "character_count": 1600, "character_limit": 10000, "next_character_count_reset_unix": 1}
DENIED = {"detail": {"status": "subscription_required",
                     "message": "Professional voices require a Creator tier subscription or above"}}
SPEAK = "/text-to-speech/{}/stream?output_format=mp3_44100_128"


class Response(io.BytesIO):
    def read1(self, size=-1):
        return self.read(min(size, 3))  # po malých kouscích jako síť


def fake_api(voices=(BRIAN, BILL, PREMADE, PVC), sub=SUB, speak=(200, b"ID3mp3"), refuse=()):
    """`refuse` = id hlasů, jejichž syntéza vrátí `speak` chybu; ostatní hrají."""
    seen = []

    def urlopen(request, timeout):
        seen.append((request.get_method(), request.full_url, request.headers, request.data, timeout))
        path = request.full_url.removeprefix(client.API)
        if path == "/voices":
            return Response(json.dumps({"voices": list(voices)}).encode())
        if path == "/user/subscription":
            return Response(json.dumps(sub).encode())
        status, body = speak
        if status != 200 and (not refuse or any(f"/{voice_id}/" in path for voice_id in refuse)):
            raise urllib.error.HTTPError(request.full_url, status, "chyba", {}, io.BytesIO(body))
        return Response(b"ID3mp3" if status != 200 else body)
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
    assert client.settings() == {"key": KEY, "voice": "Daniel", "voice_id": None, "custom": True,
                                 "model": "eleven_multilingual_v2"}
    assert client.settings(environ={"ELEVENLABS_VOICE_ID": "abc", "ELEVENLABS_MODEL": "eleven_flash_v2_5",
                                    "OPENAI_API_KEY": "x"}) == {
        "key": KEY, "voice": "Daniel", "voice_id": "abc", "custom": True, "model": "eleven_flash_v2_5"}
    isolated.unlink()
    bare = client.settings(environ={})
    assert bare["key"] == "" and bare["voice"] == "Pletor_MH" and bare["custom"] is False
    assert client.settings(environ={"ELEVENLABS_VOICE_ID": "abc"})["custom"] is True


def test_voices_custom_only_from_env_and_legacy_choice(isolated):
    assert {key: label for key, (_, label) in client.voices().items()} == {
        "brian": "Brian · hluboký, konejšivý", "bill": "Bill · moudrý, vyrovnaný", "custom": "Daniel"}
    assert client.key("elevenlabs:voice") == "custom" and client.key("elevenlabs:bill") == "bill"
    isolated.write_text(f"ELEVENLABS_API_KEY={KEY}\n", encoding="utf-8")
    assert list(client.voices()) == ["brian", "bill"]
    assert client.key("elevenlabs:voice") == "brian"  # stará uložená volba bez vlastního hlasu
    for unknown in ("elevenlabs:custom", "elevenlabs:rachel"):
        with pytest.raises(VoiceMissing, match="nezná"):
            client.key(unknown)
    with pytest.raises(VoiceMissing):
        client.stream("Ahoj.", "elevenlabs:rachel", fake_api()[0])


def test_stream_picks_voice_by_key_finds_name_before_dash_once_and_streams_mp3():
    urlopen, seen = fake_api()
    assert b"".join(client.stream("Ahoj.", "elevenlabs:brian", urlopen)) == b"ID3mp3"
    assert b"".join(client.stream("Čau.", "elevenlabs:brian", urlopen)) == b"ID3mp3"
    assert b"".join(client.stream("Nazdar.", "elevenlabs:bill", urlopen)) == b"ID3mp3"
    assert b"".join(client.stream("Ahoj.", "elevenlabs:voice", urlopen)) == b"ID3mp3"  # stará volba → custom
    calls = [(method, url.removeprefix(client.API)) for method, url, *_ in seen]
    assert calls == [("GET", "/voices"), ("POST", SPEAK.format("v-brian")), ("POST", SPEAK.format("v-brian")),
                     ("GET", "/voices"), ("POST", SPEAK.format("v-bill")),
                     ("GET", "/voices"), ("POST", SPEAK.format("v-daniel"))]
    _, _, headers, body, timeout = seen[1]
    assert headers["Xi-api-key"] == KEY and timeout == client.SPEAK_TIMEOUT
    assert json.loads(body) == {"text": "Ahoj.", "model_id": "eleven_multilingual_v2"}


def test_status_reports_quota_and_caches_60_s():
    urlopen, seen = fake_api()
    clock = [100.0]
    first = client.status("brian", urlopen, lambda: clock[0])
    assert first == (None, {"tier": "free", "character_count": 1600, "character_limit": 10000})
    assert client.status("bill", urlopen, lambda: clock[0]) == first
    assert len(seen) == 3  # kvóta jednou za účet, seznam hlasů za každý hlas
    clock[0] += 59
    assert client.status("brian", urlopen, lambda: clock[0]) == first and len(seen) == 3
    clock[0] += 2
    client.status("brian", urlopen, lambda: clock[0])
    assert len(seen) == 4  # kvóta znovu, id hlasu zůstalo v paměti


def test_professional_custom_voice_on_free_tier_does_not_dim_brian_and_bill(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE", "Pletor_MH")
    urlopen, seen = fake_api(speak=(403, json.dumps(DENIED).encode()), refuse=("v-pletor",))
    assert client.status("custom", urlopen)[0] == "hlas Pletor_MH vyžaduje tarif Creator"
    assert client.status("brian", urlopen)[0] is None and client.status("bill", urlopen)[0] is None
    assert all(method == "GET" for method, *_ in seen)  # kontrola nespotřebuje znaky
    with pytest.raises(EngineMissing, match="Pletor_MH vyžaduje tarif Creator"):
        client.stream("Ahoj.", "elevenlabs:custom", urlopen)
    assert b"".join(client.stream("Ahoj.", "elevenlabs:brian", urlopen)) == b"ID3mp3"
    assert client.status("bill", urlopen)[0] is None and client.status("custom", urlopen)[0] is not None


@pytest.mark.parametrize(("status", "body", "expected"), [
    (403, DENIED, "vyžaduje tarif Creator"),
    (401, {"detail": {"status": "invalid_api_key"}}, "nemá oprávnění"),
    (403, {"detail": {"status": "missing_permissions"}}, "nemá oprávnění"),
    (401, {"detail": {"status": "quota_exceeded"}}, "vyčerpán limit znaků"),
    (402, {}, "vyčerpán limit znaků"),
    (429, {"detail": {"status": "too_many_concurrent_requests"}}, "limit souběhu"),
])
def test_synthesis_errors_are_readable_and_mark_only_that_voice_unavailable(status, body, expected):
    urlopen, _ = fake_api(speak=(status, json.dumps(body).encode()))
    with pytest.raises(EngineMissing, match=expected) as error:
        client.stream("Ahoj.", "elevenlabs:bill", urlopen)
    assert KEY not in str(error.value)
    assert expected in client.status("bill", urlopen)[0]  # do dalšího ověření nedostupný, žádné 500
    assert client.status("brian", urlopen)[0] is None


def test_missing_key_and_network_failure():
    urlopen, seen = fake_api()
    client.ENV_FILE.unlink()
    assert client.status("brian", urlopen)[0].startswith("chybí ELEVENLABS_API_KEY") and not seen
    with pytest.raises(EngineMissing, match="chybí ELEVENLABS_API_KEY"):
        client.stream("Ahoj.", "elevenlabs:brian", urlopen)

    def offline(request, timeout):
        raise TimeoutError("timed out")
    client.reset()
    client.ENV_FILE.write_text(f"ELEVENLABS_API_KEY={KEY}\nELEVENLABS_VOICE=Pletor_MH\n", encoding="utf-8")
    assert client.status("bill", offline)[0] == "ElevenLabs neodpověděl: TimeoutError"
    urlopen, _ = fake_api(voices=[BRIAN, PREMADE])
    client.reset()
    assert client.status("custom", urlopen)[0] == "hlas Pletor_MH na účtu ElevenLabs není"
    assert client.status("bill", urlopen)[0] == "hlas Bill na účtu ElevenLabs není"
    assert client.status("brian", urlopen)[0] is None
