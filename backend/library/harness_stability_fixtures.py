"""Revalidate retained server reports for one exact accepted comparison and fault plan."""
import hashlib
import json
import re

from backend.canvas.graph import digest
from backend.library import harness_verifier_records as records
from backend.library.harness_verifier_quarantine import FAILURES


def read(db, project, workspace, pinned, image):
    problem, candidate = pinned["plan"]["problem"], pinned["candidate"]
    bad = db.execute(FAILURES + "SELECT COUNT(*) FROM classified WHERE NOT bound OR "
                     "(problem=? AND candidate=? AND digest=?)",
                     (project, workspace, problem, candidate["id"], candidate["digest"])).fetchone()[0]
    rows = db.execute("SELECT q.id,q.record,r.record FROM opora_verification_requests q"
                      " LEFT JOIN opora_verification_reports r ON r.verification_id=q.id"
                      " AND r.project_id=q.project_id AND r.workspace_id=q.workspace_id"
                      " WHERE q.project_id=? AND q.workspace_id=?"
                      " AND json_extract(q.record,'$.origin.kind')=?"
                      " AND json_extract(q.record,'$.origin.problem')=?"
                      " AND json_extract(q.record,'$.origin.candidate.id')=?"
                      " AND json_extract(q.record,'$.origin.candidate.digest')=? ORDER BY q.id LIMIT 1001",
                      (project, workspace, records.KIND, problem, candidate["id"], candidate["digest"])).fetchall()
    if bad or len(rows) > 1000:
        return {"complete": False, "reason": "quarantined-or-history-incomplete", "reports": []}
    proofs = []
    for identifier, raw, report_raw in rows:
        request = json.loads(raw)
        origin = request["origin"]
        if origin.get("baseline") != pinned["baseline"] or origin.get("plan") != pinned["resource"] or origin.get("image") != image:
            continue
        if report_raw is None:
            return {"complete": False, "reason": "comparison-pending", "reports": []}
        report = json.loads(report_raw)
        try:
            if (request["domain"] != "harness-fixtures" or origin["protocol"] != "harness.server-fixtures/1"
                    or request["id"] != identifier or (request["project"], request["workspace"]) != (project, workspace)
                    or any(request[key] != origin["execution"][key] for key in records.BINDING)
                    or any(request.get(key) != value for key, value in records.PENDING.items())):
                raise ValueError("Invalid request binding")
            identity = {k: v for k, v in origin.items() if k != "kind"}
            if request["requestDigest"] != digest(identity):
                raise ValueError("Invalid request digest")
            observed = report["paired"]
            expected = records.report(request, observed, True)
            # createdAt is not part of the immutable observation digest.
            if any(report.get(k) != v for k, v in expected.items() if k != "createdAt"):
                raise ValueError("Invalid server report")
            trials = observed["trials"]
            cases = pinned["plan"]["cases"]
            if any(type(observed[k]) is not int for k in ("plannedTrials", "observedTrials", "unknownPairs", "regressions", "improvements")):
                raise ValueError("Invalid comparison counters")
            if (observed["complete"] is not True or observed["cleanupComplete"] is not True
                    or observed["plannedTrials"] != 2 * len(cases) or request["plannedTrials"] != len(trials)
                    or observed["observedTrials"] != len(trials) or len(trials) != 2 * len(cases)
                    or observed["unknownPairs"] != 0 or report["outcome"] != "passed"):
                raise ValueError("Incomplete comparison")
            improvements = 0
            for index, case in enumerate(cases):
                expected_output = hashlib.sha256(case["expectedStdout"].encode("utf-8")).hexdigest()
                pair = trials[2 * index:2 * index + 2]
                sides = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
                for offset, trial in enumerate(pair):
                    if (trial["case"] != case["id"] or trial["side"] != sides[offset]
                            or trial["order"] != 2 * index + offset + 1 or trial["outcome"] not in ("pass", "fail")
                            or type(trial["exitCode"]) is not int or not 0 <= trial["exitCode"] <= 255
                            or trial["exitCode"] in (125, 126, 127)):
                        raise ValueError("Invalid trial")
                    output = trial["outputDigest"]
                    if not isinstance(output, str) or not re.fullmatch(r"[a-f0-9]{64}", output):
                        raise ValueError("Invalid output digest")
                    passed = trial["exitCode"] == 0 and output == expected_output
                    reason = "expected-output" if passed else "output-mismatch" if trial["exitCode"] == 0 else "nonzero-exit"
                    if trial["outcome"] != ("pass" if passed else "fail") or trial["reason"] != reason:
                        raise ValueError("Trial contradicts observed output")
                b = next(t for t in pair if t["side"] == "baseline")
                c = next(t for t in pair if t["side"] == "candidate")
                if c["outcome"] != "pass":
                    raise ValueError("Candidate failure")
                improvements += b["outcome"] == "fail"
            if observed["regressions"] != 0 or observed["improvements"] != improvements:
                raise ValueError("Invalid comparison totals")
            proofs.append({"verificationId": identifier, "reportDigest": report["reportDigest"]})
        except (KeyError, TypeError, ValueError, StopIteration):
            return {"complete": False, "reason": "comparison-invalid-or-inconclusive", "reports": []}
    return {"complete": bool(proofs), "reason": None if proofs else "comparison-missing", "reports": proofs}
