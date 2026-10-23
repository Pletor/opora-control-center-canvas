"""Měřicí obal kolem skutečného backendu OPORA Canvas na dočasné datové složce.

Každé volání jde přes FastAPI TestClient do `create_app(<tmp>)`, nikdy na živou aplikaci :8740
ani do `P:/opora-data`. Obal počítá volání, bajty požadavku a odpovědi a kdo volal (agent,
člověk, office), aby obě varianty protokolu šly porovnat stejným metrem.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ORIGIN = "http://127.0.0.1:8740"
UI_SECRET = "ab-protokol-ui-secret-" + "x" * 24
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ample-3-karty.json"
NONE = {"kind": "none", "targetId": "", "note": ""}
ENV = {
    "OPORA_MAP_REFRESH_WORKER": "0", "OPORA_EXECUTION_PR_WORKER": "0", "OPORA_AUTO_REBASE_WORKER": "0",
    "OPORA_RECONCILIATION_WORKER": "0", "OPORA_UI_SECRET": UI_SECRET, "OPORA_READ_CACHE_GUARD": "1",
}
ACTORS = {
    "agent": "agent; name=sim-worker",
    "agent2": "agent; name=sim-worker-2",
    "reviewer": "agent; name=sim-reviewer",
    "planner": "agent; name=sim-planner",
    "office": "agent; name=agent-office",
}
_ID = re.compile(r"/[0-9a-f]{16,64}(?=/|$)")


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def sha(*parts):
    return hashlib.sha1(":".join(parts).encode()).hexdigest()


@contextlib.contextmanager
def isolated_env(extra=None):
    """Vypne pracovní smyčky a nastaví lidský doklad UI; po běhu vrátí prostředí, jak bylo."""
    values = {**ENV, **(extra or {})}
    before = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@dataclass
class Call:
    option: str
    card: str
    phase: str
    actor: str
    method: str
    path: str
    status: int
    request_bytes: int
    response_bytes: int


@dataclass
class Meter:
    """Jediný vstup na server; `where(card, phase)` určuje, kam se volání započítá."""
    client: object
    option: str
    calls: list = field(default_factory=list)
    card: str = "-"
    phase: str = "-"
    transcripts: dict = field(default_factory=dict)

    def where(self, card, phase):
        self.card, self.phase = card, phase
        return self

    def call(self, actor, method, path, *, params=None, body=None, headers=None, expect=(200,)):
        sent = {"origin": ORIGIN, **(headers or {})}
        if actor != "human":
            sent["X-Opora-Actor"] = ACTORS[actor]
        if method == "GET":
            response = self.client.get(path, params=params, headers=sent)
        else:
            response = self.client.post(path, params=params, json=body, headers=sent)
        payload = json.dumps(body, ensure_ascii=False).encode() if body is not None else b""
        self.calls.append(Call(self.option, self.card, self.phase, actor, method, _ID.sub("/{id}", path),
                               response.status_code, len(payload), len(response.content)))
        if actor != "human":
            self.transcripts.setdefault((self.card, self.phase, actor), []).append(response.text)
        if expect and response.status_code not in expect:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
        return response

    def read_text(self, card, phase, actor="agent"):
        return "\n".join(self.transcripts.get((card, phase, actor), []))


def new_app(data_root):
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    app = create_app(Path(data_root))
    client = TestClient(app, base_url=ORIGIN)
    client.__enter__()
    client.cookies.set("opora_ui", UI_SECRET)
    return app, client


from ab_repo import (  # noqa: F401
    LEFTOVERS,
    Repo,
    cleanup,
    final_cleanup,
    git,
    sweep_previous,
    tmpdir,
)
from ab_seed import block_id, desk_state, graph_nodes, markers, seed  # noqa: F401
