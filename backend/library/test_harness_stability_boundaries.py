"""Keep evidence thresholds and selection/causality distinctions explicit."""
import sqlite3

from backend.library.test_harness_stability import prepared as prepared  # noqa: PLC0414
from backend.library.test_harness_stability import seed
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414


def test_coverage_gate_retains_unknowns_after_twenty_verified_outcomes(prepared):
    assess, db, record, _ = prepared
    # Extend the original twenty records without duplicating their native sources.
    seed(db, 22, start=21)
    with db:
        db.execute("UPDATE harness_learning_outcomes SET outcome='unknown' WHERE execution_id='baseline-22'")
    below = assess.assess(payload(record))
    assert below["eligible"] is True and below["cohort"]["verifiedPasses"] == 21
    with db:
        db.execute("UPDATE harness_learning_outcomes SET outcome='unknown' WHERE execution_id='baseline-21'")
    above = assess.assess(payload(record))
    assert above["cohort"]["verifiedPasses"] == 20
    assert "insufficient-evidence-coverage" in above["reasons"]


def test_duplicate_enrollment_cannot_manufacture_successes(prepared):
    assess, db, record, _ = prepared
    try:
        with db:
            db.execute("INSERT INTO harness_learning_resources SELECT * FROM harness_learning_resources LIMIT 1")
    except sqlite3.IntegrityError as error:
        # The installed native learning schema rejects duplicates before the reader.
        assert "UNIQUE constraint failed: harness_learning_resources." in str(error)
        result = assess.assess(payload(record))
        assert result["eligible"] is True and result["cohort"]["verifiedPasses"] == 20
        assert result["cohort"]["executions"] == 20
        return
    result = assess.assess(payload(record))
    assert result["eligible"] is False and "native-cohort-unavailable" in result["reasons"]


def test_eligibility_never_claims_actual_task_invocation_or_causal_benefit(prepared):
    assess, _, record, _ = prepared
    result = assess.assess(payload(record))
    assert result["eligible"] is True
    assert result["evidenceBasis"] == {
        "taskOutcomes": "selected-kit-association", "taskInvocationVerified": False,
        "causalBenefitEstablished": False, "directObservation": "approved-fixture-cases-only",
    }
    assert result["promotionAllowed"] is False
