"""Public request receipts must remain scoped and cannot expose internal worker fields."""
import re

from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_review_policy_validation import timestamp
from database.repositories.opora_reconciliation_job_validation import ERROR_CODES

JOB_KEYS = {"bindingId", "generation", "state", "nextAttemptAt", "leaseUntil", "consecutiveFailures",
            "lastErrorCode", "lastAttemptId", "lastObservationId", "lastEventId", "providerRetryUntil"}


def validate_receipt(result):
    try:
        binding, control, job = result["binding"], result["control"], result["job"]
        if (not isinstance(job, dict) or set(job) != JOB_KEYS or job["bindingId"] != binding["id"]
                or job["generation"] != control["generation"] or type(job["generation"]) is not int
                or job["state"] != ("scheduled" if control["enabled"] else "paused")
                or type(job["consecutiveFailures"]) is not int or job["consecutiveFailures"] < 0):
            raise ValueError("Invalid stored reconciliation receipt.")
        if job["lastErrorCode"] is not None and job["lastErrorCode"] not in ERROR_CODES:
            raise ValueError("Invalid stored receipt error code.")
        for key in ("nextAttemptAt", "leaseUntil", "providerRetryUntil"):
            if job[key] is not None:
                timestamp(job[key])
        for key in ("lastObservationId", "lastEventId"):
            identifier(job[key], nullable=True)
        attempt = job["lastAttemptId"]
        if attempt is not None and (not isinstance(attempt, str) or re.fullmatch(r"[a-f0-9]{32}", attempt) is None):
            raise ValueError("Invalid stored receipt attempt.")
        return result
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Malformed stored reconciliation receipt.") from error
