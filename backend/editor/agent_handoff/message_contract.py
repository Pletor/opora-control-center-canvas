"""Striktní kontrakt neměnných adresovaných zpráv (opora.agent-message/1)."""

import hashlib
import json

from backend.canvas.graph import valid_id

KINDS = ("handoff", "question", "answer", "blocker", "result", "correction")
DISPOSITIONS = ("accepted", "rejected", "needs_clarification")
MAX_BODY = 12000
MAX_LABEL = 120
MESSAGE_KEYS = {
    "project", "workspace", "sourceNodeId", "targetNodeId", "kind", "body",
    "replyToMessageId", "idempotencyKey", "senderLabel",
}
RECEIPT_KEYS = {
    "project", "workspace", "nodeId", "messageId", "digest", "disposition", "note", "recipientLabel",
}


def _fail(message):
    raise ValueError("Neplatná zpráva agenta: " + message)


def _id(value, label, *, project=False):
    if not isinstance(value, str) or (project and value != "draft" and not valid_id(value)) or (not project and not valid_id(value)):
        _fail(f"{label} má neplatný identifikátor.")
    return value


def _text(value, label, limit, *, required=True):
    if not isinstance(value, str) or "\0" in value or len(value) > limit or (required and not value.strip()):
        _fail(f"{label} musí být neprázdný text do {limit} znaků bez NUL.")
    return value


def validate_message(payload):
    if not isinstance(payload, dict) or set(payload) != MESSAGE_KEYS:
        _fail("očekávám přesně project, workspace, sourceNodeId, targetNodeId, kind, body, replyToMessageId, idempotencyKey a senderLabel.")
    _id(payload["project"], "project", project=True)
    _id(payload["workspace"], "workspace")
    source = _id(payload["sourceNodeId"], "sourceNodeId")
    target = _id(payload["targetNodeId"], "targetNodeId")
    if source == target:
        _fail("sourceNodeId a targetNodeId musí být různé karty.")
    if payload["kind"] not in KINDS:
        _fail("kind musí být handoff, question, answer, blocker, result nebo correction.")
    _text(payload["body"], "body", MAX_BODY)
    reply_to = payload["replyToMessageId"]
    if reply_to is not None:
        _id(reply_to, "replyToMessageId")
    _id(payload["idempotencyKey"], "idempotencyKey")
    _text(payload["senderLabel"], "senderLabel", MAX_LABEL)
    return payload


def validate_receipt(payload):
    if not isinstance(payload, dict) or set(payload) != RECEIPT_KEYS:
        _fail("očekávám přesně project, workspace, nodeId, messageId, digest, disposition, note a recipientLabel.")
    _id(payload["project"], "project", project=True)
    _id(payload["workspace"], "workspace")
    _id(payload["nodeId"], "nodeId")
    _id(payload["messageId"], "messageId")
    digest = payload["digest"]
    if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        _fail("digest musí být SHA-256 v malých hexadecimálních znacích.")
    if payload["disposition"] not in DISPOSITIONS:
        _fail("disposition musí být accepted, rejected nebo needs_clarification.")
    _text(payload["note"], "note", MAX_BODY, required=payload["disposition"] != "accepted")
    _text(payload["recipientLabel"], "recipientLabel", MAX_LABEL)
    return payload


def canonical_digest(value):
    """SHA-256 kanonického JSON neměnného obsahu, bez receiptu."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def message_content(payload):
    """Verze pro idempotenci: přesný klientský obsah bez serverového ID a času."""
    return {key: payload[key] for key in sorted(MESSAGE_KEYS)}
