import re
import uuid
from datetime import UTC, datetime

from backend.agent_sources import redact
from backend.graph import valid_id

REQUIRED_FIELDS = {
    "project",
    "workspace",
    "nodeId",
    "sourceId",
    "runId",
    "sourceEventId",
    "sourceTimestamp",
    "kind",
    "summary",
    "authorType",
}

# Typ autora je tvrzení klienta, nikoli důkaz existence a obsahu události.
# Vazba run<->node ověřuje pouze cíl zápisu; bez ověření u adaptéru zdroje
# nesmí klient získat source_confirmed. Ruční poznámka zůstává odlišena.
_AUTHOR_TYPES = {"source_event": "unverified_source_claim", "operator_note": "unverified_note"}
# Read boundary nikdy nevrací source_trust přímo ze sloupce uloženého při zápisu:
# starší (i chybný) řádek by tak mohl navždy nést důvěru z dřívější politiky.
# Důvěra se při každém čtení znovu odvodí z author_type podle aktuální politiky výše;
# neznámý/starší author_type dostane nejkonzervativnější možnou hodnotu.
_LEGACY_UNVERIFIED_TRUST = "unverified_legacy_record"
_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,200}")
_KIND_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")


def _valid_opaque_id(value):
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


def _valid_timestamp(value):
    return value is None or (isinstance(value, str) and 1 <= len(value) <= 64)


class AgentActivityJournal:
    """Append-only žurnál bezpečných náhledů aktivity agenta, klíčovaný ID události zdroje.

    Toto NENÍ lidský žurnál (ten vlastní jiný modul); je to jen strojově vyplněný, jen ke
    čtení a k explicitnímu zachycení zdroj -> Canvas, vždy s odlišením času zdroje a
    času příjmu. Nepřepisuje se, jen se doplňuje a deduplikuje podle (scope, source_id,
    run_id, source_event_id) — scope (projekt/workspace/uzel) je součástí dedup klíče,
    aby zápis pro jeden uzel nikdy nevrátil/nezablokoval cizí uzel se stejným ID události.
    """

    def __init__(self, canvas, *, known_sources=(), bindings=None):
        self.canvas = canvas
        self.known_sources = frozenset(known_sources)
        self.bindings = bindings
        canvas.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_activity_entries(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                node_id TEXT NOT NULL, source_id TEXT NOT NULL, run_id TEXT NOT NULL,
                source_event_id TEXT NOT NULL, source_timestamp TEXT, ingest_timestamp TEXT NOT NULL,
                kind TEXT NOT NULL, summary TEXT NOT NULL,
                author_type TEXT NOT NULL, source_trust TEXT NOT NULL,
                UNIQUE(project_id, workspace_id, node_id, source_id, run_id, source_event_id)
            );
            """
        )
        canvas.db.commit()

    def capture(self, payload):
        if not isinstance(payload, dict) or set(payload) != REQUIRED_FIELDS:
            raise ValueError("Neplatný formát záznamu aktivity agenta.")
        pid, wid, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        if not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")
        if not isinstance(payload["sourceId"], str) or payload["sourceId"] not in self.known_sources:
            raise ValueError("Neznámý zdroj aktivity agenta.")
        if not _valid_opaque_id(payload["runId"]):
            raise ValueError("Neplatný identifikátor běhu.")
        if not _valid_opaque_id(payload["sourceEventId"]):
            raise ValueError("Neplatný identifikátor události zdroje.")
        if not _valid_timestamp(payload["sourceTimestamp"]):
            raise ValueError("Neplatný časový údaj zdroje.")
        if not isinstance(payload["kind"], str) or not _KIND_RE.fullmatch(payload["kind"]):
            raise ValueError("Neplatný druh záznamu aktivity.")
        author_type = payload["authorType"]
        if not isinstance(author_type, str) or author_type not in _AUTHOR_TYPES:
            raise ValueError("Neplatný typ autora záznamu aktivity.")
        source_trust = _AUTHOR_TYPES[author_type]
        summary = payload["summary"]
        if not isinstance(summary, str) or not summary:
            raise ValueError("Neplatný náhled aktivity.")
        # Redakce před persist i před response: klientský text nikdy neprochází syrový.
        summary = redact(summary)
        if len(summary) > 2000:
            raise ValueError("Neplatný náhled aktivity.")
        with self.canvas.lock, self.canvas.db:
            self.canvas.db.execute("BEGIN IMMEDIATE")
            view = self.canvas.view(pid, wid)
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení. Aktivitu nelze zapisovat.")
            graph = view["graph"]
            if not any(n["id"] == node_id for n in graph["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            if self.bindings is None or not self.bindings.is_bound(
                pid, wid, node_id, payload["sourceId"], payload["runId"], graph
            ):
                raise ValueError("Běh agenta není vázán na tento uzel ani jeho sektor.")
            existing = self.canvas.db.execute(
                """SELECT id,source_timestamp,ingest_timestamp FROM agent_activity_entries
                   WHERE project_id=? AND workspace_id=? AND node_id=?
                     AND source_id=? AND run_id=? AND source_event_id=?""",
                (pid, wid, node_id, payload["sourceId"], payload["runId"], payload["sourceEventId"]),
            ).fetchone()
            if existing is not None:
                return {
                    "entryId": existing["id"],
                    "sourceTimestamp": existing["source_timestamp"],
                    "ingestTimestamp": existing["ingest_timestamp"],
                }
            entry_id = uuid.uuid4().hex
            ingest_timestamp = datetime.now(UTC).isoformat()
            self.canvas.db.execute(
                "INSERT INTO agent_activity_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry_id,
                    pid,
                    wid,
                    node_id,
                    payload["sourceId"],
                    payload["runId"],
                    payload["sourceEventId"],
                    payload["sourceTimestamp"],
                    ingest_timestamp,
                    payload["kind"],
                    summary,
                    author_type,
                    source_trust,
                ),
            )
        return {"entryId": entry_id, "sourceTimestamp": payload["sourceTimestamp"], "ingestTimestamp": ingest_timestamp}

    def list_for_node(self, pid, wid, node_id):
        if not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")
        with self.canvas.lock:
            self.canvas.view(pid, wid)  # ověří existenci projektu/workspace bez odhalení interních cest
            rows = self.canvas.db.execute(
                """SELECT id,source_id,run_id,source_event_id,source_timestamp,ingest_timestamp,
                          kind,summary,author_type,source_trust
                   FROM agent_activity_entries WHERE project_id=? AND workspace_id=? AND node_id=?
                   ORDER BY ingest_timestamp""",
                (pid, wid, node_id),
            ).fetchall()
        return [
            {
                "entryId": r["id"],
                "sourceId": r["source_id"],
                "runId": r["run_id"],
                "sourceEventId": r["source_event_id"],
                "sourceTimestamp": r["source_timestamp"],
                "ingestTimestamp": r["ingest_timestamp"],
                "kind": r["kind"],
                "summary": redact(r["summary"]),
                "authorType": r["author_type"],
                "sourceTrust": _AUTHOR_TYPES.get(r["author_type"], _LEGACY_UNVERIFIED_TRUST),
            }
            for r in rows
        ]
