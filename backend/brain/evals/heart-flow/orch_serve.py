"""Obal `opora_serve.py --heart` pro scénáře O sondy: kratší perioda hlídače gitu (`--git-poll S`).

Supervisor srdce čte `GIT_POLL` jako globál modulu při každém průchodu (`run_once`), proměnná prostředí pro něj
neexistuje a server běží v samostatném procesu. Obal proto v procesu serveru nastaví `supervisor.GIT_POLL` před
`create_app` a pak předá řízení beze změny `opora_serve.main`. Produktový kód ani sdílený `opora_serve.py` se nemění.

    uv run --project <repo> python orch_serve.py --git-poll 30 --heart --data … --repo … --port … --ready-file …
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MULTI = REPO / "backend" / "brain" / "evals" / "opora-vs-bare" / "multi"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    poll = None
    if "--git-poll" in argv:
        i = argv.index("--git-poll")
        poll = float(argv[i + 1])
        del argv[i:i + 2]
    sys.path[:0] = [str(REPO), str(MULTI), str(MULTI.parent)]
    if poll is not None:
        from backend.brain_opora.heart import supervisor
        supervisor.GIT_POLL = max(5.0, poll)
        print(f"orch_serve: GIT_POLL={supervisor.GIT_POLL}", flush=True)
    import opora_serve
    return opora_serve.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
