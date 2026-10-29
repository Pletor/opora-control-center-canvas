"""Nastavení rozhodovacího modelu Jev (docs/brain-heart-channel.md §5, H2b2a).

- `GET /api/brain/jev` → `{configured, provider, keys}`: který poskytovatel je zvolený a jestli má klíč (jen booleany).
- `POST /api/brain/jev/key {key: text | null, provider?}`: uloží nebo smaže klíč; jen člověk, klíč se nikdy nevrací.
- `GET|POST /api/brain/jev/gate-check {project, provider, allowed}`: povolení externí kontroly bran Schránky
  pro projekt (docs/schranka-neurony.md §7, §9 bod 10); zápis jen člověk.
Celá cesta je jen pro loopback (`backend/app/remote_access.py`): klíč placeného API se mění jen doma.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.activity_log import require_authority, require_human
from backend.integrations.typesafe_client import DEFAULT_PROVIDER, PROVIDERS


def create_jev_router(settings, provider=DEFAULT_PROVIDER):
    """`settings` je úložiště klíčů a povolení (`AppSettings`); `provider` je volba z `opora.local.toml`,
    `configured` platí pro něj."""
    router = APIRouter(prefix="/api/brain/jev", tags=["jev"])

    def _jev():
        keys = {name: bool(settings and settings.jev_key(name)) for name in PROVIDERS}
        return {"configured": keys[provider], "provider": provider, "keys": keys}

    @router.get("")
    def jev_status():
        return _jev()

    @router.post("/key")
    def jev_key(payload: dict, request: Request):
        """Uloží nebo smaže klíč poskytovatele Jev pro celou aplikaci; klíč se nikdy nevrací.
        Bez `provider` jde o klíč TypeSafe."""
        # Výjimka §4 (docs/plna-autonomie-agenta.md): klíče a tajemství jen člověk, i při plné autonomii.
        require_human(getattr(request.state, "actor", "unknown"), "Klíč poskytovatele ukládá jen člověk v UI.")
        if (settings is None or not isinstance(payload, dict) or "key" not in payload
                or set(payload) - {"key", "provider"}):
            return JSONResponse({"error": "Tělo je {key: text | null, provider?: typesafe | celeris}."}, status_code=422)
        name = payload.get("provider", "typesafe")
        if name not in PROVIDERS:
            return JSONResponse({"error": "provider musí být " + " nebo ".join(PROVIDERS) + "."}, status_code=422)
        try:
            settings.set_jev_key(payload["key"], name)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        return {"jev": _jev()}

    @router.get("/gate-check")
    def gate_check_status(project: str):
        """Pro který poskytovatel je v projektu povolená externí kontrola bran (§9 bod 10)."""
        allowed = settings.gate_check_permissions().get(project, []) if settings else []
        return {"project": project, "allowed": {name: name in allowed for name in PROVIDERS}}

    @router.post("/gate-check")
    def gate_check_set(payload: dict, request: Request):
        """Povolí nebo zakáže kontrolu bran pro (projekt, poskytovatel); jen člověk v UI."""
        require_authority(getattr(request.state, "actor", "unknown"),
                          "Externí kontrolu bran povoluje jen člověk v UI.")
        if (settings is None or not isinstance(payload, dict)
                or set(payload) != {"project", "provider", "allowed"}):
            return JSONResponse({"error": "Tělo je přesně {project, provider, allowed: true | false}."}, status_code=422)
        try:
            allowed = settings.set_gate_check_allowed(payload["project"], payload["provider"], payload["allowed"])
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        return {"project": payload["project"], "allowed": {name: name in allowed for name in PROVIDERS}}

    return router
