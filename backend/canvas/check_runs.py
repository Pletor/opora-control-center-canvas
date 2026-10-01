"""Zaznamenaný běh kontrol u jednoho commitu: aplikace testy nespouští, jen zapisuje výsledek.

Krok 11 kontraktu `docs/synchronizace-pravdy.md`. Bránu 1:1 otevírá až zelený běh
zapsaný u páru; bez něj drží echo `checks-unknown`. Kdo testy spustil (člověk, CI,
agent ve svém prostoru), sem pošle hotový výsledek. Aplikace žádný běh nezahajuje
a žádný model nevolá.

Zápis je append-only: oprava je nový záznam s vlastním časem, nikdy přepis staršího.
Rozhoduje nejnovější záznam rozsahu, historie zůstává čitelná.
"""

import re
from datetime import UTC, datetime, timedelta

from backend.canvas.graph import valid_id

STATUSES = ("green", "red")
SHA = re.compile(r"[0-9a-f]{7,64}")
DETAIL_LIMIT = 2000
COLUMNS = "scope_id,sha,status,detail,recorded_at"


class CheckRuns:
    """Jediný vlastník tabulky `check_runs` ve složce projektu; čte ji a píše, nevytváří."""

    def __init__(self, canvas):
        self.canvas = canvas

    def record(self, scope, payload):
        """Zapíše jeden běh; vrací uložený záznam. Starší záznamy zůstávají beze změny."""
        pid, wid, scope_id = _scope(scope)
        status, sha, detail = _entry(payload)
        db = self.canvas.db_for(pid)
        with db:
            db.execute("BEGIN IMMEDIATE")
            recorded_at = _free_stamp(db, (pid, wid, scope_id))
            db.execute(
                "INSERT INTO check_runs VALUES(?,?,?,?,?,?,?)",
                (pid, wid, scope_id, sha, status, detail, recorded_at),
            )
        return {"scopeId": scope_id, "sha": sha, "status": status,
                "detail": detail, "recordedAt": recorded_at}

    def latest(self, scope):
        """Nejnovější záznam rozsahu, nebo None, když rozsah žádný běh nemá."""
        pid, wid, scope_id = _scope(scope)
        row = self.canvas.db_for(pid).execute(
            f"SELECT {COLUMNS} FROM check_runs WHERE project_id=? AND workspace_id=? AND scope_id=?"
            " ORDER BY recorded_at DESC LIMIT 1",
            (pid, wid, scope_id),
        ).fetchone()
        return None if row is None else _record(row)

    def latest_for_project(self, pid, wid):
        """`{scope_id: nejnovější záznam}` pro celý projekt; jedno čtení pro celý report."""
        rows = self.canvas.db_for(pid).execute(
            f"SELECT {COLUMNS} FROM check_runs WHERE project_id=? AND workspace_id=?"
            " ORDER BY recorded_at ASC",
            (pid, wid),
        ).fetchall()
        # Řazení vzestupně: pozdější záznam téhož rozsahu přepíše dřívější.
        return {row["scope_id"]: _record(row) for row in rows}


def _record(row):
    return {"scopeId": row["scope_id"], "sha": row["sha"], "status": row["status"],
            "detail": row["detail"], "recordedAt": row["recorded_at"]}


def _scope(scope):
    """Rozsah běhu je trojice (projekt, pracovní prostor, rozsah); projekt ověří `db_for`."""
    if not isinstance(scope, (tuple, list)) or len(scope) != 3:
        raise ValueError("Rozsah běhu musí být trojice projekt, prostor a rozsah.")
    pid, wid, scope_id = scope
    if not isinstance(wid, str) or not wid or len(wid) > 64:
        raise ValueError("Neplatný pracovní prostor běhu kontrol.")
    if not valid_id(scope_id):
        raise ValueError("Neplatný rozsah běhu kontrol.")
    return pid, wid, scope_id


def _entry(payload):
    if not isinstance(payload, dict):
        raise ValueError("Běh kontrol musí být objekt.")  # noqa: TRY004 — API to mapuje na 409
    status = payload.get("status")
    if status not in STATUSES:
        raise ValueError("Výsledek běhu je jen zelený (green), nebo červený (red).")
    sha = payload.get("sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("SHA commitu musí mít 7 až 64 znaků z rozsahu 0-9 a a-f.")
    detail = payload.get("detail") or ""
    if not isinstance(detail, str) or len(detail) > DETAIL_LIMIT or "\0" in detail:
        raise ValueError("Popis běhu je text nejvýše 2000 znaků.")
    return status, sha, detail


def _free_stamp(db, key):
    """Čas záznamu, vždy novější než poslední běh téhož rozsahu.

    Hrubé systémové hodiny dají dvěma zápisům za sebou stejnou hodnotu; pořadí
    append-only by pak nešlo přečíst a klíč tabulky by se srazil. Kolizi proto
    posuneme o mikrosekundu za poslední zapsaný čas rozsahu.
    """
    stamp = datetime.now(UTC).isoformat(timespec="microseconds")
    row = db.execute(
        "SELECT MAX(recorded_at) AS last FROM check_runs"
        " WHERE project_id=? AND workspace_id=? AND scope_id=?",
        key,
    ).fetchone()
    last = row["last"] if row is not None else None
    if last and last >= stamp:
        later = datetime.fromisoformat(last) + timedelta(microseconds=1)
        stamp = later.isoformat(timespec="microseconds")
    return stamp
