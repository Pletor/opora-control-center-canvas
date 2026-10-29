"""Zeď brány (docs/brain-gate.md §3): kdo smí zapisovat do projektu se zapnutou bránou.

`decide` je čistá funkce nad tabulkou §3: nečte nic, jen rozhodne. `check` k ní dohledá, co potřebuje
(přepínač projektu, ověření tokenu přes `tokens.verify`), a volá ji middleware `boundary` v
`backend/app/factory.py`. Projekt se bere z `project` v query nebo v těle, stejně jako `_authority`.

Projekt s vypnutou bránou zeď nevidí: `check` vrátí `ALLOW` a middleware nic nezmění.
"""
from dataclasses import dataclass

from backend.brain_opora.determinism import gate_setting, tokens

GATE_PREFIX = "/api/gate"
READS = ("GET", "HEAD")
INVALID = "invalid"  # token v hlavičce je, ale neplatí (neznámý, prošlý, zneplatněný)
GATE_HINT = "Write through the gate: POST /api/gate/requests"
# Pruh orchestrátora (docs/brain-heart-orchestrator.md §2): práce na kartě projde i bez tokenu brány.
# Plátno a pravidla dál zapisuje jen srdce a člověk. Předpona končící „-“ je rodina rout (`harness-*`),
# ostatní se porovnávají po celých segmentech.
LANE = (
    "/api/oporahub/executions",
    "/api/oporahub/process-events",
    "/api/oporahub/execution-observers",
    "/api/oporahub/harness-",
    "/api/oporahub/github-evidence",
    "/api/oporahub/review-jobs",
    "/api/oporahub/review-identities/claim",
    "/api/oporahub/verifications",
    "/api/desktop-v3/agent-output",
    "/api/desktop-v3/agent-messages",
    "/api/desktop-v3/agent-message-receipt",
    "/api/desktop-v3/agent-workspace",
    "/api/desktop-v3/lease",
)
# Relé záměru (docs/brain-heart-orchestrator.md §8): pracovník brány předá srdci zprávu člověka. Jen tahle
# přesná cesta a jen s platným tokenem pracovníka téhož projektu; kdo smí psát, ověří ještě routa.
RELAY = "/api/brain/heart/messages"


@dataclass(frozen=True)
class Verdict:
    """Rozhodnutí zdi. `heart` = srdce v projektu `project` dostane oprávnění plné autonomie."""

    allow: bool
    status: int = 200
    code: str = ""
    error: str = ""
    hint: str = ""
    heart: bool = False
    project: str = ""

    def body(self):
        return {"error": self.error, "code": self.code, "hint": self.hint}


ALLOW = Verdict(True)


def _refuse(status, code, error, hint):
    return Verdict(False, status, code, error, hint)


def _is_gate(path):
    return path == GATE_PREFIX or path.startswith(GATE_PREFIX + "/")


def in_lane(path):
    """Je cesta v pruhu? `/api/oporahub/executions/x` ano, `/api/oporahub/executionsX` ne."""
    return any(path.startswith(prefix) if prefix.endswith("-")
               else path == prefix or path.startswith(prefix + "/") for prefix in LANE)


def decide(method, path, actor, gate_on, token, project=""):
    """Tabulka §3. `token`: None (bez hlavičky), `INVALID`, nebo `{role, project}` platné relace.

    `project` je jediný projekt požadavku; když query a tělo jmenují různé projekty, je prázdný
    a token srdce pak neplatí pro „tento projekt“.
    """
    if not gate_on or actor == "human":
        return ALLOW
    heart_here = (isinstance(token, dict) and token.get("role") == "heart" and bool(project)
                  and token.get("project") == project)
    if heart_here:
        # Srdce v projektu své relace jedná s plnou autonomií, při čtení i zápisu.
        return Verdict(True, heart=True, project=project)
    if method in READS or _is_gate(path):
        # Čtení je volné; routy brány si token ověřují samy.
        return ALLOW
    if in_lane(path):
        # Pruh nepotřebuje token: bez hlavičky, s neplatným i s cizím tokenem rozhoduje jen cesta.
        return ALLOW
    if (path == RELAY and isinstance(token, dict) and token.get("role") == "worker" and bool(project)
            and token.get("project") == project):
        return ALLOW
    if token == INVALID:
        return _refuse(401, "gate_token_invalid", "Token brány je neznámý, prošlý nebo zneplatněný.",
                       "Založte novou relaci: POST /api/gate/sessions.")
    if isinstance(token, dict) and token.get("project") != project:
        return _refuse(403, "gate_scope", "Token brány platí jen pro svůj projekt.",
                       "Pro jiný projekt založte novou relaci: POST /api/gate/sessions.")
    return _refuse(403, "gate_required", "Projekt má zapnutou bránu; zapisuje jen člověk a srdce.", GATE_HINT)


def _token(service, header):
    if not header:
        return None
    session = tokens.verify(service, header)
    if session is None:
        return INVALID
    return {"role": session["role"], "project": session["project_id"]}


def _name(value):
    return value if isinstance(value, str) else ""


def relevant(method, actor, header):
    """Může zeď požadavek vůbec ovlivnit? Člověk ani čtení bez tokenu ne; levné, bez I/O."""
    return actor != "human" and (method not in READS or bool(header))


def check(service, method, path, actor, header, query_project, body_project):
    """Rozhodnutí zdi pro jeden požadavek. `body_project` je funkce: tělo se čte, jen když je třeba."""
    if not relevant(method, actor, header):
        return ALLOW
    named = {name for name in (_name(query_project), _name(body_project())) if name}
    if not any(gate_setting.is_on(service, name) for name in named):
        return ALLOW
    project = next(iter(named)) if len(named) == 1 else ""
    return decide(method, path, actor, True, _token(service, header), project)
