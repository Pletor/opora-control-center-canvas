"""Kdo je člověk: relační doklad UI (upgrade-opora #29).

Původce požadavku se dřív četl jen z hlavičky `X-Opora-Actor` a chybějící hlavička znamenala
člověka. Agent, který hlavičku neposlal, tak mohl svěřit autonomii nebo potvrdit karty.

Teď je člověkem jen požadavek s cookie `opora_ui`. Její hodnotu (náhodné tajemství procesu)
vydá `GET /api/access/ui-session` jen prohlížeči: musí poslat `Sec-Fetch-Site: same-origin`,
kterou skript v JavaScriptu nastavit nemůže. Cookie je HttpOnly a SameSite=Strict.

Hranice je poctivě omezená: lokální proces se stejným uživatelem OS si prohlížeč umí
napodobit. Doklad proto nebrání úmyslnému podvrhu, ale z „výchozí = člověk“ dělá
„výchozí = neznámý“: obejít ho jde jen vědomým padělkem hlaviček, ne opomenutím.
Agentní hlavička má vždy přednost před cookie, takže agent se člověkem omylem nestane.
"""

import os
import secrets

from backend.app.remote_access import tokens_equal
from backend.canvas.activity_log import parse_actor

UI_COOKIE = "opora_ui"
# Jen pro testy: pevné tajemství, aby testovací klient mohl hrát lidské UI (backend/conftest.py).
SECRET_ENV = "OPORA_UI_SECRET"


class HumanSession:
    def __init__(self, secret=None):
        self.secret = secret or os.environ.get(SECRET_ENV) or secrets.token_urlsafe(32)

    @staticmethod
    def from_browser(headers):
        """Fetch z UI nese `Sec-Fetch-Site: same-origin`; curl ani skript ji samy nepošlou."""
        return (headers.get("sec-fetch-site") == "same-origin"
                and headers.get("sec-fetch-mode") in ("cors", "same-origin", "navigate"))

    def issue(self, response, *, secure):
        response.set_cookie(UI_COOKIE, self.secret, httponly=True, secure=secure,
                            samesite="strict", path="/api")

    def actor(self, headers, cookies):
        """(`actor`, `agent`): agentní hlavička > platná cookie UI (člověk) > `unknown`."""
        actor, agent = parse_actor(headers.get("x-opora-actor"))
        if actor == "agent":
            return actor, agent
        if tokens_equal(self.secret, cookies.get(UI_COOKIE)):
            return "human", ""
        return "unknown", ""
