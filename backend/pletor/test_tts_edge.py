"""Hlas Edge s falešným cloudem: kousky MP3 v pořadí, jen zvuk, výpadek = EngineMissing."""
import asyncio

import pytest

from backend.pletor import tts, tts_edge


def fake_cloud(chunks, error=None):
    seen = []

    class Communicate:
        def __init__(self, text, voice):
            seen.append((text, voice))

        async def stream(self):
            for chunk in chunks:
                yield chunk
            if error:
                raise error
    return Communicate, seen


async def collect(stream):
    return [chunk async for chunk in stream]


def test_stream_yields_audio_only():
    cloud, seen = fake_cloud([{"type": "WordBoundary"}, {"type": "audio", "data": b"ID3"}, {"type": "audio", "data": b""},
                              {"type": "audio", "data": b"mp3"}])
    chunks = asyncio.run(collect(tts_edge.stream("Ahoj.", "edge:cs-CZ-AntoninNeural", cloud)))
    assert chunks == [b"ID3", b"mp3"]
    assert seen == [("Ahoj.", "cs-CZ-AntoninNeural")]


def test_cloud_failure_is_engine_missing():
    cloud, _ = fake_cloud([], ConnectionError("offline"))
    with pytest.raises(tts.EngineMissing, match="offline"):
        asyncio.run(collect(tts_edge.stream("Ahoj.", "edge:cs-CZ-VlastaNeural", cloud)))
