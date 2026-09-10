"""Izolovaný testovací server; nikdy nepoužívá živá data ani živý frontend."""
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from backend.app import create_app


def create_fixture():
    app = create_app()
    app.router.routes = [route for route in app.router.routes if getattr(route, 'name', None) != 'canvas']
    app.mount('/', StaticFiles(directory=Path('.data/clean-editor-dist'), html=True), name='canvas')
    return app
