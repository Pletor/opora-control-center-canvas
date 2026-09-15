"""Úložiště procesů: `processes/<prc-id>/process.json` uvnitř složky projektu.

Soubor je pravda, zápis je atomický, revize chrání před souběžným přepsáním,
historie přechodů je append-only.
"""

# ruff: noqa: TRY004 — kontroly tvaru končí ValueError, který API mapuje na 409
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path

STATES = ("draft", "running", "done", "repair")
STEP_STATES = ("pending", "running", "done", "failed")
ACTOR_KINDS = ("human", "agent", "system")
OUTPUT_KINDS = ("json", "db", "md", "file")
PROCESS_ID = re.compile(r"^prc-[0-9a-f]{12}$")
STEP_ID = re.compile(r"^stp-[0-9a-f]{8}$")
REQUIRED = ("id", "projectId", "title", "state", "createdAt", "updatedAt", "revision", "owner", "inputs", "steps", "outputs", "failure", "history")
INPUT_KEYS = ("nodeText", "spec", "packet", "worktree", "references")
_PATH_LOCKS: dict[str, threading.Lock] = {}
_PATH_LOCKS_LOCK = threading.Lock()


def _path_lock(path: Path) -> threading.Lock:
    """Vrátí procesový zámek pro kanonickou cestu jednoho souboru procesu."""
    canonical_path = os.path.normcase(str(path.resolve()))
    with _PATH_LOCKS_LOCK:
        lock = _PATH_LOCKS.get(canonical_path)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[canonical_path] = lock
        return lock


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_process_id() -> str:
    return "prc-" + secrets.token_hex(6)


def new_step_id() -> str:
    return "stp-" + secrets.token_hex(4)


def actor(kind: str, name: str) -> dict:
    if kind not in ACTOR_KINDS or not name or len(name) > 120:
        raise ValueError("Neplatný aktér: druh human/agent/system a název do 120 znaků.")
    return {"kind": kind, "name": name}


def _check_actor(value, where: str):
    if not isinstance(value, dict) or value.get("kind") not in ACTOR_KINDS or not isinstance(value.get("name"), str) or not value["name"]:
        raise ValueError(f"Neplatný aktér v {where}.")


def validate(process: dict) -> None:
    """Přísná kontrola tvaru podle shared/process.schema.json (bez externí knihovny)."""
    if not isinstance(process, dict):
        raise ValueError("Proces musí být objekt.")
    missing = [key for key in REQUIRED if key not in process]
    if missing:
        raise ValueError("Procesu chybí pole: " + ", ".join(missing) + ".")
    if not PROCESS_ID.match(str(process["id"])):
        raise ValueError("Neplatné ID procesu.")
    if not isinstance(process["projectId"], str) or not process["projectId"]:
        raise ValueError("Chybí projectId.")
    if not isinstance(process["title"], str) or not process["title"].strip() or len(process["title"]) > 200:
        raise ValueError("Název procesu musí mít 1–200 znaků.")
    if process["state"] not in STATES:
        raise ValueError("Neznámý stav procesu.")
    if not isinstance(process["revision"], int) or process["revision"] < 1:
        raise ValueError("Revize musí být celé číslo od 1.")
    _check_actor(process["owner"], "owner")
    inputs = process["inputs"]
    if not isinstance(inputs, dict) or "worktree" not in inputs or not isinstance(inputs.get("references"), list):
        raise ValueError("inputs musí obsahovat worktree a references.")
    if any(key not in INPUT_KEYS for key in inputs):
        raise ValueError("inputs obsahuje neznámé pole.")
    if inputs["worktree"] is not None and not isinstance(inputs["worktree"], str):
        raise ValueError("inputs.worktree musí být id worktree nebo null.")
    if not isinstance(process["steps"], list):
        raise ValueError("steps musí být seznam.")
    seen = set()
    for step in process["steps"]:
        if not isinstance(step, dict) or not STEP_ID.match(str(step.get("id", ""))):
            raise ValueError("Krok má neplatné ID.")
        if step["id"] in seen:
            raise ValueError("Duplicitní ID kroku.")
        seen.add(step["id"])
        if step.get("state") not in STEP_STATES:
            raise ValueError("Krok má neznámý stav.")
        if not isinstance(step.get("title"), str) or not step["title"]:
            raise ValueError("Krok nemá název.")
        evidence = step.get("evidence")
        if step["state"] in ("done", "failed") and not evidence:
            raise ValueError(f"Krok {step['id']} ve stavu {step['state']} musí mít důkaz.")
        if evidence is not None:
            if not isinstance(evidence, dict) or not evidence.get("summary") or not evidence.get("at"):
                raise ValueError("Důkaz kroku musí mít summary a at.")
            _check_actor(evidence.get("by"), "evidence.by")
    if not isinstance(process["outputs"], list):
        raise ValueError("outputs musí být seznam.")
    for output in process["outputs"]:
        if not isinstance(output, dict) or output.get("kind") not in OUTPUT_KINDS or not output.get("ref"):
            raise ValueError("Výstup musí mít kind (json/db/md/file) a ref.")
    failure = process["failure"]
    if failure is not None:
        if not isinstance(failure, dict) or not failure.get("reason") or not failure.get("at"):
            raise ValueError("failure musí mít reason a at.")
        _check_actor(failure.get("reportedBy"), "failure.reportedBy")
    history = process["history"]
    if not isinstance(history, list) or not history:
        raise ValueError("history musí být neprázdný seznam.")
    for entry in history:
        if not isinstance(entry, dict) or entry.get("to") not in STATES or (entry.get("from") is not None and entry["from"] not in STATES):
            raise ValueError("Záznam historie má neplatné stavy.")
        if not entry.get("at") or "note" not in entry:
            raise ValueError("Záznam historie musí mít at a note.")
        _check_actor(entry.get("by"), "history.by")
    if history[-1]["to"] != process["state"]:
        raise ValueError("Poslední záznam historie neodpovídá stavu procesu.")


