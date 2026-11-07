"""Revert jako operace služby a evidence rebase (docs/navrhy/2026-11-06-linie-rebrand.md §5, §7 bod 5).

`revert` ověří `HEAD větve == expectedHead` a že `sha` leží na větvi, zapíše `started` do
`<data>/projects/<p>/linie/revert_log.json`, provede `git revert --no-edit sha` v dočasném odpojeném worktree
(`merge.detached`) a nový commit dá na větev (lokální ref compare-and-set, když ji nedrží žádný strom; push do originu,
když tam větev je). Konflikt → `revert --abort`, záznam `state: conflict` a 409 `revert_conflict`, nikdy `finished`.
Stejné `op` po dokončení jen vrátí záznam. `rebase_note` git nemění: zapíše `{kind: rebase, from, to}` jako evidenci.
"""
import uuid
from pathlib import Path

from backend.agi_pletor.linie import journal, jsonfile, merge
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.work import SHA, WorkError
from backend.integrations import gitio


def _path(data_root, project):
    return Path(data_root) / "projects" / project / "linie" / "revert_log.json"


def read(data_root, project):
    found = jsonfile.read(_path(data_root, project), [])
    return [e for e in found if isinstance(e, dict) and e.get("op")] if isinstance(found, list) else []


def _put(data_root, project, entry):
    """Záznam se stejným `op` nahradí, jinak připojí."""
    jsonfile.update(_path(data_root, project), [],
                    lambda found: [e for e in found if e.get("op") != entry["op"]] + [entry])
    return entry


def _apply(git, root, workdir, branch, head, sha, pushable):
    """`git revert` v odpojeném worktree na `head`; `(nový sha, pushed)`, nebo None při konfliktu."""
    with merge.detached(git, root, workdir, head):
        if git(workdir, *merge._identity(git, root), "revert", "--no-edit", sha, timeout=merge.TIMEOUT,
               optional=True) is None:
            git(workdir, "revert", "--abort", optional=True)
            return None
        new = git(workdir, "rev-parse", "HEAD")
        pushed = pushable and git(workdir, "push", "origin", f"{new}:refs/heads/{branch}", timeout=merge.TIMEOUT,
                                  optional=True) is not None
        return new, pushed


def revert(service, project, ticket_id, sha, expected_head, now, *, op=None, by="opora", git=gitio.git):
    op = merge._op(op) or str(uuid.uuid4())
    with merge.LOCK:
        known = next((e for e in read(service.root, project) if e["op"] == op), None)
        if known and known["ticket"] != ticket_id:
            raise WorkError("op_conflict", 409, f"Operace {op} patří jinému úkolu.", "Pošlete nové op.")
        if known and known["state"] == "finished":
            return known
        work = work_mod.get(service, project, ticket_id)["work"]
        root, branch = work["repository"], work["branch"]
        head = work_mod.rev(root, branch)
        if not head or not isinstance(expected_head, str) or len(expected_head) < 7 \
                or not head.startswith(expected_head.lower()):
            raise WorkError("head_moved", 409, f"Hlava {branch} ({(head or '-')[:7]}) není {expected_head}.",
                            "Načtěte kuličku znovu a pošlete aktuální expectedHead.")
        full = work_mod.rev(root, sha) if isinstance(sha, str) and SHA.fullmatch(sha) else None
        if not full or not work_mod.ancestor(root, full, head):
            raise WorkError("work_mismatch", 409, f"Commit {sha} neleží na větvi {branch}.", "Pošlete sha z větve úkolu.")
        entry = _put(service.root, project, {"op": op, "kind": "revert", "ticket": ticket_id, "repo": root,
                                              "branch": branch, "sha": full, "expectedHead": head, "by": by,
                                              "at": now, "state": "started", "result_sha": None})
        refs = {"ticket": ticket_id, "op": op, "sha": full}
        journal.record(service, project, "linie.revert.started", by, refs)
        workdir = Path(service.root) / "pletor" / "linie" / "revert" / ticket_id
        pushable = work_mod.rev(root, "refs/remotes/origin/" + branch) is not None
        done = _apply(git, root, workdir, branch, head, full, pushable)
        if done is None:  # OP-A20FB1.3: konflikt je nedokončený (`conflict`), nikdy `finished`
            _put(service.root, project, {**entry, "state": "conflict", "finishedAt": now})
            journal.record(service, project, "linie.revert.conflict", by, refs)
            raise WorkError("revert_conflict", 409, f"Revert {full[:7]} na {branch} narazil na konflikt; nic se "
                            "nezměnilo.", "Agent revert provede ručně na větvi a pošle report.")
        new, pushed = done
        local = not merge._checked_out(git, root, branch) and git(
            root, "update-ref", f"refs/heads/{branch}", new, head, optional=True) is not None
        if not (local or pushed):
            _put(service.root, project, {**entry, "state": "failed", "finishedAt": now})
            journal.record(service, project, "linie.revert.failed", by, refs)
            raise WorkError("revert_not_applied", 409, f"Revert {full[:7]} se na {branch} nezapsal (větev drží "
                            "worktree a origin ji nemá nebo push selhal).", "Agent revert provede ve svém stromu.")
        entry = _put(service.root, project, {**entry, "state": "finished", "result_sha": new, "local": local,
                                              "pushed": pushed, "finishedAt": now})
        journal.record(service, project, "linie.revert.finished", by, {**refs, "sha": new}, reverted=full)
        return entry


def rebase_note(service, project, ticket_id, old, new, by, now):
    """Rebase se neprovádí, jen eviduje `{from, to}` (záznam + událost); git se nemění."""
    work_mod.get(service, project, ticket_id)  # ticket s prací existuje
    if not all(isinstance(value, str) and SHA.fullmatch(value) for value in (old, new)):
        raise WorkError("invalid_payload", 422, "from a to jsou sha commitů (7–40 hex).")
    entry = _put(service.root, project, {"op": "rb_" + uuid.uuid4().hex, "kind": "rebase", "ticket": ticket_id,
                                          "from": old.lower(), "to": new.lower(), "by": by, "at": now})
    journal.record(service, project, "linie.rebase.noted", by, {"ticket": ticket_id, "op": entry["op"], "sha": new},
                   **{"from": old.lower()})
    return entry
