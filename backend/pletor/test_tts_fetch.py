"""Stažení hlasů s falešným transportem: adresy HuggingFace, kontrola ONNX a configu, nic napůl."""
import json

import pytest

from backend.pletor import tts, tts_fetch

MODEL = b"\x08" + b"\x00" * tts_fetch.MIN_MODEL
CONFIG = json.dumps({"audio": {"sample_rate": 22050}}).encode()


def transport(model=MODEL, config=CONFIG):
    seen = []

    def get(address):
        seen.append(address)
        return config if address.endswith(".json") else model
    return get, seen


def test_fetch_writes_model_and_config(tmp_path):
    get, seen = transport()
    path = tts_fetch.fetch(tmp_path, "cs_CZ-jirka-medium", get=get)
    assert seen == [
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx.json"]
    assert path.read_bytes() == MODEL and path.with_name(path.name + ".json").read_bytes() == CONFIG
    assert tts.available(tmp_path)["default"] == "cs_CZ-jirka-medium"


@pytest.mark.parametrize("model, config", [
    (b"<html>Not found</html>" * 100_000, CONFIG),  # chybová stránka místo modelu
    (b"\x08tiny", CONFIG),  # useknutý model
    (MODEL, b"<html>"),  # config není JSON
    (MODEL, b"{}"),  # config bez sample_rate
], ids=["html", "useknuty", "config-html", "config-bez-rate"])
def test_fetch_rejects_bad_files(tmp_path, model, config):
    get, _ = transport(model, config)
    with pytest.raises(ValueError):
        tts_fetch.fetch(tmp_path, "cs_CZ-jirka-medium", get=get)
    assert not tts.voices_dir(tmp_path).exists()


def test_fetch_rejects_unknown_voice(tmp_path):
    get, seen = transport()
    with pytest.raises(ValueError):
        tts_fetch.fetch(tmp_path, "en_US-lessac-medium", get=get)
    assert seen == []
