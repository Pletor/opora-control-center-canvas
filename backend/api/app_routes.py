"""Rozhraní aplikace: zdraví, identita buildu a bootstrap klienta."""

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder

from backend.api.http_etag import conditional, etag_of


def create_app_router(service, identity):
    router = APIRouter(prefix="/api", tags=["app"])

    @router.get("/health")
    def health():
        return {"status": "ok", "product": "Opora Canvas", "execution": "explicit_bounded"}

    @router.get("/build-identity")
    def runtime_identity():
        return identity

    @router.get("/bootstrap")
    def bootstrap(request: Request):
        # Klient se ptá každé 2,5 s a obsah (projekty, úlohy, draft, paměť) se mění zřídka.
        # ETag je otisk kanonického JSON celé odpovědi, takže jakákoli změna dá jiný tag;
        # beze změny jde 304 bez těla a klient vezme tělo z paměti (`api` v shared/types).
        body = jsonable_encoder(service.bootstrap())
        return conditional(request, etag_of("bootstrap", body), lambda: body)

    return router
