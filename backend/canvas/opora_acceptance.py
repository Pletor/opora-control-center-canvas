"""Human acceptance changes raw node specs and accepted reference in one SQLite transaction."""
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_changesets import OporaChangesets, stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_graph_records import preserved_manifest
from backend.canvas.opora_proposal_acceptance_guard import guard, seal


class OporaAcceptance:
    def __init__(self, service):
        self.service = service
        self.changesets = OporaChangesets(service)

    def accept(self, proposal_id, payload, by):
        by = _author(by)
        if by["kind"] != "human":
            raise ValueError("Návrh zadání přijímá člověk.")
        pid, wid = scope(payload)
        expected = payload.get("expectedAcceptedHead")
        identifier(expected)
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            repo = self.changesets.repository(pid, wid)
            previous = repo.db.execute("SELECT id FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? AND proposal_id=?",
                                       (pid, wid, proposal_id)).fetchone()
            if previous:
                repo.read(proposal_id, proposal=True)
                return repo.read(previous[0])
            current = self.changesets.context(pid, wid)
            if current["readOnly"]:
                raise ValueError("Pracovní prostor je jen pro čtení.")
            repo = self.changesets.repository(pid, wid)
            proposal = repo.read(proposal_id, proposal=True)
            if current["acceptedHead"] != expected or proposal["parentRevision"] != expected:
                raise ValueError("Přijatá revize se změnila; návrh vyžaduje přenos na nového rodiče.")
            if current["graphDigest"] != proposal["graphDigest"]:
                raise ValueError("Graf se změnil; návrh nelze přijmout.")
            live = {item["nodeId"]: item for item in current["documents"]}
            accepted = {item["nodeId"]: item for item in current["acceptedDocuments"]}
            for change in proposal["changes"]:
                observed = {"nodeId": change["nodeId"], "ownerWorkspace": change["ownerWorkspace"],
                            "revision": change["expectedRevision"], "fields": change["before"]}
                if (live.get(change["nodeId"]) != observed
                        or accepted.get(change["nodeId"]) != change["acceptedBefore"]):
                    raise ValueError("Zadání dotčené karty se změnilo; návrh nelze přijmout.")
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                if repo.head() != expected:
                    raise ValueError("Přijatá revize se změnila.")
                authorization = guard(repo.db, pid, wid, "spec", proposal_id)
                for change in proposal["changes"]:
                    saved = self.service.specs.save_in_transaction(
                        (pid, change["ownerWorkspace"], change["nodeId"]),
                        change["expectedRevision"], change["fields"])
                    accepted[change["nodeId"]] = {"nodeId": change["nodeId"],
                                                   "ownerWorkspace": change["ownerWorkspace"],
                                                   "revision": saved["revision"], "fields": saved["fields"]}
                result = repo.insert({"project": pid, "workspace": wid, "kind": "acceptance",
                                      "parentRevision": expected, "proposalId": proposal_id,
                                      "subject": proposal["subject"], "by": by, "createdAt": stamp(),
                                      "documents": [accepted[key] for key in sorted(accepted)],
                                      **preserved_manifest(repo, expected)})
                repo.advance(expected, result["id"])
                seal(repo.db, pid, wid, authorization, result)
            return result
