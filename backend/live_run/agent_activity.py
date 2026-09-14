from backend.canvas.graph import valid_id
from backend.live_run.agent_sources import redact

# Typ autora je tvrzení klienta, nikoli důkaz existence a obsahu události.
# Ruční poznámka zůstává odlišena.
_AUTHOR_TYPES = {"source_event": "unverified_source_claim", "operator_note": "unverified_note"}
# Read boundary nikdy nevrací source_trust přímo ze sloupce uloženého při zápisu:
# starší (i chybný) řádek by tak mohl navždy nést důvěru z dřívější politiky.
# Důvěra se při každém čtení znovu odvodí z author_type podle aktuální politiky výše;
# neznámý/starší author_type dostane nejkonzervativnější možnou hodnotu.
_LEGACY_UNVERIFIED_TRUST = "unverified_legacy_record"


class AgentActivityJournal:
    """Jen ke čtení: žurnál bezpečných náhledů aktivity agenta, klíčovaný ID události zdroje.

    Toto NENÍ lidský žurnál (ten vlastní jiný modul). Zápis přes API byl zrušen; tabulka
    zůstává čitelná kvůli dříve zachyceným záznamům, vždy s odlišením času zdroje a času
    příjmu a s důvěrou odvozenou při čtení.
    """

    def __init__(self, canvas):
        self.canvas = canvas

    def list_for_node(self, pid, wid, node_id):
        if not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")
        with self.canvas.lock:
            self.canvas.view(pid, wid)  # ověří existenci projektu/workspace bez odhalení interních cest
            rows = self.canvas.db_for(pid).execute(
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
