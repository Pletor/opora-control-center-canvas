"""Tvary těl Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P1); frontend na ně čeká, nemění se."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.agi_pletor import tts
from backend.agi_pletor.actions import TEXT_LIMIT


class PletorMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(min_length=1, max_length=200)
    workspace: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=TEXT_LIMIT)
    voice: bool = False  # P3: zpráva vznikla hlasem nebo je zapnutý Hlas; odpověď se čte nahlas


class PletorAction(BaseModel):
    type: str
    text: str
    ok: bool
    detail: str | None = None


class PletorReplyOut(BaseModel):
    reply: str
    actions: list[PletorAction]


class PletorMessage(BaseModel):
    role: Literal["human", "pletor"]
    text: str
    at: str


class PletorBrain(BaseModel):
    brain: Literal["claude", "ollama"]
    model: str | None
    available: list[str]


class PletorStateOut(BaseModel):
    messages: list[PletorMessage]
    heart: dict[str, Any]
    escalations: list[dict[str, Any]]
    brain: PletorBrain


class PletorBrainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brain: Literal["claude", "ollama"]
    model: str | None = Field(default=None, min_length=1, max_length=200)


class PletorBrainOut(BaseModel):
    ok: bool
    reply: str
    brain: PletorBrain


class PletorSpeechIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=tts.TEXT_LIMIT)  # jedna nebo pár vět; frontend posílá po větách
    voice: str | None = Field(default=None, min_length=1, max_length=100)  # id z /voices, engine je v id


class PletorQuota(BaseModel):
    tier: str | None
    character_count: int | None
    character_limit: int | None


class PletorVoice(BaseModel):
    id: str
    label: str
    gender: Literal["male", "female"]
    engine: Literal["xtts", "elevenlabs", "edge", "piper"]
    available: bool
    reason: str | None  # proč hlas nejde (nestažený model, málo VRAM, tarif…); u dostupného None
    quota: PletorQuota | None = None  # jen ElevenLabs: znaky z tarifu uživatele


class PletorVoicesOut(BaseModel):
    voices: list[PletorVoice]


class PletorLlmOut(BaseModel):
    """Sekce z `backend/agi_pletor/llm_settings/` (každá aspoň `available`, při chybě `reason`); tvar viz README modulu."""
    claude: dict[str, Any]
    codex: dict[str, Any]
    ollama: dict[str, Any]
    cswap: dict[str, Any]


class PletorLlmClaudeIn(BaseModel):
    model: str


class PletorLlmCodexIn(BaseModel):
    model: str
    reasoning: str | None = None


class PletorLlmClaudeIn(BaseModel):
    model: str


class PletorLlmCodexIn(BaseModel):
    model: str
    reasoning: str | None = None


class LiniePreviewIn(BaseModel):
    """Náhled větve nad kopií dat projektu (docs/navrhy/2026-11-06-velin-git-linie.md §5)."""
    model_config = ConfigDict(extra="forbid")
    branch: str = Field(min_length=1, max_length=200)
    project: str = Field(min_length=1, max_length=200)


class LinieRowIn(BaseModel):
    """Řádek editoru Linie (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3); tvar ověřuje `linie/rows.py`."""
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    type: Literal["items", "work", "experiment", "fix"]
    base: dict[str, Any] | None = None
    target: str | None = Field(default=None, max_length=200)


class LinieRowPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    branch: str | None = Field(default=None, max_length=200)
    target: str | None = Field(default=None, max_length=200)
    collapsed: bool | None = None


class LinieAttachIn(BaseModel):
    """Práce Linie k ticketu: řádek, větev (agent ji založí z `baseBranch`), cíl."""
    model_config = ConfigDict(extra="forbid")
    rowId: str = Field(min_length=1, max_length=80)
    branch: str = Field(min_length=1, max_length=200)
    baseBranch: str | None = Field(default=None, max_length=200)  # chybí → rodič ze jména (linie/tree.py)
    target: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    requestId: str | None = Field(default=None, min_length=1, max_length=80)  # žádost srdci (linie/requests.py)


class LinieWorkIn(LinieAttachIn):
    """Nový ticket z editoru: tělo pro dělníka (`essence`, `build`, `doneCriteria`) ověří `ticket_model.body_payload`."""
    rowId: str | None = Field(default=None, min_length=1, max_length=80)  # chybí → řádek větve se založí sám
    title: str = Field(min_length=1, max_length=200)
    essence: str
    build: str
    doneCriteria: list[str]
    idempotencyKey: str | None = Field(default=None, min_length=1, max_length=200)


class LinieCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    status: Literal["green", "red", "pending"]


class LinieReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha: str = Field(min_length=7, max_length=40)
    checks: list[LinieCheckIn] = Field(default_factory=list, max_length=50)
    worktree: str | None = Field(default=None, max_length=500)


class LinieRunIn(BaseModel):
    """Relace LLM na úkolu; stejné `sessionId` záznam jen osvěží (heartbeat). `worktree` = explicitní vazba na adresář."""
    model_config = ConfigDict(extra="forbid")
    sessionId: str = Field(min_length=1, max_length=200)
    agent: str | None = Field(default=None, max_length=200)
    transcriptPath: str | None = Field(default=None, max_length=500)
    worktree: str | None = Field(default=None, max_length=500)


class LinieMergeIn(BaseModel):
    """Identifikátor operace začlenění (UUID); opakování se stejným `op` nic znovu neslučuje (L7 §5a)."""
    model_config = ConfigDict(extra="forbid")
    op: str | None = Field(default=None, max_length=64)


class LinieAttemptIn(BaseModel):
    """Pokus práce (L7 §7 bod 5): větev zakládá agent z `baseSha`; `baseRef` chybí → rodič ze jména."""
    model_config = ConfigDict(extra="forbid")
    branch: str = Field(min_length=1, max_length=200)
    baseRef: str | None = Field(default=None, min_length=1, max_length=200)
    baseSha: str | None = Field(default=None, min_length=7, max_length=40)
    repo: str | None = Field(default=None, max_length=500)
    agent: str | None = Field(default=None, max_length=200)
    requestId: str | None = Field(default=None, min_length=1, max_length=80)
    idempotencyKey: str | None = Field(default=None, min_length=1, max_length=200)


class LinieRevertIn(BaseModel):
    """Revert commitu na větvi úkolu; `expectedHead` = hlava, kterou volající viděl."""
    model_config = ConfigDict(extra="forbid")
    sha: str = Field(min_length=7, max_length=40)
    expectedHead: str = Field(min_length=7, max_length=40)
    op: str | None = Field(default=None, max_length=64)


class LinieRebaseNoteIn(BaseModel):
    """Evidence rebase `{from, to}`; v gitu se nic neprovádí."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    old: str = Field(alias="from", min_length=7, max_length=40)
    to: str = Field(min_length=7, max_length=40)


