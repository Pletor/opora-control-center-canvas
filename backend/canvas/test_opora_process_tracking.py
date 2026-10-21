"""Local immutable GitHub observations remain workspace-wide and revision-labelled."""
from backend.canvas.opora_process_tracking import tracking
from backend.canvas.opora_reconciliation import OporaReconciliation
from backend.canvas.test_opora_reconciliation import (
    reconciliation_project as reconciliation_project,  # noqa: PLC0414
)
from backend.canvas.test_opora_review_fixtures import HUMAN
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_project,  # noqa: PLC0414
)


def test_existing_local_review_and_subscription_never_imply_card_or_merge_authority(reconciliation_project):
    service, scope, payload = reconciliation_project
    enrolled = OporaReconciliation(service).enroll(payload, HUMAN)
    db = service.db_for(scope["project"])
    before = list(db.iterdump()), db.total_changes
    result = tracking(db, scope["project"], scope["workspace"], payload["expectedAcceptedHead"])
    assert result["scope"] == "workspace"
    assert result["items"][0]["bindingId"] == enrolled["binding"]["id"]
    assert result["items"][0]["matchesCurrentRevision"]
    assert result["reviews"][0]["matchesCurrentRevision"]
    assert "nodeId" not in str(result) and "mergeAllowed" not in str(result)
    old = tracking(db, scope["project"], scope["workspace"], "f" * 40)
    assert not old["items"][0]["matchesCurrentRevision"]
    assert not old["reviews"][0]["matchesCurrentRevision"]
    assert old["reviews"][0]["freshness"] == "stale"
    assert before == (list(db.iterdump()), db.total_changes)
