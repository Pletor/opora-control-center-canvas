"""Evidence schválení asistenta: co čeká na člověka a co už je rozhodnuté (docs/asistent.md §5.1).

Bez vláken a bez sítě; zámek drží správce session. Rozhodnuté id si kniha pamatuje, aby druhé
rozhodnutí o stejné žádosti skončilo 409 a ne 404. Čas je z hodin správce (testy ho posouvají).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.claude_code.assistant.errors import AssistantError

RESOLVED_LIMIT = 2000


class ApprovalNotFound(AssistantError):
    status = 404


@dataclass
class Pending:
    approval_id: str
    session_id: str
    request_id: str
    tool_input: dict
    created: float
    tool: str = "Bash"
    draft: tuple | None = None  # (cesta, sha256) konceptu u `--json-file`; ověří se před povolením


class ApprovalBook:
    def __init__(self):
        self._pending = {}
        self._resolved = {}  # approval_id → session_id

    def add(self, entry):
        self._pending[entry.approval_id] = entry
        return entry

    def mark_resolved(self, approval_id, session_id):
        self._resolved[approval_id] = session_id
        while len(self._resolved) > RESOLVED_LIMIT:
            self._resolved.pop(next(iter(self._resolved)))

    def session_of(self, approval_id):
        entry = self._pending.get(approval_id)
        if entry is not None:
            return entry.session_id
        if approval_id in self._resolved:
            return self._resolved[approval_id]
        raise ApprovalNotFound("Žádost o schválení neexistuje.")

    def take(self, approval_id, session_id):
        """Vyjme čekající žádost; neznámá = 404, už rozhodnutá = 409."""
        entry = self._pending.get(approval_id)
        if entry is None or entry.session_id != session_id:
            if self._resolved.get(approval_id) == session_id:
                raise AssistantError("O této žádosti už je rozhodnuto.")
            raise ApprovalNotFound("Žádost o schválení neexistuje.")
        del self._pending[approval_id]
        self.mark_resolved(approval_id, session_id)
        return entry

    def has_pending(self, session_id):
        return any(entry.session_id == session_id for entry in self._pending.values())

    def drop_session(self, session_id):
        """Proces session skončil: všechny její čekající žádosti padají (CLI už odpověď nepřečte)."""
        dropped = [entry for entry in self._pending.values() if entry.session_id == session_id]
        for entry in dropped:
            self.take(entry.approval_id, session_id)
        return dropped

    def expired(self, now, seconds):
        """Vyjme žádosti starší než `seconds`; bez rozhodnutí platí zamítnutí."""
        old = [entry for entry in self._pending.values() if now - entry.created > seconds]
        for entry in old:
            self.take(entry.approval_id, entry.session_id)
        return old
