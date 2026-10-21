"""Registry linking Canvas human reviewers to verified GitHub accounts (docs/oporahub-review-identity.md).

A human session claims `name` + GitHub login and gets a nonce. The person then posts the exact
line `Opora-Identity: <identityId> <nonce>` as a comment on a PR or issue of the project's GitHub
repository; the server reads that comment with a GET and links the numeric GitHub user ID only
when the commenting account is the claimed login, of type User and not a configured agent
account. Agents can read the registry but never claim, verify or revoke. Different accounts
still do not prove different people: the registry records the operator's explicit claim."""
import re
import secrets

from backend.canvas import opora_review_risk as risk
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_review_aggregation import short_id
from backend.canvas.opora_review_insight_common import (
    InsightHumanRequired,
    InsightMissing,
    fields,
    project_id,
    reading,
    text,
    writing,
)
from backend.canvas.opora_review_scope import configuration

LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
MARKER = "Opora-Identity:"


class IdentityProofMissing(ValueError):
    """No comment by the claimed account carries the marker (HTTP 409 `identity_proof_missing`)."""


def marker(row):
    return f"{MARKER} {row['identity_id']} {row['nonce']}"


def public(row, actor="agent"):
    """Nonce only for the human session that has to post it; agents see the verified facts."""
    value = {"identityId": row["identity_id"], "name": row["name"], "githubLogin": row["github_login"],
             "githubUserId": row["github_user_id"], "state": row["state"], "operator": row["operator"],
             "claimedAt": row["claimed_at"], "verifiedAt": row["verified_at"], "revokedAt": row["revoked_at"],
             "evidence": row["evidence"]}
    if actor == "human" and row["state"] == "claimed":
        value["marker"] = marker(row)
    return value


def proves(comment, row, agent_ids):
    lines = {line.strip() for line in comment["body"].replace("\r\n", "\n").split("\n")}
    return (marker(row) in lines and comment["login"].casefold() == row["github_login"]
            and comment["userType"] == "User" and comment["userId"] not in agent_ids)


class ReviewIdentities:
    def __init__(self, canvas, reader=None, *, agent_ids=None):
        self.canvas, self._reader, self._agent_ids = canvas, reader, agent_ids

    @property
    def reader(self):
        if self._reader is None:
            from backend.integrations.github_identity_reader import GitHubIdentityReader
            self._reader = GitHubIdentityReader()
        return self._reader

    def agent_ids(self):
        return set(self._agent_ids if self._agent_ids is not None else risk.load()["agentAccountIds"])

    def list(self, project, actor):
        with reading(self.canvas, project_id(project)) as (_, store):
            return {"items": [public(row, actor) for row in store.identities()]}

    def claim(self, payload, actor):
        if actor != "human":
            raise InsightHumanRequired("Identitu reviewera zakládá jen člověk.")
        fields(payload, ("project", "name", "githubLogin"), ("operator",))
        project, name = project_id(payload["project"]), text(payload["name"], "Jméno", 80)
        login, operator = payload["githubLogin"], payload.get("operator", False)
        if not isinstance(login, str) or LOGIN.fullmatch(login) is None or type(operator) is not bool:
            raise ValueError("Neplatný GitHub login nebo příznak operátora.")
        login = login.casefold()
        identity_id = short_id("hi_", project, login)
        with writing(self.canvas, project) as (_, store):
            current = store.identity(identity_id)
            if current is not None and current["state"] == "verified":
                raise ValueError("Tento GitHub účet už je ověřený; nejdřív identitu zrušte.")
            if current is not None and current["state"] == "claimed" and (current["name"], current["operator"]) == (
                    name, operator):
                return public(current, actor)  # Same claim again: same nonce, nothing to post twice.
            if operator and any(row["operator"] and row["state"] != "revoked" and row["identity_id"] != identity_id
                                for row in store.identities()):
                raise ValueError("Operátor Canvasu už je přiřazen jiné identitě.")
            row = store.save_identity({"identity_id": identity_id, "name": name, "github_login": login,
                                       "github_user_id": None, "state": "claimed", "operator": operator,
                                       "nonce": secrets.token_hex(16), "claimed_at": stamp(), "verified_at": None,
                                       "revoked_at": None, "evidence": None})
            return public(row, actor)

    def verify(self, identity_id, payload, actor):
        if actor != "human":
            raise InsightHumanRequired("Identitu ověřuje jen člověk.")
        fields(payload, ("project", "number"))
        project, number = project_id(payload["project"]), payload["number"]
        if type(number) is not int or number < 1:
            raise ValueError("Neplatné číslo PR nebo issue.")
        with reading(self.canvas, project) as (_, store):
            row = store.identity(identity_id)
        if row is None:
            raise InsightMissing("Neznámá identita reviewera.")
        if row["state"] != "claimed":
            raise ValueError("Ověřit lze jen nárokovanou identitu.")
        repository = configuration(self.canvas, project)["repository"]
        agent_ids = self.agent_ids()
        comments = self.reader.comments(repository, number)  # Network outside every lock.
        proof = next((item for item in comments if proves(item, row, agent_ids)), None)
        if proof is None:
            raise IdentityProofMissing("Komentář s ověřovacím řádkem od tohoto účtu nebyl nalezen.")
        with writing(self.canvas, project) as (_, store):
            current = store.identity(identity_id)
            if current is None or current["state"] != "claimed" or current["nonce"] != row["nonce"]:
                raise ValueError("Identita se mezitím změnila; ověřte znovu.")
            if any(item["github_user_id"] == proof["userId"] for item in store.verified()):
                raise ValueError("Tento GitHub účet už patří jiné ověřené identitě.")
            evidence = {"repository": repository, "number": number, "commentId": proof["id"], "url": proof["url"],
                        "commentedAt": proof["createdAt"], "observedAt": stamp()}
            return public(store.save_identity({**current, "github_user_id": proof["userId"], "state": "verified",
                                               "verified_at": stamp(), "evidence": evidence}), actor)

    def revoke(self, identity_id, payload, actor):
        if actor != "human":
            raise InsightHumanRequired("Identitu ruší jen člověk.")
        fields(payload, ("project",))
        with writing(self.canvas, project_id(payload["project"])) as (_, store):
            row = store.identity(identity_id)
            if row is None:
                raise InsightMissing("Neznámá identita reviewera.")
            if row["state"] == "revoked":
                return public(row, actor)
            return public(store.save_identity({**row, "state": "revoked", "revoked_at": stamp()}), actor)
