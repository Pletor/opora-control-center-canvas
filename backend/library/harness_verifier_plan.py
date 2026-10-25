"""Server configuration and optional accepted-plan binding; no worker chooses an executor."""
import importlib
import os
import re

from backend.canvas.graph import digest
from backend.canvas.opora_change_validation import scope
from backend.library.harness_scope_config import select


def configuration(project=None, workspace=None):
    raw = os.environ.get("OPORA_HARNESS_VERIFIER", "")
    if not raw:
        raise ValueError("Harness server verifier is disabled.")
    return select(raw, _configuration, project, workspace)


def _configuration(value):
    if set(value) != {"project", "workspace", "image", "maxExperiments"}:
        raise ValueError("Invalid Harness verifier configuration.")
    scope(value)
    if type(value["maxExperiments"]) is not int or not 0 <= value["maxExperiments"] <= 1000:
        raise ValueError("Harness maxExperiments must be an integer from 0 to 1000.")
    if not isinstance(value["image"], str) or not re.fullmatch(r"node@sha256:[a-f0-9]{64}", value["image"]):
        raise ValueError("Harness verifier requires a pinned Node image.")
    return value


def resolver():
    # Independent main-based PR: older installations explicitly lack this capability.
    try:
        return importlib.import_module("backend.library.harness_paired_plan").accepted_plan
    except ModuleNotFoundError as error:
        if error.name != "backend.library.harness_paired_plan":
            raise
        raise ValueError("Accepted Harness paired-plan support is unavailable.") from None


def prepare(record, reference):
    if digest(record.get("assignment")) != record.get("assignmentDigest"):
        raise ValueError("Accepted assignment digest does not match.")
    pinned = resolver()(record, reference)
    document = next(d for d in record["assignment"]["documents"] if d.get("nodeId") == record["nodeId"])
    resources = document["fields"]["harness"]["resources"]
    return {**pinned, "contents": {side: next(r["content"] for r in resources if r["resource"] == pinned[side]["id"])
                                   for side in ("baseline", "candidate")}}
