Robustní API: tenké FastAPI routery rozdělené podle prostředí. app_routes (zdraví, identita, bootstrap), project_setup/, project/, editor/. Žádná logika, jen validace vstupu a volání balíčků prostředí. Nad api/ se staví mcp/.

Odstraňování v Editoru (`editor/canvas_routes.py`): `GET /api/removal-preview`, `POST /api/remove` (odpověď nese `recoveryId` u node/edge/selection) a `POST /api/remove/restore` `{project, workspace, recoveryId, digest}` → `{view}`.
