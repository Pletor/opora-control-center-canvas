"""Kanál odpovědi agenta: append-only soubory `processes/<prc-id>/reports/<čas>-<agent>.json`.

Odpověď se uloží vždy, běžící proces se nepřerušuje. Podle druhu odpovědi se pak promítne do
process.json: hotový krok dostane důkaz, selhání přepne proces do opravy, výsledek přidá výstupy.
"""

# ruff: noqa: TRY004 — kontroly tvaru končí ValueError, který API mapuje na 409
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import UTC, datetime

from backend.editor.process.process_lifecycle import mark_step, transition
from backend.editor.process.process_store import OUTPUT_KINDS, ProcessStore, now

KINDS = ("progress", "step_done", "step_failed", "question", "result")
REPORT_ID = re.compile(r"^rpt-[0-9a-f]{12}$")
SYSTEM = {"kind": "system", "name": "process_reports"}


def _stamp_for_name() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.casefold()).strip("-")[:40] or "agent"


class ProcessReports:
    def __init__(self, store: ProcessStore):
        self.store = store

    def directory(self, process_id: str):
        return self.store.directory(process_id) / "reports"

    def list(self, process_id: str) -> list[dict]:
        folder = self.directory(process_id)
        if not folder.is_dir():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]

    def submit(self, process_id: str, payload: dict) -> dict:
        """Uloží odpověď a promítne ji do procesu. Vrací {report, process}."""
        process = self.store.get(process_id)
        report = self._validate(process, payload)
        folder = self.directory(process_id)
        folder.mkdir(parents=True, exist_ok=True)
        sequence = len(list(folder.glob("*.json"))) + 1
        path = folder / f"{sequence:05d}-{_stamp_for_name()}-{_slug(report['by']['name'])}-{report['id'][-6:]}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        report["file"] = path.name
        updated = self._apply(process, report)
        if updated is not process:
            updated = self.store.save(updated, expected_revision=process["revision"])
        return {"report": report, "process": updated}

    def _validate(self, process: dict, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Odpověď musí být objekt.")
        kind = payload.get("kind")
        if kind not in KINDS:
            raise ValueError("Druh odpovědi musí být progress, step_done, step_failed, question nebo result.")
        by = payload.get("by")
        if not isinstance(by, dict) or by.get("kind") not in ("human", "agent", "system") or not by.get("name"):
            raise ValueError("Odpověď musí mít autora (by).")
        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
            raise ValueError("Shrnutí odpovědi musí mít 1–4000 znaků.")
        revision = payload.get("processRevision")
        if not isinstance(revision, int) or revision < 1:
            raise ValueError("processRevision musí být revize procesu, kterou agent četl.")
        step_id = payload.get("stepId")
        if kind in ("step_done", "step_failed") and not any(step["id"] == step_id for step in process["steps"]):
            raise ValueError("Odpověď ke kroku musí uvádět existující stepId.")
        error = payload.get("error")
        if kind == "step_failed" and (not isinstance(error, str) or not error.strip()):
            raise ValueError("Selhání kroku musí mít popis chyby (error).")
        outputs = payload.get("outputs", [])
        if not isinstance(outputs, list) or len(outputs) > 200:
            raise ValueError("outputs musí být seznam do 200 položek.")
        for item in outputs:
            if not isinstance(item, dict) or item.get("kind") not in OUTPUT_KINDS or not item.get("ref"):
                raise ValueError("Výstup musí mít kind (json/db/md/file) a ref.")
        context = payload.get("context") or {}
        if not isinstance(context, dict):
            raise ValueError("context musí být objekt.")
        return {
            "id": "rpt-" + secrets.token_hex(6),
            "processId": process["id"],
            "processRevision": revision,
            "at": now(),
            "by": {"kind": by["kind"], "name": str(by["name"])[:120]},
            "context": {
                "worktree": context.get("worktree", process["inputs"].get("worktree")),
                "lastStepId": context.get("lastStepId", step_id),
                "session": context.get("session"),
            },
            "kind": kind,
            "stepId": step_id,
            "summary": summary.strip(),
            "outputs": [{"kind": o["kind"], "ref": o["ref"], "digest": o.get("digest")} for o in outputs],
            "error": error.strip() if isinstance(error, str) and error.strip() else None,
            "stale": revision != process["revision"],
        }

    def _apply(self, process: dict, report: dict) -> dict:
        kind = report["kind"]
        evidence = {"summary": report["summary"], "at": report["at"], "by": report["by"], "reportId": report["id"], "outputs": [o["ref"] for o in report["outputs"]]}
        if kind == "step_done":
            updated = mark_step(process, report["stepId"], "done", evidence)
            return {**updated, "outputs": updated["outputs"] + report["outputs"]}
        if kind == "step_failed":
            failure = {"reason": report["error"], "stepId": report["stepId"], "reportedBy": report["by"], "reportId": report["id"]}
            if process["state"] == "running":
                return transition(process, "repair", by=SYSTEM, note=f"step_failed v odpovědi {report['id']}", failure=failure)
            updated = mark_step(process, report["stepId"], "failed", evidence)
            return {**updated, "failure": {**failure, "at": report["at"], "fix": (process.get("failure") or {}).get("fix")}}
        if kind == "result":
            return {**process, "outputs": process["outputs"] + report["outputs"]}
        return process
