"""Import immutable read-only GitHub evidence without holding locks across the network."""
from datetime import UTC, datetime

from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_review_scope import context, validate_request
from backend.canvas.opora_review_status import evaluate
from backend.integrations.github_review_reader import GitHubReviewReader
from backend.integrations.github_review_transport import GitHubReadError
from database.repositories.opora_review_evidence import ReviewEvidenceRepository


class OporaReviewEvidence:
    def __init__(self, service, reader=None):
        self.service = service
        self.reader = reader or GitHubReviewReader()

    def repository(self, pid, wid):
        return ReviewEvidenceRepository(self.service.db_for(pid), pid, wid)

    @staticmethod
    def _check(current, payload):
        if not current["available"]:
            raise ValueError(current["unavailableReason"])
        if current["acceptedHead"] != payload["expectedAcceptedHead"]:
            raise ValueError("Přijatá revize se změnila. Obnovte kontext.")

    def observe(self, payload, by):
        pid, wid = validate_request(payload)
        by = _author(by, allow_agent=True)
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            before = context(self.service, pid, wid)
            self._check(before, payload)
        # No graph/project/registry locks are held during any remote request.
        try:
            data = self.reader.read(before["repository"], payload["prNumber"])
        except GitHubReadError:
            data = {"complete": False, "errorCode": "github-observation-unavailable",
                    "observedAt": datetime.now(UTC).isoformat()}
        if data.get("complete") is True and (
                    data["repository"]["fullName"].casefold() != before["repository"]
                    or data["pr"]["number"] != payload["prNumber"]
                    or data["pr"]["baseRef"] != before["config"]["branch"]
                    or ("expectedHeadSha" in payload and data["pr"]["headSha"] != payload["expectedHeadSha"])):
            raise ValueError("PR, cílová větev nebo SHA neodpovídá požadovanému projektu.")
        content = {**data, "schemaVersion": 1, "project": pid, "workspace": wid,
                   "acceptedRevision": before["acceptedHead"], "initiatedBy": by,
                   "configuredRepository": before["repository"],
                   "configuredBaseBranch": before["config"]["branch"], "prNumber": payload["prNumber"]}
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            current = context(self.service, pid, wid)
            self._check(current, payload)
            if current["config"] != before["config"]:
                raise ValueError("Konfigurace projektu se během načítání změnila.")
            repo = self.repository(pid, wid)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                # Recheck the accepted pointer inside the write transaction as well.
                current = context(self.service, pid, wid)
                self._check(current, payload)
                record = repo.insert(content)
            return self._item(record, current, repo)

    @staticmethod
    def _item(snapshot, current, repo, cache=None):
        cache = {} if cache is None else cache
        key = (snapshot["prNumber"], snapshot["configuredRepository"], snapshot["configuredBaseBranch"])
        if key not in cache:
            cache[key] = repo.known_identity(*key)
        identity = cache[key]
        known_head = identity["headSha"] if identity else None
        effective = snapshot
        config_changed = (current["repository"] != snapshot["configuredRepository"]
                          or (current["config"] or {}).get("branch") != snapshot["configuredBaseBranch"])
        identity_changed = bool(identity and snapshot.get("complete") is True and (
            snapshot["repository"]["id"] != identity["repositoryId"]
            or snapshot["pr"]["id"] != identity["prId"]))
        if config_changed or identity_changed:
            effective = {**snapshot, "complete": False}
        result = evaluate(effective, current["acceptedHead"], known_head)
        if config_changed:
            result["blockers"].append("repository-configuration-changed")
        if identity_changed:
            result["blockers"].append("github-repository-or-pr-identity-changed")
        return {"snapshot": snapshot, "evaluation": result}

    def list(self, pid, wid):
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            current = context(self.service, pid, wid)
            repo = self.repository(pid, wid)
            items, cache = [], {}
            for record in repo.iterate():
                item = self._item(record, current, repo, cache)
                item["snapshot"] = self._summary(record)
                items.append(item)
            return {key: value for key, value in current.items() if key != "config"} | {"items": items}

    @staticmethod
    def _summary(record):
        result = {key: value for key, value in record.items() if key not in {"reviews", "checks", "statuses", "pr"}}
        if "pr" in record:
            result["pr"] = {key: value for key, value in record["pr"].items() if key != "body"}
        result["counts"] = {key: len(record.get(key, [])) for key in ("reviews", "checks", "statuses")}
        return result

    def read(self, pid, wid, identifier):
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            current = context(self.service, pid, wid)
            repo = self.repository(pid, wid)
            return self._item(repo.read(identifier), current, repo)
