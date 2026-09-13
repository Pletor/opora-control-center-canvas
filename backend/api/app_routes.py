"""Rozhraní aplikace: zdraví, identita buildu a bootstrap klienta."""

from fastapi import APIRouter


def create_app_router(service, identity):
    router = APIRouter(prefix="/api", tags=["app"])

    @router.get("/health")
    def health():
        return {"status": "ok", "product": "Opora Canvas", "execution": "explicit_bounded"}

    @router.get("/build-identity")
    def runtime_identity():
        return identity

    @router.get("/bootstrap")
    def bootstrap():
        return service.bootstrap()

    return router
