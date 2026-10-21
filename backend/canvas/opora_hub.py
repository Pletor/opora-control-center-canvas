"""Úložiště OporaHub: neměnné commity zadání a práce, verzované mimo git.

Krok 9 kontraktu `docs/synchronizace-pravdy.md`, část 3 „OporaHub: commity, větve, main“.
Commit patří vždy jednomu rozsahu (oblast, sektor, uzel), ukazuje na rodiče téhož rozsahu
a jeho `id` je otiskem vlastního obsahu. Pravda leží v souborech (`opora_hub_store.py`),
tabulka `opora_commits` je jen index a `rebuild_index` ji z těch souborů kdykoli postaví znovu.

Agenti zapisují hlídané návrhy; běžný commit i merge dělá orchestrátor nebo člověk.
"""

import re
from datetime import UTC, datetime, timedelta

from backend.canvas.graph import valid_id
from backend.canvas.opora_commit_validation import (
    AUTHORS as AUTHORS,  # noqa: PLC0414 — preserve public re-export
)
from backend.canvas.opora_commit_validation import (
    WRITERS as WRITERS,  # noqa: PLC0414 — preserve public re-export
)
from backend.canvas.opora_commit_validation import _author, _content
from backend.canvas.opora_hub_store import OporaHubStore, content_id

INSERT = "INSERT INTO opora_commits VALUES(?,?,?,?,?,?,?,?,?,?,?,?)"
COLUMNS = ("id,parent,scope_id,scope_kind,spec_revision,subject,"
           "author_kind,author_name,created_at,in_main")


def _scope(scope):
    """Rozsah commitu je trojice (projekt, pracovní prostor, rozsah); projekt ověří `db_for`."""
    if not isinstance(scope, (tuple, list)) or len(scope) != 3:
        raise ValueError("Rozsah commitu musí být trojice projekt, prostor a rozsah.")
    pid, wid, scope_id = scope
    if not isinstance(wid, str) or not wid or len(wid) > 64:
        raise ValueError("Neplatný pracovní prostor commitu.")
    if not valid_id(scope_id):
        raise ValueError("Neplatný rozsah commitu.")
    return pid, wid, scope_id


def _record(row):
    """Index podoba commitu: co potřebuje přehled. Celý obsah leží v souboru."""
    return {"id": row["id"], "parent": row["parent"],
            "scope": {"kind": row["scope_kind"], "id": row["scope_id"]},
            "specRevision": row["spec_revision"], "subject": row["subject"],
            "by": {"kind": row["author_kind"], "name": row["author_name"]},
            "createdAt": row["created_at"], "inMain": bool(row["in_main"])}


def _values(record, in_main):
    """Řádek indexu ze souboru commitu; pořadí sloupců drží `PROJECT_SCHEMA`."""
    return (record["project"], record["workspace"], record["scope"]["id"], record["id"],
            record["parent"], record["scope"]["kind"], record["specRevision"], record["subject"],
            record["by"]["kind"], record["by"]["name"], record["createdAt"], int(in_main))


def _stamp(db, key):
    """Čas commitu, vždy novější než poslední commit téhož rozsahu.

    Hrubé systémové hodiny dají dvěma zápisům za sebou stejnou hodnotu a pořadí historie
    by pak nešlo přečíst. Kolizi proto posuneme o mikrosekundu za poslední zapsaný čas.
    """
    stamp = datetime.now(UTC).isoformat(timespec="microseconds")
    row = db.execute(
        "SELECT MAX(created_at) AS last FROM opora_commits"
        " WHERE project_id=? AND workspace_id=? AND scope_id=?", key).fetchone()
    last = row["last"] if row is not None else None
    if last and last >= stamp:
        later = datetime.fromisoformat(last) + timedelta(microseconds=1)
        stamp = later.isoformat(timespec="microseconds")
    return stamp


