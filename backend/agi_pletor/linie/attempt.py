"""Pokus práce úkolu (docs/navrhy/2026-11-06-linie-rebrand.md §3, §7 bod 5): `work.attempts[]`.

`attempt` zapíše `{attemptId, repo, baseRef, baseSha, branch, agent, createdBy, published: False, at, requestId}`.
Větev zakládá agent z `baseSha`, služba ji nikdy nezakládá ani nepřepisuje: jméno rodiče (`tree.parent`) jen nabízí
výchozí `baseRef`; operace ověří, že `baseRef` existuje a `baseSha` je v něm (chybí → `rev(baseRef)`), a existující
větev přijme jen jako potomka `baseSha` (jinak 409 `branch_foreign`). Týž pokus (stejné `attemptId` z klíče nebo
stejná větev) se nezdvojí: po pádu mezi založením větve a zápisem evidence opakování jen doplní záznam.
`publish` po `report` ověří výsledek: `published = True`, když po `git fetch` existuje `refs/remotes/origin/<branch>`
a obsahuje `baseSha`.
"""
import uuid
from pathlib import Path

from backend.agi_pletor.linie import tree
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.work import WorkError, ancestor, rev

FETCH_TIMEOUT = 60


def _same(attempt_id, branch):
    return lambda item: item["attemptId"] == attempt_id or item["branch"] == branch


def attempt(service, project, ticket_id, payload, by, now, attempt_id=None):
    shown = work_mod.get(service, project, ticket_id)
    work = shown["work"]
    root = work["repository"]
    if payload.get("repo") is not None and Path(payload["repo"]).resolve() != Path(root).resolve():
        raise WorkError("invalid_payload", 422, "repo je repozitář úkolu (nebo chybí).", "repo vynechte.")
    branch = work_mod._name(payload.get("branch"), "branch")
    attempt_id = attempt_id or "at_" + uuid.uuid4().hex
    if any(map(_same(attempt_id, branch), work.get("attempts") or [])):
        return shown  # opakování téhož pokusu: nic nového
    if payload.get("requestId") is not None and payload["requestId"] != work.get("requestId"):
        raise WorkError("request_mismatch", 422, f"Ticket nepatří k žádosti {payload['requestId']}.",
                        "Žádost váže ticket přes requestId v POST /work; requestId vynechte.")
    work_mod.require(shown, "attempt")
    heads = set((work_mod.git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)", optional=True)
                 or "").split())
    base_ref = work_mod._name(payload.get("baseRef") or tree.parent(branch, heads), "baseRef")
    tip = rev(root, base_ref)
    if not tip:
        raise WorkError("base_missing", 422, f"Výchozí větev {base_ref} v repozitáři neexistuje.",
                        f"Rodič podle jména je {tree.parent(branch, heads)}.")
    base_sha = rev(root, payload["baseSha"]) if payload.get("baseSha") else tip
    if not base_sha or not ancestor(root, base_sha, tip):
        raise WorkError("base_mismatch", 409, f"baseSha {payload.get('baseSha')} neleží na {base_ref}.",
                        "baseSha vynechte (doplní se špička baseRef), nebo pošlete commit z baseRef.")
    current = rev(root, branch)
    if current and not ancestor(root, base_sha, current):
        raise WorkError("branch_foreign", 409, f"Větev {branch} existuje a nevychází z {base_sha[:7]}; nepřevezme se.",
                        "Zvolte nové jméno větve, nebo baseSha, ze kterého větev vznikla.")
    record = {"attemptId": attempt_id, "repo": root, "baseRef": base_ref, "baseSha": base_sha, "branch": branch,
              "agent": payload.get("agent") or by.split(":", 1)[-1],
              "createdBy": "agent" if by.startswith("agent:") else "service", "published": False, "at": now,
              "requestId": work.get("requestId")}

    def change(ticket):
        attempts = ticket["work"].get("attempts") or []
        if any(map(_same(attempt_id, branch), attempts)):
            return ticket["work"]
        return {**ticket["work"], "attempts": [*attempts, record]}
    return work_mod._change(service, project, ticket_id, now, change, "linie.attempt", by, attempt=attempt_id,
                            sha=base_sha, request=record["requestId"])


def publish(service, project, ticket_id, now, by="opora"):
    """Nepublikované pokusy, jejichž větev je po `git fetch` v originu a obsahuje `baseSha`, označí `published`."""
    work = work_mod.get(service, project, ticket_id)["work"]
    found = {}
    for item in work.get("attempts") or []:
        if item["published"]:
            continue
        work_mod.git(item["repo"], "fetch", "origin", item["branch"], timeout=FETCH_TIMEOUT, optional=True)
        remote = rev(item["repo"], "refs/remotes/origin/" + item["branch"])
        if remote and ancestor(item["repo"], item["baseSha"], remote):
            found[item["attemptId"]] = remote
    if not found:
        return None

    def change(ticket):
        return {**ticket["work"], "attempts": [
            {**item, "published": True, "publishedSha": found[item["attemptId"]]} if item["attemptId"] in found
            else item for item in ticket["work"].get("attempts") or []]}
    return work_mod._change(service, project, ticket_id, now, change, "linie.attempt.published", by,
                            attempt=",".join(found))
