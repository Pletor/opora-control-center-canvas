"""HTTP kontrakt paměti agenta podle role: stav, role, vybavení, zápis, půjčka, přepínač.

Tenký router: veškerá logika je v `backend/memory/memory_service.py`. Klíče požadavku se
kontrolují přesně (ValueError → 409 přes handler v `backend/app/factory.py`), aby klient
nemohl poslat půlku nebo překlep.

Role karty je autorita serveru: když klient `role` nepošle (`null`), server ji přečte
z `agentRole` uzlu. Karta bez role není chyba — vrací se `status: "skipped"`, ne prázdný
výsledek, který by vypadal jako „nic si nepamatuji“.
"""

from fastapi import APIRouter

from backend.memory import roles

RECALL_KEYS = {"role", "project", "workspace", "nodeId", "query", "maxTokens"}
REMEMBER_KEYS = {"role", "project", "workspace", "nodeId", "kind", "text", "confirmed"}
LEND_KEYS = {"fromRole", "toRole", "query", "maxTokens"}
SETTINGS_KEYS = {"enabled"}
PROVISION_KEYS = {"confirmed"}
NO_ROLE = "Karta nemá přiřazenou roli agenta."


def _exact(payload, keys, label):
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ValueError(f"{label} vyžaduje přesně pole {', '.join(sorted(keys))}.")
    return payload


def _optional_role(value):
    if value is None:
        return None
    if not isinstance(value, str) or roles.role(value) is None:
        raise ValueError(f"Role {value!r} není v knihovně rolí agenta.")
    return value


def create_memory_router(service, memory_service):
    router = APIRouter(prefix="/api/memory", tags=["memory"])

    def node_role(project, workspace, node_id):
        """Role karty ze stavu Desktop v3; scope ověří sám `state.read` (409 na nesmysl)."""
        state = getattr(service, "desktop_v3_state", None)
        if state is None or not isinstance(node_id, str) or not node_id:
            return None
        node = state.read(project, workspace)["state"]["nodes"].get(node_id, {})
        value = node.get("agentRole")
        return value if isinstance(value, str) and value else None

    @router.get("/status")
    def status():
        """Pravdivý stav: disabled, unavailable, needs_provisioning (+ `missingRoles`), configured."""
        return memory_service.status()

    @router.post("/provision")
    def provision(payload: dict):
        """Rozdá rolím klíče u OpenVikingu. Zakládá uživatele, proto to potvrzuje člověk.

        Odpověď nese jen jména rolí a důvody chyb — **klíč se nikdy nevrací ani neloguje**.
        """
        _exact(payload, PROVISION_KEYS, "Rozdání klíčů rolím")
        if payload["confirmed"] is not True:
            raise ValueError("Rozdání klíčů rolím vyžaduje výslovné potvrzení.")
        return memory_service.provision_roles()

    @router.get("/roles")
    def role_registry():
        """Knihovna rolí (library/agent-roles.json); jen ke čtení."""
        return {"roles": roles.load()}

    @router.post("/recall")
    def recall(payload: dict):
        _exact(payload, RECALL_KEYS, "Vybavení paměti")
        role = _optional_role(payload["role"]) or node_role(
            payload["project"], payload["workspace"], payload["nodeId"]
        )
        if role is None:
            return {"status": "skipped", "reason": NO_ROLE, "role": None,
                    "items": [], "rendered": "", "truncated": False}
        return memory_service.recall(role, payload["project"], payload["nodeId"],
                                     payload["query"], payload["maxTokens"])

    @router.post("/remember")
    def remember(payload: dict):
        """Zápis do sdílené paměti role potvrzuje člověk; `confirmed` není volitelné."""
        _exact(payload, REMEMBER_KEYS, "Zápis do paměti")
        if payload["confirmed"] is not True:
            raise ValueError("Zápis do paměti role vyžaduje výslovné potvrzení.")
        role = _optional_role(payload["role"]) or node_role(
            payload["project"], payload["workspace"], payload["nodeId"]
        )
        if role is None:
            return {"status": "skipped", "reason": NO_ROLE, "uri": ""}
        return memory_service.remember(role, payload["project"], payload["nodeId"],
                                       payload["kind"], payload["text"])

    @router.post("/lend")
    def lend(payload: dict):
        """Půjčka z paměti jiné role; položky nesou `origin: lent:<role>`, nikdy `self`."""
        _exact(payload, LEND_KEYS, "Půjčka paměti")
        return memory_service.lend(payload["fromRole"], payload["toRole"],
                                   payload["query"], payload["maxTokens"])

    @router.post("/settings")
    def settings(payload: dict):
        """Přepínač platí pro celou aplikaci, nikdy pro jeden projekt."""
        _exact(payload, SETTINGS_KEYS, "Nastavení paměti")
        if type(payload["enabled"]) is not bool:
            raise ValueError("Přepínač paměti rolí musí být true/false.")
        memory_service.settings.set_enabled(payload["enabled"])
        return memory_service.status()

    return router
