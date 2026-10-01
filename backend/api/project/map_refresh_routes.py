"""Rozhraní Projektu: stav, globální přepínač, nastavení a opakování obnovy map."""

from fastapi import APIRouter, Query


def create_map_refresh_router(manager):
    router = APIRouter(prefix='/api/map-refresh', tags=['map-refresh'])

    @router.get('/status')
    def status(project: str = Query(min_length=1, max_length=64)):
        return manager.status(project)

    @router.get('/config')
    def config():
        # Globální přepínač aplikace (Nastavení → Obecné), nikdy per projekt.
        return manager.config()

    @router.post('/configure')
    def configure(payload: dict):
        if set(payload) != {'enabled'} or type(payload['enabled']) is not bool:
            raise ValueError('Očekáván pouze explicitní příznak enabled.')
        return manager.set_enabled(payload['enabled'])

    @router.post('/retry')
    def retry(project: str = Query(min_length=1, max_length=64), tool: str | None = Query(default=None)):
        return manager.retry(project, tool)

    @router.post('/settings')
    def settings(payload: dict):
        if set(payload) != {'project', 'tool', 'automatic'}:
            raise ValueError('Neplatný formát nastavení mapy.')
        return manager.settings(payload['project'], payload['tool'], payload['automatic'])

    return router
