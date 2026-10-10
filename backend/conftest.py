"""Testy nikdy nespouštějí worker automatické aktualizace map (ten by volal Graphify a Sonnet).

Fronta se v testech řídí ručně přes `claim()` a `run_one()`; viz docs/mapy-projektu.md.
"""
import os

os.environ['OPORA_MAP_REFRESH_WORKER'] = '0'
# Sdílené hodnoty cache čtení (karta P3) se nesmí měnit na místě: v testech to hlídá otisk
# hodnoty při každém čtení z cache (backend/canvas/read_cache.py).
os.environ['OPORA_READ_CACHE_GUARD'] = '1'

# Testovací klient hraje lidské UI (upgrade-opora #29): server bere za člověka jen požadavek
# s relačním dokladem `opora_ui`. Pevné tajemství dostane každá aplikace z prostředí a každý
# TestClient nese jeho cookie, takže testy zápisů za člověka fungují jako v prohlížeči.
# Agent se dál hlásí hlavičkou `X-Opora-Actor` (ta má přednost) a test „bez dokladu“ cookie smaže.
TEST_UI_SECRET = 'test-ui-secret-' + 'x' * 24
os.environ['OPORA_UI_SECRET'] = TEST_UI_SECRET

from starlette.testclient import TestClient

_init = TestClient.__init__


def _as_human_ui(self, *args, **kwargs):
    _init(self, *args, **kwargs)
    self.cookies.set('opora_ui', TEST_UI_SECRET)


TestClient.__init__ = _as_human_ui
