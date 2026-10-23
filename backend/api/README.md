Robustní API: tenké FastAPI routery rozdělené podle prostředí. app_routes (zdraví, identita, bootstrap), project_setup/, project/, editor/. Žádná logika, jen validace vstupu a volání balíčků prostředí. Nad api/ se staví mcp/.

Podmíněné GET (`http_etag.py`, karta P3): `/api/view`, `/api/desktop-v3/state`, `/api/canvas-index`, `/api/canvas-versions` a `/api/canvas-versions/head` posílají `ETag` (otisk revize nebo digestu, projektu a prostoru); `If-None-Match` beze změny → 304 bez těla. Neznámé ID projektu (i jiná velikost písmen) → 404 `ProjectNotFound` a nic se nezaloží.

Štíhlé zápisy (oprava 8, `docs/navrhy/2026-10-14-vykon-platna.md`): `POST /api/desktop-v3/node` zapíše jednu kartu stavu (`DesktopV3State.save_node`) a `POST /api/graph/positions` `{project, workspace, digest, positions: [{id, x, y}]}` jen posun uzlů (`CanvasService.save_positions` → `save_graph`, takže platí rozdělení na architekturu a pravidlo čistého mainu; neznámé ID → 409). Obě odpovědi nesou jen revizi / hlavičku pohledu, ne celý stav ani graf.

Odstraňování v Editoru (`editor/canvas_routes.py`): `GET /api/removal-preview`, `POST /api/remove` (odpověď nese `recoveryId` u node/edge/selection) a `POST /api/remove/restore` `{project, workspace, recoveryId, digest}` → `{view}`.

Podmíněné GET (`http_etag.py`): `If-None-Match` → 304 bez těla mají stav, graf, index, výpis verzí a `GET /api/bootstrap`. Bootstrap klient polluje každé 2,5 s; jeho ETag je otisk kanonického JSON celé odpovědi, takže nový projekt, úloha i přepnutá paměť dají jiný tag (`test_bootstrap_etag.py`).
