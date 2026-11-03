"""Modely OpenAPI rout brány a mozku (docs/brain-control-api.md §1.2).

Routy čtou tělo samy (`parse_body`), aby každá chyba nesla `code` a `hint` (413, 422), proto modely jen popisují
dokument OpenAPI: tělo požadavku přes `body(...)`, odpovědi přes `answers(...)`. Tvary těl druhů brány jsou
schémata z `kinds.py` (`GET /api/gate/kinds`), tady se na ně jen odkazuje.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.brain_opora.determinism.kinds import KINDS

KindName = Literal[tuple(KINDS)]  # type: ignore[valid-type]


class Refusal(BaseModel):
    """Odmítnutí: lidská zpráva, strojový kód a další krok."""

    error: str
    code: str
    hint: str


class Worker(BaseModel):
    name: str
    office: str | None = None
    floor: str | None = None


class SessionIn(BaseModel):
    project: str
    workspace: str
    worker: Worker


class SessionOut(BaseModel):
    sessionId: str
    token: str
    expiresAt: str


class GateRequestIn(BaseModel):
    kind: KindName
    body: dict[str, Any] = Field(default_factory=dict, description="Tělo podle schématu input druhu (GET /api/gate/kinds).")


class GateRequestOut(BaseModel):
    ticketId: str
    seq: int
    kind: str
    status: Literal["queued", "answered"]
    answer: Any = Field(None, description="Jen u synchronního druhu: výstup podle schématu output druhu.")


class KindCode(BaseModel):
    code: str
    hint: str


class KindOut(BaseModel):
    kind: str
    role: Literal["worker", "heart"]
    description: str
    sync: bool
    input: dict[str, Any]
    output: dict[str, Any]
    example: dict[str, Any]
    codes: list[KindCode]


class KindsOut(BaseModel):
    role: Literal["worker", "heart", "human"]
    kinds: list[KindOut]


class Ticket(BaseModel):
    ticketId: str
    seq: int
    sessionId: str
    kind: str
    body: Any
    status: Literal["queued", "answered"]
    answer: Any
    answeredBy: str | None
    createdAt: str
    answeredAt: str | None
    answeredSeq: int | None


class InboxOut(BaseModel):
    tickets: list[Ticket]
    last: int


class AnswerIn(BaseModel):
    answer: Any = Field(..., description='Libovolná hodnota JSON kromě null, například {"text": "Ano."}.')


class GateSettingIn(BaseModel):
    project: str
    enabled: bool


class GateSettingOut(BaseModel):
    project: str
    enabled: bool
    since: str | None = None
    by: str | None = None


class IntakeSettingIn(BaseModel):
    """Povolení a strop Jevu vstupní brány (docs/navrhy/2026-10-30-vstupni-brana.md §7)."""
    project: str
    jev: bool
    jevPerDay: int | None = Field(None, ge=0, le=10000, description="Chybí = beze změny (výchozí 200).")


class IntakeSettingOut(BaseModel):
    project: str
    jev: bool
    jevPerDay: int


class WorkTicketBody(BaseModel):
    """Tělo ticketu pro dělníka, bez ID (docs/navrhy/2026-11-03-novy-zaklad.md §3.3)."""

    essence: str
    build: str
    openPaths: list[str]
    cautions: list[str]
    skills: list[str]
    doneCriteria: list[str]


class WorkTicketPin(BaseModel):
    """Pin Brainu po pluginu (docs/navrhy/2026-11-03-novy-zaklad.md §3.4): zip pro `claude --plugin-dir`."""

    pin: str
    plugin: str
    version: str
    zip: str


class WorkTicketMachine(BaseModel):
    cardId: str | None
    executionId: str | None
    cardVersion: int | None
    department: str | None
    profile: str | None
    pins: list[WorkTicketPin]


class WorkTicketFeedback(BaseModel):
    feedbackId: str
    seq: int
    kind: Literal["bug", "idea", "improvement", "question"]
    text: str
    sessionId: str
    answer: Any
    answeredAt: str | None
    createdAt: str


class WorkTicket(BaseModel):
    ticketId: str
    seq: int
    workspaceId: str
    status: str
    body: WorkTicketBody
    machine: WorkTicketMachine
    sessionId: str | None
    delivery: Any
    feedback: list[WorkTicketFeedback]
    createdAt: str
    updatedAt: str


class WorkTicketsOut(BaseModel):
    tickets: list[WorkTicket]


class HeartMessageIn(BaseModel):
    project: str
    workspace: str
    text: str


class HeartMessageOut(BaseModel):
    queued: bool
    pending: int


class SnapshotOut(BaseModel):
    snapshot: str


class ContextOut(BaseModel):
    """Data dílny srdce (`ctx <name>`, docs/brain-heart.md §3b)."""
    name: str
    items: list[dict[str, Any]]


class EscalateOut(BaseModel):
    ticketId: str
    kind: str
    status: str


class WithdrawIn(BaseModel):
    project: str
    workspace: str
    reason: str


class WithdrawOut(BaseModel):
    ticketId: str
    status: str
    reason: str


class IntakeVerdictIn(BaseModel):
    """Srdce potvrdí nebo opraví stanovisko vstupu brány (docs/navrhy/2026-10-30-vstupni-brana.md §4)."""
    project: str
    workspace: str
    entry: str
    verdict: str = Field(..., description="done | extends_in_progress | fix_for_milestone | changes_intent | "
                                          "later_extension | needs_info")
    reason: str = ""
    requirement: str | None = Field(None, description="rq_… (připojit vstup k požadavku) | new (založit požadavek)")
    title: str | None = Field(None, description="Název nového požadavku (jen s requirement new).")
    openCondition: str | None = Field(None, description="Podmínka otevření odloženého požadavku (ID milníku); jen "
                                                         "later_extension, výchozí aktivní milník oblasti vstupu.")


class IntakeVerdictOut(BaseModel):
    id: str
    verdict: str
    layer: str
    areaId: str | None = None
    reason: str | None = None
    requirementId: str | None = None


class MilestoneCriterionIn(BaseModel):
    text: str
    cards: list[str] = Field(..., description="ID karet, které kritérium dokládají (splněno = všechny done.confirmed).")


class MilestoneProposalIn(BaseModel):
    """Návrh milníku srdcem (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5); aktivuje ho jen člověk."""
    project: str
    workspace: str
    area: str
    title: str
    criteria: list[MilestoneCriterionIn]


class MilestoneProposalOut(BaseModel):
    id: str
    status: str
    areaId: str
    title: str
    criteria: list[dict[str, Any]]


class MilestoneDecisionIn(BaseModel):
    """Rozhodnutí člověka o návrhu milníku (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5)."""
    project: str
    workspace: str
    milestoneId: str
    action: Literal["activate", "reject"]


class MilestoneDecisionOut(BaseModel):
    id: str
    status: str
    superseded: str | None = None


class BriefSynthesisIn(BaseModel):
    """Syntéza výslechu požadavku od srdce (docs/navrhy/2026-10-30-vyslech-srdce.md §3.3, §7)."""
    project: str
    workspace: str
    requirement: str
    synthesis: dict = Field(..., description="goal, users, parts, acceptance, outOfScope, dependencies, questions…")


class BriefSynthesisOut(BaseModel):
    requirement: str
    status: Literal["draft", "research", "grilling", "clear"]
    missing: list[str] = Field(..., description="Co chybí do jasna (§4); prázdné = clear.")


class BriefAskIn(BaseModel):
    """Otázka výslechu s doporučenou odpovědí a důvodem (§3.4); nejvýš 3 otevřené, nejvýš 3 kola."""
    project: str
    workspace: str
    requirement: str
    question: str
    recommended: str
    why: str


class BriefAskOut(BaseModel):
    requirement: str
    status: str
    question: str
    open: int
    rounds: int
    missing: list[str]


class BriefAnswerIn(BaseModel):
    """Odpověď člověka na otázku výslechu (docs/navrhy/2026-10-30-vyslech-srdce.md §7, řez 3): buď `answer`,
    nebo `accept: true` (doporučená odpověď srdce)."""
    project: str
    workspace: str
    requirement: str
    question: str = Field(..., description="ID otázky (q1…) z brief.questions v GET /api/intake.")
    answer: str | None = None
    accept: Literal[True] | None = None


class BriefAnswerOut(BaseModel):
    requirement: str
    question: str
    answer: str
    accepted: bool
    status: str
    open: int
    missing: list[str]


class BriefStartIn(BaseModel):
    """„Vyslechni mě k tomu“ (§2, řez 3): člověk ve Velínu žádá výslech k požadavku."""
    project: str
    workspace: str
    requirement: str


class BriefStartOut(BaseModel):
    requirement: str
    status: Literal["draft"]


class BriefResearchIn(BaseModel):
    """Strop rešerše požadavku (docs/navrhy/2026-10-30-vyslech-srdce.md §8): bez `costUsd` kontrola před rešerší,
    s `costUsd` přičtení ceny (a výtahu) po rešerši."""
    project: str
    workspace: str
    requirement: str
    costUsd: float | None = Field(None, ge=0, le=100)
    fragmentId: str | None = None
    digest: str | None = None
    sources: list[str] | None = None


class BriefResearchOut(BaseModel):
    requirement: str
    spentUsd: float
    capUsd: float
    leftUsd: float


class BriefSettingIn(BaseModel):
    """Výslech srdce zapnutý a strop rešerše na požadavek (docs/navrhy/2026-10-30-vyslech-srdce.md §8)."""
    project: str
    enabled: bool
    researchUsd: float | None = Field(None, ge=0, le=5, description="Chybí = beze změny (výchozí 0,30 USD).")


class BriefSettingOut(BaseModel):
    project: str
    enabled: bool
    researchUsd: float


class Escalation(BaseModel):
    ticketId: str
    text: str
    createdAt: str


class EscalationsOut(BaseModel):
    escalations: list[Escalation]


def _inline(schema, defs):
    """Schéma bez `$ref` na `$defs`: vnořené modely se vloží přímo (tělo není v components)."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            return _inline(defs[schema["$ref"].rsplit("/", 1)[-1]], defs)
        return {key: _inline(value, defs) for key, value in schema.items() if key != "$defs"}
    if isinstance(schema, list):
        return [_inline(item, defs) for item in schema]
    return schema


def body(model):
    """`openapi_extra` s tělem požadavku podle modelu (routa si ho čte sama)."""
    schema = model.model_json_schema()
    return {"requestBody": {"required": True, "content": {"application/json": {
        "schema": _inline(schema, schema.get("$defs", {}))}}}}


def answers(status, model, *errors):
    """`responses` pro OpenAPI: úspěch s modelem a odmítnutí s `Refusal`."""
    return {status: {"model": model}, **{code: {"model": Refusal} for code in errors}}
