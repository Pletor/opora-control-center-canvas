"""Řádky `gate_tickets` (docs/brain-gate.md §4, §5): požadavky relací brány a odpovědi na ně.

`seq` je pořadí vzniku, `answered_seq` pořadí odpovědí v projektu a kurzor schránky
(lístek zodpovězený později se tak neztratí za kurzorem). `body` a `answer` jsou text JSON. Transakci vlastní volající."""
import json

COLUMNS = ("seq", "id", "project_id", "workspace_id", "session_id", "kind", "body", "status", "answer",
           "answered_by", "created_at", "answered_at", "answered_seq")


def public(row):
    """Lístek v podobě, jakou vrací API brány."""
    if row is None:
        return None
    value = dict(zip(COLUMNS, tuple(row)))
    return {"ticketId": value["id"], "seq": value["seq"], "sessionId": value["session_id"], "kind": value["kind"],
            "body": json.loads(value["body"]), "status": value["status"],
            "answer": None if value["answer"] is None else json.loads(value["answer"]),
            "answeredBy": value["answered_by"], "createdAt": value["created_at"], "answeredAt": value["answered_at"],
            "answeredSeq": value["answered_seq"]}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class GateTicketStore:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def insert(self, ticket_id, workspace, session_id, kind, body, created_at):
        """Uloží čekající lístek; vrací jeho `seq`."""
        cursor = self.db.execute(
            "INSERT INTO gate_tickets(id,project_id,workspace_id,session_id,kind,body,status,created_at)"
            " VALUES(?,?,?,?,?,?,'queued',?)",
            (ticket_id, self.project, workspace, session_id, kind, _json(body), created_at))
        return cursor.lastrowid

    def get(self, ticket_id):
        return public(self.db.execute("SELECT " + ",".join(COLUMNS) + " FROM gate_tickets WHERE project_id=? AND id=?",
                                      (self.project, ticket_id)).fetchone())

    def answer(self, ticket_id, answer, answered_by, answered_at):
        """Jednou odpoví na čekající lístek; True, když odpovědělo právě toto volání."""
        cursor = self.db.execute(
            "UPDATE gate_tickets SET status='answered', answer=?, answered_by=?, answered_at=?,"
            " answered_seq=(SELECT COALESCE(MAX(answered_seq), 0) + 1 FROM gate_tickets WHERE project_id=?)"
            " WHERE project_id=? AND id=? AND status='queued'",
            (_json(answer), answered_by, answered_at, self.project, self.project, ticket_id))
        return cursor.rowcount == 1

    def answered_after(self, session_id, after, limit):
        """Zodpovězené lístky jedné relace s `answered_seq > after`, v pořadí odpovědí.

        Lístky, které brána zodpověděla hned v požadavku (`answered_by = 'gate'`), sem nepatří: jejich odpověď
        přišla v odpovědi na požadavek a schránka by se jinak plnila vlastními dotazy (`inbox`, `state`)."""
        rows = self.db.execute(
            "SELECT " + ",".join(COLUMNS) + " FROM gate_tickets WHERE session_id=? AND answered_seq>?"
            " AND project_id=? AND answered_by<>'gate' ORDER BY answered_seq LIMIT ?",
            (session_id, after, self.project, limit)).fetchall()
        return [public(row) for row in rows]

    def queued(self, workspace, limit):
        """Čekající lístky pracovního prostoru od nejstaršího (co ještě musí zodpovědět srdce nebo člověk)."""
        rows = self.db.execute(
            "SELECT " + ",".join(COLUMNS) + " FROM gate_tickets WHERE project_id=? AND workspace_id=?"
            " AND status='queued' ORDER BY seq LIMIT ?", (self.project, workspace, limit)).fetchall()
        return [public(row) for row in rows]
