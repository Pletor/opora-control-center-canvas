"""Přihlášení k aplikaci z veřejného hosta (tunel): stav, login cookie, logout.

Rozhodovací logika hranice bydlí v `backend/app/remote_access.py`; tady je jen HTTP DTO,
aby router ležel v `backend/api/` jako všechny ostatní."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from backend.app.remote_access import COOKIE_NAME, TOKEN_REQUIRED, set_access_cookie, tokens_equal


def create_access_router(remote, *, port=8740, human=None):
    """`/api/access/*`: stav, přihlášení a odhlášení. Middleware je pouští bez tokenu."""
    router = APIRouter(prefix="/api/access", tags=["access"])
    loopback = (f"127.0.0.1:{port}", f"localhost:{port}")

    def public_host(request):
        host = request.headers.get("host", "")
        return "" if host in loopback else (host if remote.is_public_host(host) else "")

    @router.get("/status")
    def status(request: Request):
        host = public_host(request)
        if not host:
            # Loopback: hranice je počítač sám, žádná brána se nezobrazuje.
            return {"remote": False, "authenticated": True, "host": request.headers.get("host", "")}
        allowed = remote.authorized(request.headers.get("authorization"), request.cookies.get(COOKIE_NAME))
        return {"remote": True, "authenticated": allowed, "host": host}

    @router.post("/login")
    def login(payload: dict, request: Request, response: Response):
        if not public_host(request):
            return JSONResponse({"error": "Vzdálený přístup není zapnutý."}, status_code=403)
        token = payload.get("token") if isinstance(payload, dict) else None
        if not tokens_equal(remote.token, token):
            return JSONResponse({"error": TOKEN_REQUIRED}, status_code=401)
        set_access_cookie(response, remote.token)
        return {"ok": True}

    @router.get("/ui-session")
    def ui_session(request: Request, response: Response):
        """Doklad člověka pro UI (upgrade-opora #29): cookie dostane jen fetch z prohlížeče."""
        if human is None or not human.from_browser(request.headers):
            return JSONResponse({"error": "Doklad člověka vydává jen prohlížeč s UI aplikace."}, status_code=403)
        human.issue(response, secure=bool(public_host(request)), port=request.url.port)
        return {"ok": True}

    @router.post("/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=True, samesite="strict")
        return {"ok": True}

    return router
