"""Caller-owned policy, proposal discussion and acceptance receipt repositories."""
from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_proposal_review_validation import bounded_text, proposal_scope
from database.repositories.opora_proposal_review_records import ReviewRecords

POLICIES = "opora_acceptance_policies"
EVENTS = "opora_proposal_review_events"
RECEIPTS = "opora_acceptance_receipts"
MAX_POLICIES = 256
MAX_EVENTS = 2048


class AcceptancePolicies(ReviewRecords):
    def head(self):
        row = self.db.execute("SELECT policy_id FROM opora_acceptance_policy_refs WHERE project_id=? AND workspace_id=?", self.scope).fetchone()
        if not row:
            if self.count(POLICIES):
                raise ValueError("Acceptance policy head is missing.")
            return None
        self.read(row[0])
        return row[0]

    def read(self, record_id):
        return self.read_record(POLICIES, record_id)

    def configure(self, record, expected_head):
        result, raw, size = self.encode(POLICIES, record)
        identifier(expected_head, nullable=True)
        if self.head() != expected_head or record["parentPolicyRevision"] != expected_head:
            raise ValueError("Acceptance policy CAS head changed.")
        if self.count(POLICIES) >= MAX_POLICIES:
            raise ValueError("Acceptance policy revision bound exceeded.")
        self.quota(size)
        self.db.execute("INSERT INTO opora_acceptance_policies VALUES(?,?,?,?,?)", (*self.scope, result["id"], expected_head, raw))
        self.advance("opora_acceptance_policy_refs", "policy_id", expected_head, result["id"])
        return result


class ProposalReview(ReviewRecords):
    def __init__(self, db, project, workspace, proposal_kind, proposal_id):
        super().__init__(db, project, workspace)
        proposal_scope(proposal_kind, proposal_id)
        self.proposal = proposal_kind, proposal_id

    def head(self):
        row = self.db.execute("SELECT head_id FROM opora_proposal_review_refs WHERE project_id=? AND workspace_id=?"
                              " AND proposal_kind=? AND proposal_id=?", (*self.scope, *self.proposal)).fetchone()
        if not row:
            if self.count(EVENTS, " AND proposal_kind=? AND proposal_id=?", self.proposal):
                raise ValueError("Proposal review head is missing.")
            return None
        self.read(row[0])
        return row[0]

    def read(self, record_id):
        value = self.read_record(EVENTS, record_id)
        if (value["proposalKind"], value["proposalId"]) != self.proposal:
            raise ValueError("Proposal review event is foreign to this proposal.")
        return value

    def replay(self, key):
        bounded_text(key, 128)
        row = self.db.execute("SELECT id FROM opora_proposal_review_events WHERE project_id=? AND workspace_id=?"
                              " AND proposal_kind=? AND proposal_id=? AND idempotency_key=?", (*self.scope, *self.proposal, key)).fetchone()
        return self.read(row[0]) if row else None

    def events(self):
        count = self.count(EVENTS, " AND proposal_kind=? AND proposal_id=?", self.proposal)
        if count > MAX_EVENTS:
            raise ValueError("Proposal review event bound exceeded.")
        head, result, seen = self.head(), [], set()
        while head is not None:
            if head in seen or len(result) >= MAX_EVENTS:
                raise ValueError("Proposal review chain is cyclic or oversized.")
            seen.add(head)
            value = self.read(head)
            result.append(value)
            head = value["parentReviewEvent"]
        if len(result) != count:
            raise ValueError("Proposal review chain is incomplete.")
        return list(reversed(result))

    def append(self, record, expected_head):
        result, raw, size = self.encode(EVENTS, record)
        identifier(expected_head, nullable=True)
        if (record["proposalKind"], record["proposalId"]) != self.proposal or record["parentReviewEvent"] != expected_head:
            raise ValueError("Proposal review append scope or parent mismatch.")
        previous = self.replay(record["idempotencyKey"])
        if previous:
            comparable = lambda value: {key: item for key, item in value.items() if key not in {"id", "createdAt"}}
            if comparable(previous) != comparable(record):
                raise ValueError("Proposal review idempotency key conflict.")
            return previous
        if self.head() != expected_head:
            raise ValueError("Proposal review CAS head changed.")
        if self.count(EVENTS, " AND proposal_kind=? AND proposal_id=?", self.proposal) >= MAX_EVENTS:
            raise ValueError("Proposal review event bound exceeded.")
        self.quota(size)
        self.db.execute("INSERT INTO opora_proposal_review_events VALUES(?,?,?,?,?,?,?,?)",
                        (*self.scope, *self.proposal, result["id"], expected_head, record["idempotencyKey"], raw))
        self.advance("opora_proposal_review_refs", "head_id", expected_head, result["id"],
                     extra=" AND proposal_kind=? AND proposal_id=?", params=self.proposal,
                     insert_columns="proposal_kind,proposal_id,", insert_values=self.proposal)
        return result


class AcceptanceReceipts(ReviewRecords):
    def read(self, accepted_revision):
        identifier(accepted_revision)
        row = self.db.execute("SELECT id FROM opora_acceptance_receipts WHERE project_id=? AND workspace_id=? AND accepted_revision=?",
                              (*self.scope, accepted_revision)).fetchone()
        if not row:
            return None
        record = self.read_record(RECEIPTS, row[0])
        if record["acceptedRevision"] != accepted_revision:
            raise ValueError("Acceptance receipt revision mismatch.")
        return record

    def insert(self, record):
        result, raw, size = self.encode(RECEIPTS, record)
        previous = self.read(record["acceptedRevision"])
        if previous:
            if previous != result:
                raise ValueError("Acceptance receipt immutable identity conflict.")
            return previous
        self.quota(size)
        self.db.execute("INSERT INTO opora_acceptance_receipts VALUES(?,?,?,?,?)", (*self.scope, record["acceptedRevision"], result["id"], raw))
        return result
