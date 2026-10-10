"""Trvalé neměnné zprávy mezi kartami, bez přenosu oprávnění nebo identity."""

import uuid

from backend.canvas.canvas_service import now
from backend.editor.agent_handoff.message_contract import (
    canonical_digest,
    message_content,
    validate_message,
    validate_receipt,
)
from backend.editor.agent_memory.desktop_v3_state import default_done

PAGE_SIZE = 30


def _message_immutable(row):
    return {
        "id": row["id"], "sequence": row["sequence"], "project": row["project_id"],
        "workspace": row["workspace_id"], "sourceNodeId": row["source_node_id"],
        "targetNodeId": row["target_node_id"], "kind": row["kind"], "body": row["body"],
        "replyToMessageId": row["reply_to_message_id"], "senderLabel": row["sender_label"],
        "createdAt": row["created_at"], "digest": row["digest"],
    }


class MessageStore:
    def __init__(self, canvas, state):
        self.canvas = canvas
        self.state = state

    def _view(self, project, workspace):
        # Contract validation deliberately runs before CanvasService discovers a foreign scope.
        validate_message({
            "project": project, "workspace": workspace, "sourceNodeId": "scope", "targetNodeId": "other",
            "kind": "handoff", "body": "scope", "replyToMessageId": None, "idempotencyKey": "scope", "senderLabel": "scope",
        })
        return self.canvas.view(project, workspace)

    def _cards(self, view):
        return {item["id"]: item for item in view["graph"]["nodes"]}

    def _closed_ids(self, project, workspace):
        """Uzavřené karty z jednoho čtení stavu. Stav má stovky kB; parsovat ho pro každou kartu
        zvlášť dělalo z výpisu zpráv O(N²) (karta P1)."""
        nodes = self.state.current(project, workspace)["state"]["nodes"]
        return {node_id for node_id, node in nodes.items() if node.get("done", default_done())["confirmed"]}

    def _assert_card(self, cards, node_id):
        if node_id not in cards:
            raise ValueError("Karta v tomto pracovním prostoru neexistuje.")

    def _assert_open_pair(self, project, workspace, view, cards, source, target):
        self._assert_card(cards, source)
        self._assert_card(cards, target)
        if view["readOnly"]:
            raise ValueError("Main je pouze pro čtení; zprávy se odesílají z pracovního prostoru.")
        if {source, target} & self._closed_ids(project, workspace):
            raise ValueError("Uzavřená karta nepřijímá ani neodesílá nové zprávy.")

    def _message(self, row):
        receipt = self.canvas.db_for(row["project_id"]).execute(
            "SELECT disposition,note,recipient_label,created_at FROM agent_message_receipts WHERE message_id=?",
            (row["id"],),
        ).fetchone()
        return {
            **_message_immutable(row),
            "identityVerified": False,
            "receipt": None if receipt is None else {
                "disposition": receipt["disposition"], "note": receipt["note"],
                "recipientLabel": receipt["recipient_label"], "identityVerified": False,
                "createdAt": receipt["created_at"],
            },
        }

    def create(self, payload):
        validate_message(payload)
        project, workspace = payload["project"], payload["workspace"]
        source, target = payload["sourceNodeId"], payload["targetNodeId"]
        content_digest = canonical_digest(message_content(payload))
        with self.canvas.graph_lock:
            view = self.canvas.view(project, workspace)
            cards = self._cards(view)
            self._assert_card(cards, source)
            self._assert_card(cards, target)
            db = self.canvas.db_for(project)
            with self.canvas.lock, db:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    "SELECT * FROM agent_messages WHERE project_id=? AND workspace_id=? AND source_node_id=? AND idempotency_key=?",
                    (project, workspace, source, payload["idempotencyKey"]),
                ).fetchone()
                if existing is not None:
                    if existing["content_digest"] != content_digest:
                        raise ValueError("Idempotency key už patří jiné neměnné zprávě.")
                    return self._message(existing)
                self._assert_open_pair(project, workspace, view, cards, source, target)
                reply_to = payload["replyToMessageId"]
                if reply_to is not None:
                    previous = db.execute(
                        "SELECT source_node_id,target_node_id FROM agent_messages WHERE id=? AND project_id=? AND workspace_id=?",
                        (reply_to, project, workspace),
                    ).fetchone()
                    if previous is None or {previous["source_node_id"], previous["target_node_id"]} != {source, target}:
                        raise ValueError("replyToMessageId musí odkazovat na zprávu stejné dvojice karet ve stejném rozsahu.")
                message_id, created_at = uuid.uuid4().hex, now()
                immutable = {
                    "id": message_id, "project": project, "workspace": workspace, "sourceNodeId": source,
                    "targetNodeId": target, "kind": payload["kind"], "body": payload["body"],
                    "replyToMessageId": reply_to, "senderLabel": payload["senderLabel"], "createdAt": created_at,
                }
                digest = canonical_digest(immutable)
                db.execute(
                    "INSERT INTO agent_messages(id,project_id,workspace_id,source_node_id,target_node_id,kind,body,reply_to_message_id,idempotency_key,sender_label,created_at,digest,content_digest) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (message_id, project, workspace, source, target, payload["kind"], payload["body"], reply_to,
                     payload["idempotencyKey"], payload["senderLabel"], created_at, digest, content_digest),
                )
                row = db.execute("SELECT * FROM agent_messages WHERE id=?", (message_id,)).fetchone()
                return self._message(row)

    def receipt(self, payload):
        validate_receipt(payload)
        project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        with self.canvas.graph_lock:
            view = self.canvas.view(project, workspace)
            cards = self._cards(view)
            self._assert_card(cards, node_id)
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení; potvrzení se zapisuje v pracovním prostoru.")
            db = self.canvas.db_for(project)
            with self.canvas.lock, db:
                db.execute("BEGIN IMMEDIATE")
                message = db.execute(
                    "SELECT * FROM agent_messages WHERE id=? AND project_id=? AND workspace_id=?",
                    (payload["messageId"], project, workspace),
                ).fetchone()
                if message is None:
                    raise ValueError("Zpráva v tomto pracovním prostoru neexistuje.")
                if message["target_node_id"] != node_id:
                    raise ValueError("Potvrdit zprávu smí pouze její adresát.")
                if message["digest"] != payload["digest"]:
                    raise ValueError("Potvrzení musí nést přesný digest převzaté zprávy.")
                existing = db.execute("SELECT * FROM agent_message_receipts WHERE message_id=?", (message["id"],)).fetchone()
                if existing is not None:
                    same = (
                        existing["disposition"] == payload["disposition"] and existing["note"] == payload["note"]
                        and existing["recipient_label"] == payload["recipientLabel"]
                    )
                    if not same:
                        raise ValueError("Zpráva už má jiné neměnné potvrzení.")
                    return self._message(message)
                # An exact immutable replay is above; only a new write is closed-card forbidden.
                if node_id in self._closed_ids(project, workspace):
                    raise ValueError("Uzavřená karta nové potvrzení nezapisuje.")
                db.execute(
                    "INSERT INTO agent_message_receipts(message_id,disposition,note,recipient_label,created_at) VALUES(?,?,?,?,?)",
                    (message["id"], payload["disposition"], payload["note"], payload["recipientLabel"], now()),
                )
                return self._message(message)

    def list(self, project, workspace, node_id, direction, before):
        if direction not in ("incoming", "outgoing"):
            raise ValueError("direction musí být incoming nebo outgoing.")
        cursor = None
        if before is not None:
            if not before.isdecimal() or len(before) > 19:
                raise ValueError("before musí být kladné celé serverové pořadí.")
            cursor = int(before)
            if not 1 <= cursor <= 9223372036854775807:
                raise ValueError("before musí být kladné celé serverové pořadí.")
        with self.canvas.graph_lock:
            # View i cíle se odvozují pod stejným zámkem jako validace karty.
            view = self._view(project, workspace)
            cards = self._cards(view)
            self._assert_card(cards, node_id)
            closed = set() if view["readOnly"] else self._closed_ids(project, workspace)
            with self.canvas.lock:
                page = self._page(project, workspace, node_id, direction, cursor)
            targets = [
                {"id": item["id"], "name": item["name"]}
                for item in view["graph"]["nodes"]
                if item["id"] != node_id and item["id"] not in closed
            ]
            return {"messages": page["messages"], "readOnly": view["readOnly"] or node_id in closed,
                    "targets": targets, "hasMore": page["hasMore"], "nextBefore": page["nextBefore"]}

    def pages(self, project, workspace, node_id):
        """První strana příchozích i odchozích zpráv pro node-brief: jeden pohled na plátno,
        stav Desktop v3 se nečte (brief nepotřebuje seznam cílů ani uzavření)."""
        with self.canvas.graph_lock:
            self._assert_card(self._cards(self._view(project, workspace)), node_id)
            with self.canvas.lock:
                return {direction: self._page(project, workspace, node_id, direction, None)
                        for direction in ("incoming", "outgoing")}

    def _page(self, project, workspace, node_id, direction, cursor):
        """Jedna strana zpráv karty (volající drží canvas.lock)."""
        column = "target_node_id" if direction == "incoming" else "source_node_id"
        conditions = "project_id=? AND workspace_id=? AND " + column + "=?"
        args = [project, workspace, node_id]
        if cursor is not None:
            conditions += " AND sequence<?"
            args.append(cursor)
        rows = self.canvas.db_for(project).execute(
            "SELECT * FROM agent_messages WHERE " + conditions + " ORDER BY sequence DESC LIMIT ?",
            (*args, PAGE_SIZE + 1),
        ).fetchall()
        has_more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        return {"messages": [self._message(row) for row in rows], "hasMore": has_more,
                "nextBefore": rows[-1]["sequence"] if has_more else None}
