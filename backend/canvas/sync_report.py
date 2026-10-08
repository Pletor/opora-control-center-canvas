"""Sběr podkladů pro echo a verdikt Oracle: čte graf, zadání, soubory a historii gitu.

Report nikam nezapisuje a nic nespouští. Skládá svět pro `sync_signals.evaluate`:
rozsahy z grafu, revize zadání, stav cest na disku, páry z `commit_pairs`, commity
mainu bez páru, pracovní prostory a rozbité odkazy v dokumentaci. Kontrakt je
`docs/synchronizace-pravdy.md`, části 4, 6, 7 a 8.

Důkaz kroku a zelený běh testů už report čte (kroky 7 a 11 kontraktu): `evidenceComplete`
stojí na hotovém procesu rozsahu, `checksGreen` na zaznamenaném zeleném běhu u commitu
z páru. Rozsah bez obojího dál dostane echo `evidence-missing` a `checks-unknown`.
"""

from datetime import UTC, datetime
import threading
from weakref import WeakValueDictionary
from backend.canvas.read_cache import ReadCache, database_stamp

from backend.canvas import areas, commit_pairs, sync_evidence
from backend.canvas.check_runs import CheckRuns
from backend.canvas.opora_hub import OporaHub
from backend.canvas.project_folder import ProjectFolder
from backend.canvas.sync_signals import evaluate
from backend.editor.process.process_store import ProcessStore

LINKABLE = ("area", "sector", "node")


