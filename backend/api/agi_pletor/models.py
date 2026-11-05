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
