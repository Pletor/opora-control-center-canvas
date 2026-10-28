"""Oprávnění odděleně od původce (docs/plna-autonomie-agenta.md §2).

`request.state.actor` říká, KDO požadavek poslal (člověk / agent / neznámý) a do záznamu činnosti,
událostí i revizí se píše beze změny. `authority` říká, CO smí: `human` má člověk s dokladem UI
a agent v projektu, kterému člověk zapnul plnou autonomii agentů.

Middleware (`backend/app/factory.py`) rozhodne oprávnění jednou na požadavek a uloží ho do
kontextu požadavku. Brány „jen člověk“ ve službách se ptají `acts_as_human(actor)`: služba tak
dostane rozhodnutí zvenku a sama nehádá. Když brána projde jen díky autonomii, kontext si to
poznamená a záznam činnosti řádek označí `autonomy: "full"`.
"""

from contextvars import ContextVar
from dataclasses import dataclass

AUTHORITIES = ("human", "agent", "unknown")


@dataclass
class RequestAuthority:
    actor: str
    authority: str
    project: str = ""
    used: bool = False  # brána „jen člověk“ prošla agentovi díky plné autonomii


_CURRENT: ContextVar[RequestAuthority | None] = ContextVar("opora_request_authority", default=None)


def resolve(actor, autonomy_full):
    """Oprávnění z původce a přepínače projektu; neznámý původce nikdy nedostane víc než `unknown`."""
    if actor == "human":
        return "human"
    if actor == "agent":
        return "human" if autonomy_full else "agent"
    return "unknown"


def begin(actor, authority, project=""):
    """Nastaví oprávnění požadavku; vrací stav (sdílený s vlákny endpointu) a token pro `end`."""
    state = RequestAuthority(actor, authority, project)
    return state, _CURRENT.set(state)


def end(token):
    _CURRENT.reset(token)


def current():
    return _CURRENT.get()


def acts_as_human(actor):
    """Smí `actor` projít bránou „jen člověk“? Člověk vždy; agent jen v požadavku s plnou autonomií.

    Rozhodnutí bere z kontextu požadavku, ne z dat služby: agent volaný mimo požadavek
    (smyčka na pozadí, test bez middleware) autonomii nemá.
    """
    if actor == "human":
        return True
    state = _CURRENT.get()
    if actor == "agent" and state is not None and state.actor == "agent" and state.authority == "human":
        state.used = True
        return True
    return False


def autonomy_active():
    """Probíhá požadavek agenta s plnou autonomií? Bez vedlejšího účinku (pro příznaky `can*`)."""
    state = _CURRENT.get()
    return state is not None and state.actor == "agent" and state.authority == "human"


def can_act(actor):
    """Příznak pro UI/agenta (`canAccept`, `canConfigure`…): stejné pravidlo jako brána, bez označení."""
    return actor == "human" or (actor == "agent" and autonomy_active())


def project_autonomy(canvas, project):
    """`{full: bool}` pro agent-state a node-brief: agent tak ví, že smí přijímat a uzavírat sám."""
    hub = getattr(canvas, "project_hub", None)
    try:
        return {"full": bool(hub and hub.agent_autonomy(project)["full"])}
    except Exception:  # noqa: BLE001 - neznámý projekt nebo chyba čtení = vypnuto
        return {"full": False}
