"""Izolovaná instance backendu OPORA pro rameno A evalu „OPORA vs. bez OPORY“.

Spouští se z kořene repa přes `uv run python backend/brain/evals/opora-vs-bare/opora_backend.py …`
(potřebuje závislosti backendu). Nikdy nesahá na živou aplikaci `:8740` ani na `P:/opora-data`:
data leží v `--data` (dočasná složka harnessu), pracovní smyčky jsou vypnuté a `.env`
ani `opora.local.toml` se nečtou (žádný `tools/opora.py`, rovnou `create_app` + uvicorn).

Postup (vše jako člověk s `ui_secret` tohoto procesu; agent cookie člověka nikdy nedostane):
1. připojí pracovní kopii evalu (`--repo`) jako **prázdný** lokální projekt (`POST /api/local-project`) –
   žádná mapa, stránky, cesty ani karty; celý plán si agent A vytvoří sám v plátně,
2. jednou zapne agentovi plnou autonomii (`grant_autonomy`, kontrakt `docs/plna-autonomie-agenta.md`),
   výsledek zapíše do `--autonomy-log` (JSON),
3. zapíše `--ready-file` (JSON `{project, workspace, baseUrl}`) a obslouží HTTP na `--port`.

`--setup-only` jen založí projekt, zapne autonomii a skončí (kontrola bez serveru).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ORIGIN = "http://127.0.0.1"
AGENT_NAME = "eval-agent"
ENV = {
    "OPORA_MAP_REFRESH_WORKER": "0", "OPORA_EXECUTION_PR_WORKER": "0", "OPORA_AUTO_REBASE_WORKER": "0",
    "OPORA_RECONCILIATION_WORKER": "0", "OPORA_GUARDS_WORKER": "0", "OPORA_READ_CACHE_GUARD": "1",
    "OPORA_MIRROR_URL": "", "OPORA_MIRROR_PROJECTS": "",
}


def grant_autonomy(client, project: str) -> dict:
    """Jako člověk jednou zapne projektu přepínač „plná autonomie agentů“ (docs/plna-autonomie-agenta.md §6).

    `client` = TestClient s cookie `opora_ui` a hlavičkou Origin (lidská relace harnessu). Zápis je
    `POST /api/project-settings/agent-autonomy {project, full}`; stav se ověří čtením. Jen při `status: "on"`
    řekne run_eval agentovi A, že autonomii má; jiný stav ukáže `meta.autonomy` v results.jsonl.
    """
    wrote = client.post("/api/project-settings/agent-autonomy", json={"project": project, "full": True})
    seen = client.get("/api/project-settings", params={"project": project})
    observed = seen.json().get("agentAutonomy") if seen.status_code == 200 else None
    on = wrote.status_code == 200 and isinstance(observed, dict) and observed.get("full") is True
    return {"status": "on" if on else "failed", "agent": AGENT_NAME, "project": project,
            "write": wrote.status_code, "observed": observed,
            "at": datetime.now(UTC).isoformat(timespec="seconds")}


def setup(data_root: Path, repo: Path, port: int, ui_secret: str) -> tuple[dict, dict]:
    """Prázdný lokální projekt + plná autonomie. Vrací (scope, autonomy)."""
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    origin = f"{ORIGIN}:{port}"
    app = create_app(data_root)
    with TestClient(app, base_url=origin, headers={"origin": origin}) as client:
        client.cookies.set("opora_ui", ui_secret)
        # Lokální projekt (ne git v OPOŘE): plátno žije v pracovním prostoru `draft`, žádný git worktree OPORY
        # (ten na Windows padá na délce cesty a agenta by sváděl psát kód jinam než do pracovní kopie).
        made = client.post("/api/local-project", json={"name": "Eval", "path": str(repo), "confirmed": True})
        if made.status_code != 200:
            raise RuntimeError(f"/api/local-project -> {made.status_code}: {made.text[:400]}")
        scope = {"project": made.json()["id"], "workspace": "draft"}
        view = client.get("/api/view", params=scope)
        view.raise_for_status()
        nodes = view.json()["graph"]["nodes"]
        if nodes:
            raise RuntimeError(f"nový projekt není prázdný ({len(nodes)} uzlů)")
        autonomy = grant_autonomy(client, scope["project"])
    app.state.service.close()
    return scope, autonomy


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", required=True, help="dočasná datová složka (nikdy P:/opora-data)")
    parser.add_argument("--repo", required=True, help="pracovní kopie evalu (git)")
    parser.add_argument("--port", type=int, required=True, help="port této instance OPORY")
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--autonomy-log", help="JSON s výsledkem grant_autonomy (výchozí vedle --ready-file)")
    parser.add_argument("--setup-only", action="store_true")
    args = parser.parse_args(argv)
    if args.port == 8740:
        sys.exit("port 8740 patří živé OPORE; eval ho nepoužívá")
    data = Path(args.data).resolve()
    if "opora-data" in str(data).lower():
        sys.exit("datová složka evalu nesmí ležet v opora-data")
    ui_secret = os.urandom(24).hex()  # jen v tomto procesu; do ready-file, logu ani k agentovi nejde
    os.environ.update({**ENV, "OPORA_UI_SECRET": ui_secret, "OPORA_CANVAS_DATA": str(data),
                       "OPORA_CANVAS_PORT": str(args.port)})
    scope, autonomy = setup(data, Path(args.repo).resolve(), args.port, ui_secret)
    ready = Path(args.ready_file)
    log = Path(args.autonomy_log) if args.autonomy_log else ready.with_name("autonomy.json")
    log.write_text(json.dumps(autonomy, ensure_ascii=False), encoding="utf-8")
    ready.write_text(json.dumps({**scope, "baseUrl": f"{ORIGIN}:{args.port}"}), encoding="utf-8")
    if args.setup_only:
        return 0
    import uvicorn

    from backend.app.factory import create_app
    uvicorn.run(create_app(data), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
