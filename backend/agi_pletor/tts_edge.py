"""Hlas Pletora přes Edge neural (`edge-tts`, LGPL-3): neoficiální cloudová služba Microsoftu, zdarma, bez klíče.

Text k přečtení odchází z počítače do Microsoftu. Sem proto smí jen text odpovědi, který okno čte nahlas
(`POST /api/pletor/tts`), nikdy podklady, kontext mozku ani tajemství. Zvuk přichází jako MP3 po kouscích.
"""
from backend.agi_pletor.tts import EngineMissing

VOICES = {"edge:cs-CZ-AntoninNeural": ("Antonín", "male"), "edge:cs-CZ-VlastaNeural": ("Vlasta", "female")}


def _communicate(text, voice):
    try:
        import edge_tts
    except ImportError as error:
        raise EngineMissing("Edge TTS není nainstalovaný: uv sync --group tts.") from error
    return edge_tts.Communicate(text, voice)


def reason():
    """Proč hlas Edge nejde použít (`None` = jde); síť se ověří až při čtení a chyba přepne okno na další engine."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return "Edge TTS není nainstalovaný: uv sync --group tts."
    return None


async def stream(text, voice, communicate=None):
    """Kousky MP3 hned, jak je cloud pošle. Route čeká na první kousek, takže výpadek sítě je chyba požadavku
    (okno přejde na další engine), ne useknutý zvuk."""
    try:
        async for chunk in (communicate or _communicate)(text, voice.removeprefix("edge:")).stream():
            if chunk["type"] == "audio" and chunk["data"]:
                yield chunk["data"]
    except EngineMissing:
        raise
    except Exception as error:  # edge-tts hází vlastní výjimky i chyby aiohttp; pro okno jsou všechny „nejde“
        raise EngineMissing(f"Edge TTS neodpověděl: {error}") from error
