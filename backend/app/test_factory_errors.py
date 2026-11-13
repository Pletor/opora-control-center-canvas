"""Server do deníku chyb: neošetřená výjimka → 500 + `exception`, ValueError → 409 + `refusal`; odpovědi beze změny."""
from fastapi.testclient import TestClient

from backend.app import error_log, errors
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN


def boom():
    raise RuntimeError("rozbité 3f2a9c81d0")


def conflict():
    raise ValueError("A human must reopen confirmed cards")


def test_internal_error_and_refusal_are_recorded(tmp_path):
    app = create_app(tmp_path)
    app.add_api_route("/api/test-boom", boom)
    app.add_api_route("/api/test-conflict", conflict)
    app.router.routes[:0] = [app.router.routes.pop(), app.router.routes.pop()]  # před záchytnou routu statiky
    try:
        with TestClient(app, base_url=ORIGIN, raise_server_exceptions=False) as client:
            failed = client.get("/api/test-boom", headers=HEADERS, params={"project": "p"})
            assert failed.status_code == 500
            assert failed.json() == {"error": "Interní chyba serveru.", "code": "internal_error"}
            refused = client.get("/api/test-conflict", headers=HEADERS)
            assert refused.status_code == 409 and refused.json() == {"error": "A human must reopen confirmed cards"}
            error_log.drain()
            found = {(r["source"], r["kind"], r["severity"], r["subject"]): r for r in errors.read()}
            internal = found[("server", "exception", "error", "GET /api/test-boom")]
            assert internal["project"] == "p" and "RuntimeError: rozbité" in internal["cause"]
            assert found[("server", "refusal", "warn", "GET /api/test-conflict")]["message"].startswith("A human")
            assert sum(r["kind"] == "exception" for r in errors.read()) == 1  # logování 500 nezdvojí
    finally:
        errors.configure(None)
