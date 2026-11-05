# xtts_server

Pomocný server hlasu XTTS-v2 pro Pletora (`backend/agi_pletor/tts_xtts.py`). Žije ve vlastním prostředí, protože torch
s CUDA má přes 2 GB a do hlavního projektu nepatří.

    uv sync --project tools/xtts_server                      # jednou: Python 3.12, torch 2.8 + CUDA 12.8, coqui-tts
    uv run python -m backend.agi_pletor.tts_fetch xtts           # model ~1,9 GB do <data>/pletor/voices/xtts/

Spouští ho backend sám (líně, při otevření okna Pletora nebo první větě) a ukončí ho s sebou. `server.py` naslouchá
jen na `127.0.0.1` na volném portu, `POST /tts {text, reference?}` vrací PCM 16 bit LE 24 kHz po kouscích.
Vlastní hlas: `<data>/pletor/voices/xtts/reference/jarvis.wav` (6–15 s čisté řeči, jen lokální soubor).

Torch je pod 2.9: od 2.9 potřebuje torchaudio knihovnu `torchcodec` s FFmpeg DLL, které na Windows chybí.
`six` chybí v závislostech `coqui-tts` 0.28, proto je uvedený zvlášť.

Licence: `coqui-tts` MPL-2.0; **model XTTS-v2 je Coqui Public Model License (CPML), jen nekomerčně.**
