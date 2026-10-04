"""Úložiště OporaHub: neměnné commity zadání a práce, verzované mimo git.

Krok 9 kontraktu `docs/synchronizace-pravdy.md`, část 3 „OporaHub: commity, větve, main“.
Commit patří vždy jednomu rozsahu (oblast, sektor, uzel), ukazuje na rodiče téhož rozsahu
a jeho `id` je otiskem vlastního obsahu. Pravda leží v souborech (`opora_hub_store.py`),
tabulka `opora_commits` je jen index a `rebuild_index` ji z těch souborů kdykoli postaví znovu.

Agenti do OporaHubu nezapisují: commit i merge dělá orchestrátor nebo člověk.
"""

import json
import re
from datetime import UTC, datetime, timedelta

from backend.canvas.graph import digest as graph_digest, valid_id
from backend.canvas.opora_hub_store import OporaHubStore, content_id

AUTHORS = ("human", "orchestrator", "agent")
WRITERS = ("human", "orchestrator")  # agent má svůj prostor a důkazy, historii nepíše
SCOPE_KINDS = ("area", "sector", "node")
SUBJECT_LIMIT = 200
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


def _author(by):
    """Kdo smí psát historii. Zámek proti omylu agenta, ne proti člověku."""
    if not isinstance(by, dict):
        raise ValueError("Autor commitu musí být objekt s druhem a jménem.")  # noqa: TRY004
    kind, name = by.get("kind"), by.get("name")
    if kind == "agent":
        raise ValueError(
            "Agent do OporaHubu nezapisuje; commit a merge dělá orchestrátor nebo člověk.")
    if kind not in WRITERS:
        raise ValueError("Druh autora je jen člověk (human), nebo orchestrátor (orchestrator).")
    if not isinstance(name, str) or not name.strip() or len(name) > 120 or "\0" in name:
        raise ValueError("Jméno autora musí mít 1 až 120 znaků.")
    return {"kind": kind, "name": name.strip()}


def _content(payload):
    """Ověřený obsah commitu bez rodiče a času; co projde, to se otiskne a uloží."""
    if not isinstance(payload, dict):
        raise ValueError("Obsah commitu musí být objekt.")  # noqa: TRY004
    kind, revision = payload.get("kind"), payload.get("specRevision")
    digest, subject, pair = payload.get("graphDigest"), payload.get("subject"), payload.get("pair")
    if kind not in SCOPE_KINDS:
        raise ValueError("Commit patří oblasti (area), sektoru (sector), nebo uzlu (node).")
    if type(revision) is not int or revision < 0:
        raise ValueError("Revize zadání musí být nezáporné celé číslo.")
    if not isinstance(digest, str) or not 8 <= len(digest) <= 128:
        raise ValueError("Digest grafu musí mít 8 až 128 znaků.")
    if not isinstance(subject, str) or not subject.strip() or "\0" in subject:
        raise ValueError("Předmět commitu je text 1 až 200 znaků bez nulového bajtu.")
    if len(subject) > SUBJECT_LIMIT:
        raise ValueError("Předmět commitu smí mít nejvýše 200 znaků.")
    if pair is not None and not isinstance(pair, dict):
        raise ValueError("Pár commitu je objekt s vazbou na git, nebo nic.")
    fields = {"kind": kind, "specRevision": revision, "graphDigest": digest,
              "subject": subject.strip(), "by": _author(payload.get("by")), "pair": pair}
    if "specificationSnapshot" in payload:
        snapshot = payload["specificationSnapshot"]
        if (not isinstance(snapshot, dict) or set(snapshot) != {"contextVersion", "specification"}
                or not isinstance(snapshot["contextVersion"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", snapshot["contextVersion"])
                or not isinstance(snapshot["specification"], dict)
                or snapshot["specification"].get("schema") != "opora.specification-context/1"
                or graph_digest(snapshot["specification"]) != snapshot["contextVersion"]):
            raise ValueError("Snímek zadání neodpovídá své verzi kontextu.")
        # Detached JSON content: subsequent edits to a caller's dict cannot alter the commit.
        fields["specificationSnapshot"] = json.loads(json.dumps(snapshot, ensure_ascii=False))
    return fields


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
        pid, wid, scope_id = _scope(scope)
        fields = _content(payload)
        db = self.canvas.db_for(pid)
        with db:
            db.execute("BEGIN IMMEDIATE")
            head = self.head(scope)
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
        with db:
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
        records = self.store.records(pid, wid)
        main = self.store.main_ids(pid)
        db = self.canvas.db_for(pid)
        with db:
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