class ProcessStore:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.root = self.project_dir / "processes"

    def directory(self, process_id: str) -> Path:
        if not PROCESS_ID.match(str(process_id)):
            raise ValueError("Neplatné ID procesu.")
        return self.root / process_id

    def _file(self, process_id: str) -> Path:
        return self.directory(process_id) / "process.json"

    def create(self, title: str, owner: dict, *, by: dict, node_id: str | None = None, sector_id: str | None = None, steps=(), inputs: dict | None = None, project_id: str | None = None) -> dict:
        stamp = now()
        process = {
            "id": new_process_id(),
            "projectId": project_id or self.project_dir.name,
            "nodeId": node_id,
            "sectorId": sector_id,
            "title": title,
            "state": "draft",
            "createdAt": stamp,
            "updatedAt": stamp,
            "revision": 1,
            "owner": owner,
            "inputs": {"nodeText": None, "spec": None, "packet": None, "worktree": None, "references": [], **(inputs or {})},
            "steps": [{"id": new_step_id(), "title": step, "state": "pending", "evidence": None} for step in steps],
            "outputs": [],
            "failure": None,
            "history": [{"from": None, "to": "draft", "at": stamp, "by": by, "note": "založeno"}],
        }
        validate(process)
        target = self._file(process["id"])
        if target.exists():
            raise ValueError("Proces s tímto ID už existuje.")
        self._write(target, process)
        return process

    def get(self, process_id: str) -> dict:
        path = self._file(process_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError("Proces neexistuje.") from None

    def list(self, state: str | None = None) -> list[dict]:
        if state is not None and state not in STATES:
            raise ValueError("Neznámý stav procesu.")
        items = []
        if self.root.is_dir():
            for entry in self.root.iterdir():
                if PROCESS_ID.match(entry.name) and (entry / "process.json").is_file():
                    process = self.get(entry.name)
                    if state is None or process["state"] == state:
                        items.append(process)
        return sorted(items, key=lambda item: (item["updatedAt"], item["id"]), reverse=True)

    def save(self, process: dict, expected_revision: int) -> dict:
        validate(process)
        path = self._file(process["id"])
        with _path_lock(path):
            stored = self.get(process["id"])
            if stored["revision"] != expected_revision or process["revision"] != expected_revision:
                raise ValueError(f"Proces se mezitím změnil (revize {stored['revision']}, očekávána {expected_revision}). Načtěte ho znovu.")
            if process["history"][: len(stored["history"])] != stored["history"]:
                raise ValueError("Historie procesu je append-only; existující záznamy nelze měnit ani mazat.")
            if process["createdAt"] != stored["createdAt"] or process["projectId"] != stored["projectId"]:
                raise ValueError("createdAt a projectId procesu nelze měnit.")
            updated = {**process, "revision": expected_revision + 1, "updatedAt": now()}
            self._write(path, updated)
            return updated

    def _write(self, path: Path, process: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{secrets.token_hex(12)}.tmp")
        try:
            tmp.write_text(json.dumps(process, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