class OporaHub:
    """Jediný vlastník tabulky `opora_commits`; soubory za něj drží `OporaHubStore`."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.store = OporaHubStore(canvas)

    def commit(self, scope, payload):
        """Zapíše commit rozsahu: nejdřív soubor (pravda), pak index. Vrací uložený commit."""
        return self._commit(scope, payload)

    def propose(self, scope, payload, *, expected_head):
        """Agent může navrhnout snímek, ale nepřijímá ho do mainu; rodič musí souhlasit."""
        if not isinstance(payload, dict):
            raise ValueError("Obsah návrhu musí být objekt.")  # noqa: TRY004 — API maps validation to HTTP 409
        if expected_head is not None and (
                not isinstance(expected_head, str) or not re.fullmatch(r"[a-f0-9]{40}", expected_head)):
            raise ValueError("Neplatná výchozí revize OporaHubu.")
        if "specificationSnapshot" not in payload:
            raise ValueError("Návrh vyžaduje neměnný snímek zadání.")
        return self._commit(scope, payload, guarded=True, expected_head=expected_head)

    def _commit(self, scope, payload, *, guarded=False, expected_head=None):
        pid, wid, scope_id = _scope(scope)
        fields = _content(payload, allow_agent=guarded)
        db = self.canvas.db_for(pid)
        with self.canvas.lock_for(pid), db:
            db.execute("BEGIN IMMEDIATE")
            head = self.head(scope)
            if guarded and (head["id"] if head else None) != expected_head:
                raise ValueError("Historie OporaHubu se změnila. Načtěte nový kontext návrhu.")
            content = {"project": pid, "workspace": wid,
                       "scope": {"kind": fields.pop("kind"), "id": scope_id},
                       "parent": head["id"] if head else None,
                       "createdAt": _stamp(db, (pid, wid, scope_id)), **fields}
            record = {"id": content_id(content), **content}
            self.store.write(pid, record)
            db.execute(INSERT, _values(record, False))
        return {**record, "inMain": False}

    def history(self, scope, limit=20):
        """Historie rozsahu, nejnovější první."""
        pid, wid, scope_id = _scope(scope)
        if type(limit) is not int or limit < 1:
            raise ValueError("Počet commitů v historii musí být kladné celé číslo.")
        rows = self.canvas.db_for(pid).execute(
            f"SELECT {COLUMNS} FROM opora_commits WHERE project_id=? AND workspace_id=?"
            " AND scope_id=? ORDER BY created_at DESC LIMIT ?",
            (pid, wid, scope_id, limit)).fetchall()
        return [_record(row) for row in rows]

    def read(self, scope, commit_id):
        """Úplný neměnný obsah; staré commity zůstávají čitelné bez nového snímku."""
        pid, wid, scope_id = _scope(scope)
        record = self.store.read(pid, commit_id)
        if record.get("project") != pid or record.get("workspace") != wid or record.get("scope", {}).get("id") != scope_id:
            raise ValueError("Commit nepatří tomuto rozsahu.")
        return {**record, "inMain": commit_id in self.store.main_ids(pid)}

    def head(self, scope):
        """Poslední commit rozsahu, ať v mainu je, nebo není."""
        return self._latest(scope, "")

    def main_of(self, scope):
        """Poslední commit rozsahu, který je v mainu."""
        return self._latest(scope, " AND in_main=1")

    def merge(self, scope, commit_id, *, by):
        """Označí commit rozsahu za součást mainu. Druhý merge téhož commitu nic nemění."""
        pid, wid, scope_id = _scope(scope)
        _author(by)
        db = self.canvas.db_for(pid)
        with self.canvas.lock_for(pid), db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"SELECT {COLUMNS} FROM opora_commits"
                " WHERE project_id=? AND workspace_id=? AND id=? AND scope_id=?",
                (pid, wid, commit_id, scope_id)).fetchone()
            if row is None:
                raise ValueError("Commit tohoto rozsahu v OporaHubu neexistuje.")
            if row["in_main"]:
                return _record(row)
            db.execute(
                "UPDATE opora_commits SET in_main=1 WHERE project_id=? AND workspace_id=? AND id=?",
                (pid, wid, commit_id))
            self.store.mark_main(pid, commit_id)
            return {**_record(row), "inMain": True}

    def rebuild_index(self, pid, wid):
        """Zahodí index prostoru a postaví ho znovu ze souborů; vrací počet commitů."""
        db = self.canvas.db_for(pid)
        with self.canvas.lock_for(pid), db:
            records = self.store.records(pid, wid)
            main = self.store.main_ids(pid)
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM opora_commits WHERE project_id=? AND workspace_id=?",
                       (pid, wid))
            db.executemany(INSERT, [_values(one, one["id"] in main) for one in records])
        return len(records)

    def _latest(self, scope, where):
        pid, wid, scope_id = _scope(scope)
        row = self.canvas.db_for(pid).execute(
            f"SELECT {COLUMNS} FROM opora_commits"
            f" WHERE project_id=? AND workspace_id=? AND scope_id=?{where}"
            " ORDER BY created_at DESC LIMIT 1", (pid, wid, scope_id)).fetchone()
        return None if row is None else _record(row)
