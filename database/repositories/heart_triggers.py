"""Řádky `heart_triggers` = „už jsem srdce budil“ (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4).

Klíč spouštěče (`trigger:milestone:<id>:done`) se zapíše jednou; `fire` vrátí True jen poprvé, takže srdce
se na stejný stav nebudí opakovaně. Transakci vlastní volající."""


class HeartTriggers:
    def __init__(self, db):
        self.db = db

    def fire(self, key, workspace, at):
        """Zapíše klíč; True = poprvé (budit), False = už budil."""
        cursor = self.db.execute("INSERT OR IGNORE INTO heart_triggers(key, workspace_id, fired_at) VALUES(?,?,?)",
                                 (key, workspace, at))
        return cursor.rowcount == 1

    def fired(self, key):
        return self.db.execute("SELECT 1 FROM heart_triggers WHERE key=?", (key,)).fetchone() is not None
