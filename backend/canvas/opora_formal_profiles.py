"""What one formal check run asserts: tool, claims, configuration and outcome per evidence kind.

`tlc`: every positive TLC config under tools/formal/*/ exhausted, every negative failed as
declared; claims mirror the positive configs (test-enforced). `lean`: the proof library in
tools/formal/lean kernel-checked and every theorem's `#print axioms` within the standard
three; claims are the proof modules, the per-theorem axiom audit rides in the configuration.
A green `formal/lean` without a complete clean audit is never `passed`. Used by
backend/canvas/opora_formal_checks.py; contract: docs/oporahub-verification.md.
"""
import hashlib
import json

TLC_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
LEAN_TOOLCHAIN = "leanprover/lean4:v4.22.0"
ALLOWED_AXIOMS = ("Classical.choice", "Quot.sound", "propext")
# (model directory, spec, positive-config names): mirrors tools/formal/*/<positive>.cfg (test-enforced).
TLC_MODELS = (
    ("oporahub-execution", "ExecutionAuthority",
     (("TypeOK", "invariant"), ("OneActiveOwner", "invariant"), ("NoUnauthorizedReceipt", "invariant"),
      ("OneReceiptPerExecution", "invariant"), ("Idempotency", "invariant"), ("MonotonicEpoch", "temporal-property"))),
    ("review-jobs", "ReviewJobs",
     (("TypeOK", "invariant"), ("RoundsCap", "invariant"), ("NoRepost", "invariant"), ("VoteThreshold", "invariant"),
      ("ApprovalBoundToHead", "invariant"), ("OneJobPerHead", "invariant"))),
    ("pr-loop", "PrLoop",
     (("TypeOK", "invariant"), ("MergeOnce", "invariant"), ("MergedWriteBack", "invariant"),
      ("OneEventPerClose", "invariant"), ("ClosedAttention", "invariant"), ("LinkedHeadKnown", "invariant"),
      ("RelinkOnNewHead", "temporal-property"), ("MergeEventuallyWritten", "temporal-property"))))
# ExecutionAuthority keeps its historical bare claim ids; newer models are prefixed.
CLAIMS = tuple((name if spec == "ExecutionAuthority" else f"{spec}-{name}", kind, folder, spec)
               for folder, spec, names in TLC_MODELS for name, kind in names)
LEAN_MODULES = ("AcceptedHead", "FieldMerge", "Votes")
TLC_FAILURES = {"positive_violation": "counterexample", "negative_not_detected": "failed",
                "wrong_violation": "failed", "runner_error": "failed"}
LEAN_FAILURES = {"forbidden_construct", "build_failed", "nonstandard_axiom", "audit_incomplete", "vectors_drift"}


def _claim(identifier, kind, statement):
    return {"id": identifier, "kind": kind, "statement": statement,
            "statementDigest": hashlib.sha256(statement.encode("utf-8")).hexdigest()}


def failures(tool, annotations):
    """Failure payloads the runners emitted as `::error title=formal/<tool> <kind>::<json>`."""
    prefix, kinds, result = f"formal/{tool} ", TLC_FAILURES if tool == "tlc" else LEAN_FAILURES, []
    for note in annotations or []:
        title = str(note.get("title") or "")
        if not title.startswith(prefix):
            continue
        try:
            payload = json.loads(note.get("message") or "")
        except ValueError:
            continue
        if isinstance(payload, dict) and payload.get("kind") in kinds:
            keys = ("model", "case", "config", "expect", "expectedInvariant", "kind", "violated") if tool == "tlc" \
                else ("kind", "theorem", "axioms", "found")
            result.append({key: payload.get(key) for key in keys if key in payload or tool == "tlc"})
    return result[:32]


def lean_audit(annotations):
    """The `::notice title=formal/lean audit::{...}` payload, or None when absent or malformed."""
    for note in annotations or []:
        if str(note.get("title") or "") != "formal/lean audit":
            continue
        try:
            payload = json.loads(note.get("message") or "")
        except ValueError:
            return None
        theorems = payload.get("theorems") if isinstance(payload, dict) else None
        if not isinstance(theorems, list) or not theorems:
            return None
        audit = {}
        for item in theorems[:400]:
            if (not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str)
                    or not (item[1] is None or isinstance(item[1], list))):
                return None
            audit[item[0][:200]] = None if item[1] is None else sorted(str(axiom)[:100] for axiom in item[1])
        return {"toolchain": str(payload.get("toolchain") or "")[:80], "ok": payload.get("ok") is True,
                "theorems": audit}
    return None


def audit_clean(audit):
    return bool(audit and audit["ok"] and audit["theorems"]
                and all(axioms is not None and set(axioms) <= set(ALLOWED_AXIOMS) for axioms in audit["theorems"].values()))


def outcome(tool, check, cases, audit=None):
    if check["conclusion"] == "success":
        if tool == "lean" and not audit_clean(audit):
            return "inconclusive"  # A build without a complete clean axiom audit is not a checked proof.
        return "passed"
    kinds = {case["kind"] for case in cases}
    if tool == "tlc" and "positive_violation" in kinds:
        return "counterexample"
    if kinds:
        return "failed"
    return {"failure": "failed", "cancelled": "cancelled"}.get(check["conclusion"], "inconclusive")


def describe(tool, check, audit=None):
    """(tool, claims, assumptions, configuration) for the verification record."""
    sha = check["headSha"]
    if tool == "tlc":
        claims = [_claim(identifier, kind, f"{identifier.split('-')[-1]} as defined in tools/formal/{folder}/{spec}.tla "
                                           f"at commit {sha}.") for identifier, kind, folder, spec in CLAIMS]
        return ({"name": "tlc", "version": "TLC2 2.19 (distribution 1.7.4), run by GitHub Actions",
                 "distributionSha256": TLC_SHA256}, claims,
                ["Model inputs are the files under tools/formal at the reported commit; bytes are not imported.",
                 "Finite abstract models; no refinement proof of the Python implementation."],
                {"mode": "exhaustive-model-checking", "cases": "tools/formal/*/cases.json",
                 "negativeConfigsMustFail": True, "fairness": ["PrLoop: WF Relink, WF WriteBack"], "axioms": []})
    theorems = (audit or {}).get("theorems") or {}
    claims = []
    for module in LEAN_MODULES:
        names = sorted(name for name in theorems if name.startswith(f"OporaHub.{module}."))
        listing = ", ".join(name.rsplit(".", 1)[-1] for name in names) or "audit not available"
        claims.append(_claim(f"OporaHub-{module}", "theorem",
                             (f"Every theorem in tools/formal/lean/OporaHub/{module}.lean at commit {sha} is "
                              f"kernel-checked and depends only on {', '.join(ALLOWED_AXIOMS)}: {listing}.")[:4000]))
    toolchain = (audit or {}).get("toolchain") or LEAN_TOOLCHAIN
    return ({"name": "lean", "version": f"{toolchain} via elan, run by GitHub Actions; distributionSha256 is the "
                                        "SHA-256 of the pinned lean-toolchain line, not of a binary",
             "distributionSha256": hashlib.sha256(f"{toolchain}\n".encode()).hexdigest()}, claims,
            ["Lean models of the pure core are separate from the Python implementation; agreement is the "
             "differential test on exported vectors, not a refinement proof.",
             "Proof files are restricted to a metaprogram-free subset (source scan before elaboration)."],
            {"mode": "kernel-checked-proofs", "toolchain": toolchain, "allowedAxioms": list(ALLOWED_AXIOMS),
             "axiomAudit": theorems, "auditComplete": audit_clean(audit), "fairness": [], "axioms": []})