class PletorRequestIn(BaseModel):
    """Žádost srdci (L7 §4a); opakování se stejným klíčem vrátí tutéž žádost."""
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=TEXT_LIMIT)
    idempotencyKey: str = Field(min_length=1, max_length=200)


class PletorRequestStepIn(BaseModel):
    """Potvrzení kroku žádosti s důkazem, nebo jeho selhání (`failed`, `why`)."""
    model_config = ConfigDict(extra="forbid")
    k: Literal["plan", "ticket", "attempt", "commit"]
    evidence: dict[str, Any] | None = None
    failed: bool = False
    why: str | None = Field(default=None, max_length=2000)


class LinieAbandonIn(BaseModel):
    """Opuštěná práce: evidence rozhodnutí, git ani HEAD nemění (L7 §5)."""
    model_config = ConfigDict(extra="forbid")
    sha: str = Field(min_length=7, max_length=40)
    why: str = Field(min_length=1, max_length=2000)


class LinieDeployIn(BaseModel):
    """Událost nasazení `{env, sha}` (L7 §5); `repo` jen když je to repozitář služby."""
    model_config = ConfigDict(extra="forbid")
    env: str = Field(min_length=1, max_length=64)
    sha: str = Field(min_length=7, max_length=40)
    repo: str | None = Field(default=None, max_length=500)


class LinieAcceptIn(BaseModel):
    """Přijetí přesně aktuální hlavy ticketu (`sha == headSha`)."""
    model_config = ConfigDict(extra="forbid")
    sha: str = Field(min_length=7, max_length=40)
    note: str = Field(default="", max_length=2000)


class LinieAllowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str | None = Field(default=None, min_length=1, max_length=200)


class LinieBlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class LinieDeployedIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha: str = Field(min_length=7, max_length=40)
