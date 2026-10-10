Robustní API: tenké FastAPI routery rozdělené podle prostředí. app_routes (zdraví, identita, bootstrap), project_setup/, project/, editor/. Žádná logika, jen validace vstupu a volání balíčků prostředí. Nad api/ se staví mcp/.

Podmíněné GET (`http_etag.py`, karta P3): `/api/view`, `/api/desktop-v3/state`, `/api/canvas-index`, `/api/canvas-versions` a `/api/canvas-versions/head` posílají `ETag` (otisk revize nebo digestu, projektu a prostoru); `If-None-Match` beze změny → 304 bez těla. Neznámé ID projektu (i jiná velikost písmen) → 404 `ProjectNotFound` a nic se nezaloží.

Odstraňování v Editoru (`editor/canvas_routes.py`): `GET /api/removal-preview`, `POST /api/remove` (odpověď nese `recoveryId` u node/edge/selection) a `POST /api/remove/restore` `{project, workspace, recoveryId, digest}` → `{view}`.
