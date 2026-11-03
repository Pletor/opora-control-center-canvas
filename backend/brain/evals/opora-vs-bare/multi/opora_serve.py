"""Izolovaná OPORA ramene A přes všechna sezení jednoho opakování (data přežijí restart mezi sezeními).

Spouští se stejně jako `opora_backend.py` (`uv run --project <repo> python multi/opora_serve.py --data … --repo …
--port … --ready-file … --autonomy-log …`). První start (ready-file ještě neexistuje) je přesně `opora_backend.main`:
prázdný lokální projekt + `grant_autonomy`. Každý další start nad stejnými `--data` jen znovu obslouží týž projekt na
novém portu a přepíše `baseUrl` v ready-file (žádný nový projekt, autonomie zůstává zapnutá v datech).
`opora_backend.py` se nemění (schválené sha běhů v1–v3 zůstává platné).

Rameno E (`--heart`): jen obslouží data na portu se zapnutým srdcem (`OPORA_HEART=on`, `OPORA_CANVAS_HOST=127.0.0.1`,
supervisor běží jen na loopbacku). Projekt ani bránu nezakládá: to dělá harness jako člověk přes HTTP, a proto
tajemství cookie `opora_ui` dostane od harnessu v `OPORA_EVAL_UI_SECRET` (k agentovi nikdy nejde). Bez autonomie.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FLOW = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FLOW))
import opora_backend as ob  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--heart" in argv:
        argv.remove("--heart")
        return serve_heart(dict(zip(argv[::2], argv[1::2])))
    opts = dict(zip(argv[::2], argv[1::2]))
    ready = Path(opts["--ready-file"])
    data = Path(opts["--data"]).resolve()
    prev = json.loads(ready.read_text(encoding="utf-8")) if ready.exists() else None
    if not prev or not data.exists():
        return ob.main(argv)  # první sezení: projekt + autonomie + server
    port = int(opts["--port"])
    if port == 8740:
        sys.exit("port 8740 patří živé OPORE; eval ho nepoužívá")
    if "opora-data" in str(data).lower():
        sys.exit("datová složka evalu nesmí ležet v opora-data")
    os.environ.update({**ob.ENV, "OPORA_UI_SECRET": os.urandom(24).hex(), "OPORA_CANVAS_DATA": str(data),
                       "OPORA_CANVAS_PORT": str(port)})
    ready.write_text(json.dumps({"project": prev["project"], "workspace": prev["workspace"],
                                 "baseUrl": f"{ob.ORIGIN}:{port}"}), encoding="utf-8")
    sys.path.insert(0, str(ob.ROOT))
    import uvicorn

    from backend.app.factory import create_app
    uvicorn.run(create_app(data), host="127.0.0.1", port=port, log_level="warning")
    return 0


def serve_heart(opts) -> int:
    """Rameno E: OPORA se srdcem nad `--data` na `--port`; ready-file = jen `{baseUrl}` (projekt drží harness)."""
    port = int(opts["--port"])
    data = Path(opts["--data"]).resolve()
    if port == 8740:
        sys.exit("port 8740 patří živé OPORE; eval ho nepoužívá")
    if "opora-data" in str(data).lower():
        sys.exit("datová složka evalu nesmí ležet v opora-data")
    secret = os.environ.pop("OPORA_EVAL_UI_SECRET", "")
    if len(secret) < 32:
        sys.exit("chybí OPORA_EVAL_UI_SECRET (tajemství lidské relace harnessu)")
    data.mkdir(parents=True, exist_ok=True)
    os.environ.update({**ob.ENV, "OPORA_UI_SECRET": secret, "OPORA_CANVAS_DATA": str(data),
                       "OPORA_CANVAS_PORT": str(port), "OPORA_HEART": "on", "OPORA_CANVAS_HOST": "127.0.0.1"})
    Path(opts["--ready-file"]).write_text(json.dumps({"baseUrl": f"{ob.ORIGIN}:{port}"}), encoding="utf-8")
    sys.path.insert(0, str(ob.ROOT))
    import uvicorn

    from backend.app.factory import create_app
    app = create_app(data)  # HumanSession si tajemství přečte teď
    os.environ.pop("OPORA_UI_SECRET", None)  # dávky srdce (`claude -p`) dědí prostředí: tajemství člověka jim nedáme
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
