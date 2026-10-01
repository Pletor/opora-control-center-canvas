"""Spustí backend + statický build z tohoto worktree nad zadanou kopií dat. Chráněné porty 8740/8768 nikdy; 8780 jen s --allow-8780."""  # noqa: N999 — spouštěcí skript, název se spojovníkem je záměrný
import argparse
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--data", required=True, help="adresář s canvas.sqlite (kopie dat)")
parser.add_argument("--allow-8780", action="store_true", help="povolí převzetí náhledového portu 8780")
args = parser.parse_args()
if args.port in (8740, 8768) or (args.port == 8780 and not args.allow_8780):
    sys.exit(f"port {args.port} je chráněný")
with socket.socket() as probe:
    if probe.connect_ex(("127.0.0.1", args.port)) == 0:
        sys.exit(f"port {args.port} je obsazený")
data = Path(args.data).resolve()
data.mkdir(parents=True, exist_ok=True)
os.environ["OPORA_CANVAS_PORT"] = str(args.port)
os.environ["OPORA_CANVAS_DATA"] = str(data)
# Náhled nad kopií dat nespouští automatickou aktualizaci map ve skutečných projektech.
os.environ.setdefault("OPORA_MAP_REFRESH_WORKER", "0")

import uvicorn

from backend.app import create_app

uvicorn.run(create_app(data), host="127.0.0.1", port=args.port)
