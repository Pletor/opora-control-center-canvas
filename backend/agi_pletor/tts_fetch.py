"""Výslovné stažení hlasů z HuggingFace: Piper (`rhasspy/piper-voices`, model MIT, dataset CC0) a XTTS-v2
(`coqui/XTTS-v2`, ~1,9 GB, licence CPML: jen nekomerčně).

    uv run python -m backend.pletor.tts_fetch cs_CZ-jirka-medium cs_CZ-kasandra-medium xtts [--data <kořen dat>]

Kořen dat: `--data`, jinak `OPORA_CANVAS_DATA`, jinak `[app] data` z opora.toml + opora.local.toml (jako `uv run opora`).
Soubor se zapíše jen celý: velikost podle `Content-Length`, ONNX začíná polem `ir_version`, config je JSON s
`audio.sample_rate`. Zápis přes dočasný soubor, takže přerušené stažení nenechá napůl model.
"""
import argparse
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from backend.agi_pletor import tts, tts_xtts
from backend.agi_pletor.service import FOLDER

URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{family}/{code}/{name}/{quality}/{voice}{ext}"
MIN_MODEL = 1_000_000  # medium hlas má ~60 MB; menší soubor je chybová stránka nebo useknutý přenos
XTTS_URL = "https://huggingface.co/coqui/XTTS-v2/resolve/main/{name}"
# Nejmenší rozumná velikost souborů XTTS (skutečně 1 868 MB, 4 kB, 361 kB, 7,7 MB); .pth je zip torch.save (PK).
XTTS_MIN = {"model.pth": 1_800_000_000, "config.json": 1_000, "vocab.json": 100_000, "speakers_xtts.pth": 1_000_000}


def url(voice, ext):
    code, name, quality = voice.split("-")
    return URL.format(family=code.split("_")[0], code=code, name=name, quality=quality, voice=voice, ext=ext)


def http_get(address):
    with urllib.request.urlopen(address, timeout=60) as response:
        body = response.read()
        expected = response.headers.get("Content-Length")
    if expected is not None and len(body) != int(expected):
        raise ValueError(f"neúplný přenos {len(body)} z {expected} B: {address}")
    return body


def http_download(address, path):
    """Velký soubor rovnou na disk po 1 MB (model XTTS má 1,9 GB); velikost podle `Content-Length`."""
    with urllib.request.urlopen(address, timeout=60) as response, open(path, "wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
        expected = response.headers.get("Content-Length")
    if expected is not None and path.stat().st_size != int(expected):
        raise ValueError(f"neúplný přenos {path.stat().st_size} z {expected} B: {address}")


def fetch_xtts(folder, download=http_download):
    """Stáhne XTTS-v2 do `<folder>/voices/xtts/` a připraví `reference/` pro vlastní `jarvis.wav`. Vadný soubor =
    ValueError a na místě nezůstane; hotové soubory se nestahují znovu."""
    target = tts_xtts.model_dir(folder)
    target.mkdir(parents=True, exist_ok=True)
    for name, minimum in XTTS_MIN.items():
        path = target / name
        if path.is_file() and path.stat().st_size >= minimum:
            continue
        part = path.with_name(name + ".part")
        try:
            download(XTTS_URL.format(name=name), part)
            body = part.read_bytes()[:2] if name.endswith(".pth") else part.read_bytes()
            if part.stat().st_size < minimum or (name.endswith(".pth") and body != b"PK"):
                raise ValueError(f"{name} není soubor XTTS ({part.stat().st_size} B)")
            if name.endswith(".json"):
                json.loads(body)
        except (ValueError, OSError):  # chyba sítě ani vadný soubor nenechají napůl stažený .part
            part.unlink(missing_ok=True)
            raise
        part.replace(path)
    tts_xtts.reference(folder).parent.mkdir(exist_ok=True)
    return target


def _write(path, body):
    part = path.with_name(path.name + ".part")
    part.write_bytes(body)
    part.replace(path)


def fetch(folder, voice, get=http_get):
    """Stáhne model a config hlasu do `<folder>/voices/`; vrátí cestu k `.onnx`. Neznámý hlas nebo vadný soubor = ValueError."""
    if voice not in tts.VOICES:
        raise ValueError(f"neznámý hlas {voice}; známé: {', '.join(tts.VOICES)}")
    model, config = get(url(voice, ".onnx")), get(url(voice, ".onnx.json"))
    if len(model) < MIN_MODEL or model[:1] != b"\x08":  # ONNX ModelProto: první pole ir_version (tag 0x08)
        raise ValueError(f"{voice}.onnx není model ONNX ({len(model)} B)")
    try:
        int(json.loads(config)["audio"]["sample_rate"])
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"{voice}.onnx.json není config Piperu") from error
    target = tts.voices_dir(folder)
    target.mkdir(parents=True, exist_ok=True)
    _write(target / f"{voice}.onnx.json", config)
    _write(target / f"{voice}.onnx", model)
    return target / f"{voice}.onnx"


def data_root():
    if os.environ.get("OPORA_CANVAS_DATA"):
        return Path(os.environ["OPORA_CANVAS_DATA"])
    from tools.opora import ROOT, load_config, resolve

    return (ROOT / resolve(load_config())["data"]).resolve()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stáhne české hlasy Piperu a XTTS pro Pletora.")
    parser.add_argument("voices", nargs="+", choices=[*tts.VOICES, "xtts"])
    parser.add_argument("--data", type=Path, default=None)
    args = parser.parse_args(argv)
    folder = (args.data or data_root()) / FOLDER
    for voice in args.voices:
        if voice == "xtts":
            path = fetch_xtts(folder)
            print(f"xtts: {path} (vlastní hlas ke klonování: {tts_xtts.reference(folder)}, 6–15 s WAV)")
            continue
        path = fetch(folder, voice)
        print(f"{voice}: {path} ({path.stat().st_size // 1_000_000} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
