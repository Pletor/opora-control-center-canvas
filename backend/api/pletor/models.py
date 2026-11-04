"""Tvary těl Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P1); frontend na ně čeká, nemění se."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.pletor.actions import TEXT_LIMIT


class PletorMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(min_length=1, max_length=200)
    workspace: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=TEXT_LIMIT)


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
