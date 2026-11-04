"""Hlasy Pletora ze čtyř enginů za jedním seznamem a jednou routou (`GET /api/pletor/voices`, `POST /api/pletor/tts`).

Pořadí je zároveň výchozí volba okna: XTTS (lokální GPU, nejkvalitnější) → ElevenLabs (placený cloud) → Edge
(cloud) → Piper (lokální CPU). Id hlasu nese engine (`xtts:…`, `elevenlabs:…`, `edge:…`, jinak Piper), takže
stačí jedno pole `voice`.
"""
from starlette.concurrency import run_in_threadpool

from backend.pletor import tts, tts_edge, tts_xtts
from backend.pletor.elevenlabs import client as eleven


def engine(voice):
    if voice in tts_xtts.VOICES:
        return "xtts"
    if voice == eleven.VOICE:
        return "elevenlabs"
    return "edge" if voice in tts_edge.VOICES else "piper"


def voices(folder, vram=None):
    """Všechny známé hlasy `[{id, label, gender, engine, available, reason, quota}]` v pořadí enginů; `reason` říká,
    proč hlas nejde (nestažený model, málo VRAM, chybějící balíček, tarif ElevenLabs), `quota` jen u ElevenLabs."""
    free = (vram or tts_xtts.free_vram_mb)()
    found = [(voice, label, gender, "xtts", tts_xtts.reason(folder, voice, lambda: free), None)
             for voice, (label, gender) in tts_xtts.VOICES.items()]
    reason, quota = eleven.status()
    found.append((eleven.VOICE, eleven.label(), "male", "elevenlabs", reason, quota))
    edge = tts_edge.reason()
    found += [(voice, label, gender, "edge", edge, None) for voice, (label, gender) in tts_edge.VOICES.items()]
    downloaded = {voice["id"] for voice in tts.available(folder)["available"]}
    found += [(voice, label, gender, "piper",
               None if voice in downloaded else f"není stažen: uv run python -m backend.pletor.tts_fetch {voice}", None)
              for voice, (label, gender) in tts.VOICES.items()]
    return [{"id": voice, "label": label, "gender": gender, "engine": kind, "available": reason is None,
             "reason": reason, "quota": quota} for voice, label, gender, kind, reason, quota in found]


def default(found):
    return next((voice["id"] for voice in found if voice["available"]), None)


def warm(folder, voice):
    """Načte zvolený hlas dopředu (Piper do paměti, XTTS server do GPU); cloudové enginy nic nedrží."""
    if engine(voice) == "xtts":
        tts_xtts.warm(folder, voice)
    elif engine(voice) == "piper":
        tts.warm(folder, voice)


async def speak(folder, text, voice):
    """`(media type, zvuk)`: WAV z Piperu jako bajty, PCM z XTTS a MP3 z Edge a ElevenLabs jako kousky. První kousek
    (nebo stavová odpověď) se čeká tady, takže výpadek enginu je výjimka dřív, než route pošle 200."""
    if engine(voice) == "edge":
        chunks = tts_edge.stream(text, voice)
        try:
            first = await anext(chunks)
        except StopAsyncIteration as error:
            raise tts.EngineMissing("Edge TTS nevrátil žádný zvuk.") from error

        async def rest():
            yield first
            async for chunk in chunks:
                yield chunk
        return "audio/mpeg", rest()
    if engine(voice) == "elevenlabs":
        return "audio/mpeg", await run_in_threadpool(eleven.stream, text)
    if engine(voice) == "xtts":
        return tts_xtts.MEDIA, await run_in_threadpool(tts_xtts.stream, folder, text, voice)
    return "audio/wav", await run_in_threadpool(tts.synthesize, folder, text, voice)
