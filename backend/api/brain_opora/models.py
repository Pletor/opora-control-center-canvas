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


class TaskBody(BaseModel):
    why: str = ""
    do: str
    files: list[str] = []
    doneWhen: list[str] = []
    dontTouch: list[dict[str, str]] = []
    context: dict[str, Any] = {}
    commit: str = ""


class TaskIn(BaseModel):
    project: str
    workspace: str
    nodeId: str | None = None
    order: int = 0
    title: str
    body: TaskBody


class Task(BaseModel):
    taskId: str
    seq: int
    workspaceId: str
    nodeId: str | None
    title: str
    body: TaskBody
    status: Literal["ready", "assigned", "done", "failed", "cancelled"]
    sessionId: str | None
    attempts: int
    createdBy: str
    report: Any
    createdAt: str
    updatedAt: str
    order: int


class TasksOut(BaseModel):
    tasks: list[Task]


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


class Escalation(BaseModel):
    ticketId: str
    text: str
    createdAt: str
    taskId: str | None = None


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
