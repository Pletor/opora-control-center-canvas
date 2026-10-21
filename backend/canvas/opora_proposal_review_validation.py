"""Typed scope-bound policy, discussion and acceptance evidence records."""
import re

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_review_policy_validation import timestamp
from backend.editor.node.drawings import _json_safe

PROPOSAL_KINDS = {"spec", "graph-addition", "graph-change", "content"}
RISKS = {"standard", "elevated", "critical"}
COMMON = {"schemaVersion", "kind", "project", "workspace", "by", "createdAt"}


def bounded_text(value, maximum, *, empty=False):
    if not isinstance(value, str) or len(value) > maximum or "\0" in value or (not empty and not value.strip()):
        raise ValueError("Invalid bounded proposal review text.")


def proposal_scope(kind, proposal_id):
    if kind not in PROPOSAL_KINDS:
        raise ValueError("Unsupported proposal review kind.")
    identifier(proposal_id)


def _common(record, kind, keys, *, human=False):
    _json_safe(record)
    if not isinstance(record, dict) or set(record) - {"id"} != COMMON | keys or record.get("kind") != kind:
        raise ValueError("Invalid proposal review record fields.")
    if type(record["schemaVersion"]) is not int or record["schemaVersion"] != 1:
        raise ValueError("Unsupported proposal review schema.")
    scope(record)
    if "id" in record:
        identifier(record["id"])
    if not isinstance(record["by"], dict) or set(record["by"]) != {"kind", "name"}:
        raise ValueError("Invalid proposal review actor fields.")
    author = _author(record["by"], allow_agent=True)
    if author["kind"] not in ({"human"} if human else {"human", "agent"}):
        raise ValueError("Proposal review actor is not permitted.")
    bounded_text(record["createdAt"], 80)
    timestamp(record["createdAt"])


def validate_policy(record):
    _common(record, "acceptance-policy", {"parentPolicyRevision", "enabled", "rules"}, human=True)
    identifier(record["parentPolicyRevision"], nullable=True)
    if type(record["enabled"]) is not bool:
        raise ValueError("Acceptance policy enabled must be boolean.")
    rules = record["rules"]
    if (not isinstance(rules, dict) or set(rules) != {"requireAcknowledgementFrom", "blockOpenFindings"}
            or rules["requireAcknowledgementFrom"] not in RISKS | {"none"}
            or type(rules["blockOpenFindings"]) is not bool):
        raise ValueError("Invalid acceptance policy rules.")


def validate_event(record):
    event = record.get("type") if isinstance(record, dict) else None
    extra = {"comment": {"message", "anchor"}, "finding": {"message", "anchor", "severity"},
             "resolve": {"targetEventId", "resolution", "reason"},
             "ack": {"policyId", "risk", "riskDigest", "parentAcceptedHead", "reviewHead"}}
    if event not in extra:
        raise ValueError("Unsupported proposal review event.")
    _common(record, "proposal-review-event", {"proposalKind", "proposalId", "parentReviewEvent", "idempotencyKey", "type"} | extra[event],
            human=event in {"resolve", "ack"})
    proposal_scope(record["proposalKind"], record["proposalId"])
    identifier(record["parentReviewEvent"], nullable=True)
    bounded_text(record["idempotencyKey"], 128)
    if any(ord(char) < 32 for char in record["idempotencyKey"]):
        raise ValueError("Invalid proposal review idempotency key.")
    if event in {"comment", "finding"}:
        bounded_text(record["message"], 8000)
        anchor = record["anchor"]
        if anchor is not None:
            bounded_text(anchor, 2048, empty=True)
            if (anchor and not anchor.startswith("/")) or re.search(r"~(?![01])", anchor):
                raise ValueError("Invalid proposal review JSON pointer.")
    if event == "finding" and record["severity"] not in {"info", "warning", "blocking"}:
        raise ValueError("Invalid proposal finding severity.")
    if event == "resolve":
        identifier(record["targetEventId"])
        if record["resolution"] not in {"resolved", "accepted"}:
            raise ValueError("Invalid finding resolution.")
        bounded_text(record["reason"], 8000)
    if event == "ack":
        identifier(record["policyId"])
        identifier(record["parentAcceptedHead"], nullable=True)
        identifier(record["reviewHead"], nullable=True)
        if not isinstance(record["riskDigest"], str) or not re.fullmatch(r"[a-f0-9]{64}", record["riskDigest"]):
            raise ValueError("Invalid risk acknowledgement digest.")
        if record["risk"] not in RISKS or record["reviewHead"] != record["parentReviewEvent"]:
            raise ValueError("Risk acknowledgement must bind the preceding review head.")


def validate_receipt(record):
    _common(record, "acceptance-receipt", {"acceptedRevision", "proposalKind", "proposalId", "policyId", "risk", "reasons", "reviewHead", "ackId", "bootstrap"}, human=True)
    identifier(record["acceptedRevision"])
    identifier(record["policyId"])
    identifier(record["reviewHead"], nullable=True)
    identifier(record["ackId"], nullable=True)
    if type(record["bootstrap"]) is not bool or record["risk"] not in RISKS:
        raise ValueError("Invalid acceptance receipt risk or bootstrap marker.")
    if record["bootstrap"]:
        if record["proposalKind"] is not None or record["proposalId"] is not None or record["reviewHead"] is not None or record["ackId"] is not None or record["policyId"] is None:
            raise ValueError("Bootstrap evidence cannot approve a proposal review.")
    else:
        proposal_scope(record["proposalKind"], record["proposalId"])
    if not isinstance(record["reasons"], list) or not 1 <= len(record["reasons"]) <= 32:
        raise ValueError("Acceptance receipt requires bounded risk reasons.")
    for reason in record["reasons"]:
        bounded_text(reason, 2000)