class SyncReport:
    """Jediné místo, které pro Oracle sbírá důkazy; vše ostatní jsou čisté funkce."""

    def __init__(self, service, doc_issues=None, check_runs=None):
        self.service = service
        # Běhy kontrol si report vyrobí sám ze služby; router si je pak vezme od něj.
        self.check_runs = check_runs or CheckRuns(service)
        # OporaHub verzuje zadání; bez commitu je zadání jen rozepsané.
        self.hub = OporaHub(service)
        # V testech se kontrola dokumentace nahrazuje; jinak se čte skutečný strom.
        self._doc_issues = doc_issues
        self._history_cache = ReadCache(limit=32)
        self._history_guard = threading.Lock()
        self._history_locks = WeakValueDictionary()

    def report(self, pid, wid):
        view = self.service.view(pid, wid)
        nodes = view["graph"]["nodes"]
        root = self._root(pid, wid)
        main_head = sync_evidence.main_head(root)
        commits = self._history(pid, wid, root, main_head, view["digest"])
        # SQLite spojení služby je sdílené mezi vlákny; čtení proto drží její zámek,
        # git a disk zůstávají mimo něj, ať souběžný report nikoho neblokuje.
        with self.service.lock:
            rows = self.service.db.execute(
                "SELECT id, node_id, branch, base_sha FROM workspaces WHERE project_id=?",
                (pid,),
            ).fetchall()
        workspaces = sync_evidence.workspaces_from(rows, root, main_head)
        by_node = {row["nodeId"]: row for row in workspaces if row["nodeId"]}
        done = self._done_scopes(pid)
        with self.service.lock:
            scopes = [self._scope(pid, wid, node, done, nodes)
                      for node in nodes if node["kind"] in LINKABLE]
        pairs, owned_all = self._pairs(scopes, nodes, commits, by_node)
        with self.service.lock:
            self._mark_checks(pid, wid, scopes, pairs)
        state = {
            "observedAt": datetime.now(UTC).isoformat(),
            "gitHead": main_head,
            "scopes": scopes,
            "paths": sync_evidence.path_facts(self.service.workspace_sources, root, scopes),
            "pairs": pairs,
            "unclaimedCommits": self._unclaimed(commits, owned_all),
            "workspaces": workspaces,
            "orphanSpecs": self._orphan_specs(pid, wid, {scope["id"] for scope in scopes}),
            "docIssues": self._doc_issues if self._doc_issues is not None else sync_evidence.doc_issues(root),
        }
        result = evaluate(state)
        return {
            "project": pid,
            "workspace": wid,
            "observedAt": state["observedAt"],
            "gitHead": main_head,
            "signals": result["signals"],
            "verdicts": result["verdicts"],
            "counts": _counts(result),
        }

    def _history(self, pid, wid, root, head, graph_digest):
        # Cachuje se nákladná historie, nikoli verdikt: disk a dokumentace jsou vždy živé.
        with self.service.lock:
            revision = (database_stamp(self.service.db), database_stamp(self.service.db_for(pid)))
        key, stamp = (pid, wid), (str(root), head, graph_digest, revision)
        # Single-flight jen pro konkrétní scope; mrtvé klíče nezůstávají v mapě.
        with self._history_guard:
            lock = self._history_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._history_locks[key] = lock
        with lock:
            cached = self._history_cache.get(key, stamp)
            if cached is not None:
                return cached
            return self._history_cache.put(key, stamp, sync_evidence.commits_in_main(root, head))

    def _root(self, pid, wid):
        try:
            return self.service.workspace_sources.root(pid, wid)
        except (ValueError, OSError):
            return None



    def _scope(self, pid, wid, node, done, nodes):
        spec = self.service.specs.read((pid, wid, node["id"]))
        return {
            "kind": node["kind"],
            "id": node["id"],
            "name": node.get("name") or "",
            "parentId": node.get("parentId"),
            # Členství v oblasti je geometrické, ne odkazem; počítá ho `areas.area_of`.
            "areaId": (areas.area_of(node, nodes) or {}).get("id"),
            "sourceRef": node.get("sourceRef"),
            "specRevision": spec["revision"],
            "specSavedAt": spec.get("saved_at"),
            "evidenceComplete": node["id"] in done,
            "checksGreen": False,  # doplní `_mark_checks`, až jsou známé páry
            "specCommitted": self._committed(pid, wid, node["id"], spec["revision"]),
            "closed": False,
        }

    def _committed(self, pid, wid, scope_id, revision):
        """Je tahle revize zadání zapsaná commitem OporaHubu?

        Rozsah bez zadání (revize 0) nemá co commitovat, takže platí za vyřízený.
        """
        if not revision:
            return True
        try:
            head = self.hub.head((pid, wid, scope_id))
        except (ValueError, OSError):
            return False
        return bool(head and head.get("specRevision", 0) >= revision)

    def _done_scopes(self, pid):
        """Rozsahy, které mají aspoň jeden proces ve stavu `done`.

        Uzavření procesu do `done` už dnes vyžaduje důkaz u každého kroku
        (`backend/editor/process/process_lifecycle.py:12-18`), takže hotový proces je
        sám o sobě důkazem; report jednotlivé kroky znovu nekontroluje a o ten invariant
        se opírá. Chybějící nebo nečitelná složka projektu report neshodí, jen nedá nic.
        """
        try:
            items = ProcessStore(ProjectFolder(self.service.root, pid).path).list("done")
        except (ValueError, OSError):
            return set()
        return {item.get("nodeId") for item in items if item.get("nodeId")}

    def _mark_checks(self, pid, wid, scopes, pairs):
        """Zelený běh platí jen u rozsahu, jehož pár nese commit se stejným SHA.

        Bez páru nemá běh k čemu patřit; `checksGreen` proto zůstane nepravda. Zapsané
        SHA smí být zkrácené, pokud je předponou spárovaného commitu.
        """
        runs = self.check_runs.latest_for_project(pid, wid)
        for scope in scopes:
            run = runs.get(scope["id"])
            if run is None or run["status"] != "green":
                continue
            paired = (pairs.get(scope["id"]) or {}).get("gitCommits") or []
            scope["checksGreen"] = any(str(sha).startswith(run["sha"]) for sha in paired)

    def _orphan_specs(self, pid, wid, known):
        """Zadání a texty, které přežily svůj uzel.

        Uzel se stejným id by je tiše zdědil, proto se hlásí. Mazání uzlu je dnes
        neuklízí (`backend/editor/node/removals.py`), takže je aspoň vidět.
        """
        try:
            with self.service.lock:
                db = self.service.db_for(pid)
                rows = db.execute(
                    "SELECT DISTINCT node_id FROM node_spec_revisions"
                    " WHERE project_id=? AND workspace_id=?"
                    " UNION SELECT DISTINCT node_id FROM node_text_revisions"
                    " WHERE project_id=? AND workspace_id=?",
                    (pid, wid, pid, wid),
                ).fetchall()
        except Exception:  # noqa: BLE001 — chybějící databáze nesmí shodit pozorování
            return []
        return sorted({row[0] for row in rows if row[0] and row[0] not in known})

    def _pairs(self, scopes, nodes, commits, by_node):
        pairs, owned_all = {}, set()
        # Oblast nikdy není rodičem, takže podle grafu nevlastní nic. Vlastní ale to,
        # co leží uvnitř ní na plátně; bez toho by k ní pár nemohl vzniknout a zadání
        # oblasti by navždy hlásilo, že kód chybí.
        members = {}
        for scope in scopes:
            if scope.get("areaId"):
                members.setdefault(scope["areaId"], []).append(scope["id"])
        for scope in scopes:
            if scope["kind"] == "area":
                owned = sorted({path for member in members.get(scope["id"], [])
                                for path in commit_pairs.owned_paths(member, nodes)})
            else:
                owned = commit_pairs.owned_paths(scope["id"], nodes)
            owned_all.update(owned)
            workspace = by_node.get(scope["id"])
            pair = commit_pairs.pair_for_scope(
                scope={"kind": scope["kind"], "id": scope["id"]},
                spec_revision=scope["specRevision"],
                spec_saved_at=scope["specSavedAt"],
                workspace=None if workspace is None else {
                    "branch": workspace["branch"],
                    "base_sha": workspace["baseSha"],
                    "node_id": workspace["nodeId"],
                },
                commits=commits,
                owned=owned,
            )
            pairs[scope["id"]] = pair
        return pairs, owned_all

    def _unclaimed(self, commits, owned_all):
        """Commity, které sáhly do kódu, jejž nevlastní žádný rozsah.

        Párování podle cest by jinak každý commit nad vlastněnou cestou rovnou spárovalo
        a echo by nikdy nevzniklo. Užitečná otázka zní obráceně: který kód se mění, aniž
        by k němu kdokoli držel zadání.
        """
        owned = [tuple(path.split("/")) for path in owned_all if path]
        found = []
        for commit in commits:
            loose = [path for path in commit["paths"]
                     if not any(tuple(path.split("/"))[: len(own)] == own for own in owned)]
            if loose:
                found.append({"sha": commit["sha"], "paths": loose, "date": commit["date"]})
        return found





def _counts(result):
    verdicts = result["verdicts"]
    return {
        "signals": len(result["signals"]),
        "high": sum(1 for signal in result["signals"] if signal["severity"] == "high"),
        "green": sum(1 for verdict in verdicts if verdict["state"] == "green"),
        "waiting": sum(1 for verdict in verdicts if verdict["state"] == "waiting"),
    }
