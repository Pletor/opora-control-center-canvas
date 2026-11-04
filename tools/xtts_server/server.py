"""Pomocný server hlasu XTTS-v2 pro Pletora; spouští ho `backend/pletor/tts_xtts.py` z vlastního prostředí.

    .venv/Scripts/python.exe server.py <složka modelu>

Načte model do GPU (bez CUDA na CPU, pomalu), naslouchá na volném portu jen na 127.0.0.1 a vypíše `READY <port>`.
`POST /tts {text, reference?}` → PCM 16 bit LE mono 24 kHz po kouscích, jak je GPU vyrábí (HTTP/1.0, konec =
zavřené spojení); 200 přijde až s prvním kouskem, chyba před ním je 500. `reference` je cesta k lokálnímu vzorku
hlasu, jinak vestavěný mluvčí. Skončí, když backend zavře stdin (i když backend spadne).
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

SPEAKER = "Damien Black"  # vestavěný mužský mluvčí s klidným hlasem; vlastní hlas dá reference/jarvis.wav
LANGUAGE = "cs"
RATE = 24000


def load(folder):
    config = XttsConfig()
    config.load_json(str(folder / "config.json"))
    model = Xtts.init_from_config(config)
    model.load_checkpoint(config, checkpoint_dir=str(folder), use_deepspeed=False)
    return model.cuda() if torch.cuda.is_available() else model


def pcm(chunk):
    return (chunk.float().clamp(-1, 1) * 32767).to(torch.int16).cpu().numpy().astype("<i2").tobytes()


def main(folder):
    ready, sys.stdout = sys.stdout, sys.stderr  # výpisy knihoven při načítání nesmí předběhnout řádek READY
    model = load(folder)
    gpu = threading.Lock()  # jedna syntéza naráz; druhá věta v letu čeká ve frontě
    latents = {}

    def speaker(reference):
        key = (reference, Path(reference).stat().st_mtime) if reference else SPEAKER
        if key not in latents:
            if reference:
                latents[key] = model.get_conditioning_latents(audio_path=[reference])
            else:
                found = model.speaker_manager.speakers[SPEAKER]
                latents[key] = (found["gpt_cond_latent"], found["speaker_embedding"])
        return latents[key]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            started = False
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with gpu, torch.inference_mode():
                    cond, embedding = speaker(body.get("reference"))
                    for chunk in model.inference_stream(body["text"], LANGUAGE, cond, embedding, temperature=0.7,
                                                        stream_chunk_size=20, enable_text_splitting=True):
                        if not started:
                            self.send_response(200)
                            self.send_header("Content-Type", f"audio/pcm;rate={RATE}")
                            self.end_headers()
                            started = True
                        self.wfile.write(pcm(chunk))
            except Exception as error:  # noqa: BLE001 – chyba jedné věty nesmí shodit server; backend vezme další engine
                print(f"XTTS: {error!r}", file=sys.stderr, flush=True)
                if not started:
                    self.send_error(500, "XTTS selhal")

        def log_message(self, *args):
            pass

    with torch.inference_mode():  # první inference je o ~1 s pomalejší; zahřeje se tady, ne na první odpovědi
        model.inference("Dobrý den.", LANGUAGE, *speaker(None))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=lambda: (sys.stdin.read(), os._exit(0)), daemon=True).start()
    print(f"READY {server.server_address[1]}", file=ready, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
