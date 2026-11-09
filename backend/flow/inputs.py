"""Native workflow command schemas shared by HTTP and finite capability adapters."""
from typing import Any, Literal
from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    eval_run_id: str | None = None


class RunIn(BaseModel):
    payload: Any = None
    node_id: str | None = None


class CanvasLogIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    canvas: Literal[2, 3, 4]
    kind: str = Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    payload: dict[str, Any] = Field(default_factory=dict)
