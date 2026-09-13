"""Router pro context pakety; samostatný, žádná změna app.py.

Integrace do rodičovské aplikace: `app.include_router(create_context_router(service))`
PŘED `app.mount('/', StaticFiles(...))` a PO middleware pro host/origin/JSON (viz app.py).
Handlery propagují ValueError beze změny, stejně jako zbytek API — hostitel proto musí mít
zaregistrovaný `@app.exception_handler(ValueError)` vracející 409 (viz app.py `invalid`).
"""
from fastapi import APIRouter

from backend.context_packets import ContextPackets


def create_context_router(service):
    packets = ContextPackets(service)
    router = APIRouter()

    @router.post("/api/context/packets")
    def build_packet(payload: dict):
        return packets.build(payload)

    @router.get("/api/context/packets/{packet_id}")
    def get_packet(packet_id: str):
        return packets.load(packet_id)

    @router.post("/api/context/packets/{packet_id}/validate")
    def validate_packet(packet_id: str):
        return packets.validate(packet_id)

    return router
