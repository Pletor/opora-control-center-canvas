"""Řádky `tickets` a `ticket_feedback` (docs/navrhy/2026-11-03-novy-zaklad.md §3.3): ticket jako jednotka práce.

Ticket nese tělo pro dělníka bez ID (`body`, JSON), strojovou vrstvu (`card_id`, `execution_id`, `card_version`),
držitele (`session_id`) a odevzdání (`delivery`, JSON). Položky zpětné vazby mají vlastní řádky s ID a odpovědí srdce.
Otázkové lístky leží dál v `gate_tickets`. Změna stavu je compare-and-set na starý stav; které přechody smí, říká
`backend/brain_opora/determinism/ticket_model.py`. Transakci vlastní volající."""
import json

COLUMNS = ("seq", "id", "project_id", "workspace_id", "status", "body", "card_id", "execution_id", "card_version",
           "session_id", "delivery", "created_at", "updated_at")
FEEDBACK = ("seq", "id", "ticket_id", "kind", "text", "session_id", "answer", "answered_at", "created_at")
HELD = ("claimed", "in_progress", "needs_answer", "delivered")  # stavy, ve kterých ticket drží relace dělníka


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value):
    return None if value is None else json.loads(value)


def public_feedback(row):
    value = dict(zip(FEEDBACK, tuple(row)))
    return {"feedbackId": value["id"], "seq": value["seq"], "kind": value["kind"], "text": value["text"],
            "sessionId": value["session_id"], "answer": _load(value["answer"]), "answeredAt": value["answered_at"],
            "createdAt": value["created_at"]}


def public(row, feedback=()):
    """Ticket v podobě, jakou vrací API: tělo, strojová vrstva a zpětná vazba odděleně."""
    if row is None:
        return None
    value = dict(zip(COLUMNS, tuple(row)))
    return {"ticketId": value["id"], "seq": value["seq"], "workspaceId": value["workspace_id"],
            "status": value["status"], "body": json.loads(value["body"]),
            "machine": {"cardId": value["card_id"], "executionId": value["execution_id"],
                        "cardVersion": value["card_version"]},
            "sessionId": value["session_id"], "delivery": _load(value["delivery"]),
            "feedback": [public_feedback(item) for item in feedback],
            "createdAt": value["created_at"], "updatedAt": value["updated_at"]}


class TicketStore:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def _select(self, where, args):
        rows = self.db.execute("SELECT " + ",".join(COLUMNS) + " FROM tickets WHERE project_id=? AND " + where,
                               (self.project, *args)).fetchall()
        return [public(row, self._feedback(dict(zip(COLUMNS, tuple(row)))["id"])) for row in rows]

    def _feedback(self, ticket_id):
        return self.db.execute("SELECT " + ",".join(FEEDBACK) + " FROM ticket_feedback WHERE project_id=?"
                               " AND ticket_id=? ORDER BY seq", (self.project, ticket_id)).fetchall()

    def insert(self, ticket_id, workspace, status, body, machine, at):
        self.db.execute(
            "INSERT INTO tickets(id,project_id,workspace_id,status,body,card_id,execution_id,card_version,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (ticket_id, self.project, workspace, status, _json(body), machine.get("cardId"),
             machine.get("executionId"), machine.get("cardVersion"), at, at))

    def get(self, ticket_id):
        found = self._select("id=?", (ticket_id,))
        return found[0] if found else None

    def move(self, ticket_id, old, new, at, *, session_id=None, delivery=None, execution_id=None):
        """Stav `old` → `new` (compare-and-set); `session_id` / `delivery` / `execution_id` jen když nejsou None.
        True = změněno."""
        cursor = self.db.execute(
            "UPDATE tickets SET status=?, updated_at=?, session_id=COALESCE(?, session_id),"
            " delivery=COALESCE(?, delivery), execution_id=COALESCE(?, execution_id)"
            " WHERE project_id=? AND id=? AND status=?",
            (new, at, session_id, None if delivery is None else _json(delivery), execution_id, self.project,
             ticket_id, old))
        return cursor.rowcount == 1

    def unclaim(self, ticket_id, at):
        """`claimed` → `issued` bez držitele a bez vazby na exekuci (`ticket.release`); True = změněno."""
        cursor = self.db.execute(
            "UPDATE tickets SET status='issued', updated_at=?, session_id=NULL, execution_id=NULL"
            " WHERE project_id=? AND id=? AND status='claimed'", (at, self.project, ticket_id))
        return cursor.rowcount == 1

    def by_execution(self, execution_id):
        """Nejnovější ticket navázaný na exekuci, nebo None."""
        found = self._select("execution_id=? ORDER BY seq DESC LIMIT 1", (execution_id,))
        return found[0] if found else None

    def held_by(self, session_id):
        """Nejstarší ticket, který relace drží (claimed až delivered), nebo None."""
        marks = ",".join("?" * len(HELD))
        found = self._select(f"session_id=? AND status IN ({marks}) ORDER BY seq LIMIT 1", (session_id, *HELD))
        return found[0] if found else None

    def oldest_issued(self, workspace):
        found = self._select("workspace_id=? AND status='issued' ORDER BY seq LIMIT 1", (workspace,))
        return found[0] if found else None

    def list(self, workspace, status=None, limit=200):
        """Tickety prostoru od nejstaršího, volitelně jen v jednom stavu."""
        if status:
            return self._select("workspace_id=? AND status=? ORDER BY seq LIMIT ?", (workspace, status, limit))
        return self._select("workspace_id=? ORDER BY seq LIMIT ?", (workspace, limit))

    def for_card(self, workspace, card, limit=10):
        """Nejnovější tickety karty (`card_id`) v prostoru, nejnovější první (stopa práce karty)."""
        return self._select("workspace_id=? AND card_id=? ORDER BY seq DESC LIMIT ?", (workspace, card, limit))

    def add_feedback(self, feedback_id, ticket_id, kind, text, session_id, at):
        self.db.execute("INSERT INTO ticket_feedback(id,project_id,ticket_id,kind,text,session_id,created_at)"
                        " VALUES(?,?,?,?,?,?,?)", (feedback_id, self.project, ticket_id, kind, text, session_id, at))

    def feedback(self, feedback_id):
        row = self.db.execute("SELECT " + ",".join(FEEDBACK) + " FROM ticket_feedback WHERE project_id=? AND id=?",
                              (self.project, feedback_id)).fetchone()
        if row is None:
            return None
        return {**public_feedback(row), "ticketId": dict(zip(FEEDBACK, tuple(row)))["ticket_id"]}

    def answer_feedback(self, feedback_id, answer, at):
        """Jednou odpoví na položku zpětné vazby; True, když odpovědělo právě toto volání."""
        cursor = self.db.execute("UPDATE ticket_feedback SET answer=?, answered_at=? WHERE project_id=? AND id=?"
                                 " AND answer IS NULL", (_json(answer), at, self.project, feedback_id))
        return cursor.rowcount == 1

    def open_questions(self, ticket_id):
        return self.db.execute("SELECT COUNT(*) FROM ticket_feedback WHERE project_id=? AND ticket_id=?"
                               " AND kind='question' AND answer IS NULL", (self.project, ticket_id)).fetchone()[0]
