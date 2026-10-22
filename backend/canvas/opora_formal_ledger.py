"""Proof ledger: one row per theorem / model property with its latest machine-checked status.

`GET /api/oporahub/verifications/ledger?project&workspace` lets agents see what is already
proved or model-checked (and on which SHA, with which axioms and trust) before they start
proving or modelling the same thing again. Rows come from two read-only sources:
the declared catalog in this checkout (Lean theorems under tools/formal/lean/OporaHub,
TLC claims and conformance invariants from opora_formal_profiles) and the newest CI-observed verification records.
A declared row without evidence is `unchecked`; a row seen only in evidence is
`declared: false` (renamed or removed since). Nothing here writes.
"""
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from backend.canvas import opora_formal_profiles as profiles
from backend.canvas.opora_verifications import OporaVerifications

LEAN_ROOT = Path(__file__).resolve().parents[2] / "tools" / "formal" / "lean"
SCHEMA_VERSION = 1
PASSED = {"lean": "proved", "tlc": "checked", "conformance": "checked"}


def _lean_catalog(root=LEAN_ROOT):
    script = root / "audit.py"
    if not script.is_file():
        return []
    spec = importlib.util.spec_from_file_location("opora_lean_audit", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [{"id": f"lean:{item['name']}", "tool": "lean", "kind": "theorem", "name": item["name"],
             "source": f"tools/formal/lean/{item['module'].replace('.', '/')}.lean"}
            for item in module.theorems(module.sources(root), root)]


def catalog(root=LEAN_ROOT):
    rows = _lean_catalog(root)
    rows += [{"id": f"tlc:{identifier}", "tool": "tlc", "kind": kind, "name": identifier,
              "source": f"tools/formal/{folder}/{spec}.tla"} for identifier, kind, folder, spec in profiles.CLAIMS]
    rows += [{"id": f"conformance:{name}", "tool": "conformance", "kind": "invariant", "name": name,
              "source": profiles.CONFORMANCE_TEST} for name in profiles.CONFORMANCE_INVARIANTS]
    return rows


def _status(tool, outcome, checked, axioms=None):
    if outcome == "passed" and checked and (axioms is None or set(axioms) <= set(profiles.ALLOWED_AXIOMS)):
        return PASSED[tool]
    return {"counterexample": "counterexample", "failed": "failed"}.get(outcome, "unverified")


def _evidence(record):
    """(row id, partial row) pairs one verification record vouches for."""
    report, verification = record.get("report"), record["verification"]
    if report is None:
        return []
    tool, outcome = verification["tool"]["name"], report["outcome"]
    base = {"commitSha": verification["source"]["commitSha"], "trust": record["trust"],
            "lastChecked": report["createdAt"], "verificationId": record["id"],
            "checkName": (record.get("origin") or {}).get("checkName"), "outcome": outcome}
    if tool == "lean":
        audit = verification["configuration"].get("axiomAudit") or {}
        return [(f"lean:{name}", {**base, "axioms": axioms, "status": _status("lean", outcome, True, axioms or [])
                                  if axioms is not None else "unverified"})
                for name, axioms in audit.items()]
    checked, tool = set(report["checkedClaims"]), tool if tool == "conformance" else "tlc"
    return [(f"{tool}:{claim['id']}", {**base, "axioms": [], "status": _status(tool, outcome, claim["id"] in checked)})
            for claim in verification["claims"]]


def ledger(service, project, workspace, root=LEAN_ROOT):
    records = OporaVerifications(service).history(project, workspace)["requests"]
    rows = {row["id"]: {**row, "declared": True, "status": "unchecked", "commitSha": None, "axioms": None,
                        "trust": None, "lastChecked": None, "verificationId": None, "checkName": None, "outcome": None}
            for row in catalog(root)}
    seen = set()
    for record in records:  # newest first: the first record vouching for a row wins
        for key, value in _evidence(record):
            if key in seen:
                continue
            seen.add(key)
            tool, name = key.split(":", 1)
            rows[key] = {**rows.get(key, {"id": key, "tool": tool, "kind": "theorem" if tool == "lean" else "invariant",
                                          "name": name, "source": None, "declared": False}), **value}
    entries = sorted(rows.values(), key=lambda row: row["id"])
    counts = {}
    for row in entries:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"schemaVersion": SCHEMA_VERSION, "projectId": project, "workspaceId": workspace,
            "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "allowedAxioms": list(profiles.ALLOWED_AXIOMS), "counts": counts, "entries": entries}
