"""Návrhy změn Správy webu (kontrakt Správy webu §4): srdce dokument nikdy nezapisuje, jen navrhne.

`site/proposals/<id>.json` = `{id, status, baseRevision, changes, document, diff, diffTotal, notes, note, by, at,
decidedAt?}`. `changes` je částečný dokument `{title?, settings?, design?}`: části `settings` a klíče `design`
v něm nahradí uložené celé, zbytek zůstane. Návrh se hned normalizuje (`design_system.normalize`), takže neplatný
je 422 už při podání, a nese rozdíl po listech (`diff: [{path, before, after}]`, nejvýš `MAX_DIFF`).

Čeká vždy jen jeden návrh (`pending`): nový starší čekající označí `superseded`. Přijetí (`accept`) zapíše
`document` přes `store.write` nad revizí, ze které návrh vyšel; když se dokument mezitím změnil, je to 409
(zastaralý návrh nepřepíše práci člověka). Zamítnutí jen změní stav. Kdo smí co, hlídá router.
"""

import json
import re
import uuid
from datetime import UTC, datetime

from backend.project.site_admin import proposal_apply, proposal_attachments, store
from backend.project.site_admin.design_system import normalize
from backend.project.site_admin.store import SiteAdminConflict, SiteFileMissing
from backend.project.site_admin.tokens import SiteAdminInvalid, shape

PARTS = ("title", "settings", "design")
MAX_DIFF, VALUE = 200, 300  # řádků rozdílu a znaků hodnoty v rozdílu
ID = re.compile(r"^sp_[0-9a-f]{32}$")


def _dir(service, project):
    return proposal_attachments.path(service, project, "proposals")


def _now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def _merge(current, changes):
    shape(isinstance(changes, dict) and changes and set(changes) <= set(PARTS),
          "changes je {title?, settings?, design?} s aspoň jednou částí.")
    merged = {"v": 1, **{key: current[key] for key in PARTS}}
    if "title" in changes:
        merged["title"] = changes["title"]
    for key in ("settings", "design"):
        if key in changes:
            shape(isinstance(changes[key], dict), f"changes.{key} musí být objekt.")
            merged[key] = {**current[key], **changes[key]}
    return merged


def _flat(value, path, out):
    if isinstance(value, dict):
        for key, inner in value.items():
            _flat(inner, f"{path}.{key}" if path else key, out)
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            _flat(inner, f"{path}[{index}]", out)
    else:
        out[path] = value[:VALUE] if isinstance(value, str) else value
    return out


def diff(before, after):
    """Změněné listy `[{path, before, after}]` (chybějící = None) v pořadí nového, pak odebrané."""
    old = _flat({key: before[key] for key in PARTS}, "", {})
    new = _flat({key: after[key] for key in PARTS}, "", {})
    return [{"path": path, "before": old.get(path), "after": new.get(path)}
            for path in [*new, *(path for path in old if path not in new)] if old.get(path) != new.get(path)]


def _path(service, project, proposal_id):
    if not isinstance(proposal_id, str) or not ID.match(proposal_id):
        raise SiteFileMissing(f"Návrh {proposal_id} neexistuje.")
    return proposal_attachments.path(service, project, f"proposals/{proposal_id}.json")


def _load(path):
    shape(not path.is_symlink(), "Site proposal cannot be a symbolic link.")
    return json.loads(path.read_text("utf-8"))


def _save(service, project, proposal):
    _path(service, project, proposal["id"])
    proposal_attachments.write(service, project, f"proposals/{proposal['id']}.json",
                               json.dumps(proposal, ensure_ascii=False, indent=2).encode("utf-8"))


def pending(service, project):
    """Čekající návrhy (nejvýš jeden), nejnovější první."""
    folder = _dir(service, project)
    found = [_load(path) for path in folder.glob("sp_*.json")] if folder.is_dir() else []
    interrupted = {item["proposalId"]: item for item in proposal_apply.active(service, project)}
    return sorted(({**item, **({"recoveryNeeded": True,
                               "recoveryTargets": proposal_apply.observed(service, project, interrupted[item["id"]])}
                              if item["id"] in interrupted else {})}
                   for item in found if item["status"] in ("pending", "pending-attachments") or item["id"] in interrupted),
                  key=lambda item: item["at"], reverse=True)


def propose(service, project, changes, note=None, by="heart", *, attachments=None):
    """Uloží návrh nad uloženým dokumentem; vrací záznam návrhu. Návrh bez změny je 422."""
    shape(note is None or (isinstance(note, str) and len(note) <= 280), "note je jeden řádek do 280 znaků.")
    with service.lock_for(project):
        proposal_apply.guard(service, project)
        current = store.read(service, project)
        document, notes = normalize(current if changes == {} and attachments else _merge(current, changes), current)
        changed = diff(current, document)
        binaries = proposal_attachments.prepare(service, project, attachments) if attachments is not None else []
        if not changed and not binaries:
            raise SiteAdminInvalid("Návrh nic nemění proti uloženému dokumentu.")
        for older in pending(service, project):
            _save(service, project, {**older, "status": "superseded", "decidedAt": _now()})
        proposal = {"id": "sp_" + uuid.uuid4().hex, "status": "pending", "baseRevision": current["revision"],
                    "changes": changes, "document": document, "diff": changed[:MAX_DIFF], "diffTotal": len(changed),
                    "notes": notes, "note": note or "", "by": by, "at": _now()}
        if binaries:
            proposal["attachments"] = binaries
            proposal.update(schemaVersion=2, status="pending-attachments")
        _save(service, project, proposal)
    return proposal


def _pending_one(service, project, proposal_id):
    path = _path(service, project, proposal_id)
    if not path.is_file():
        raise SiteFileMissing(f"Návrh {proposal_id} neexistuje.")
    proposal = _load(path)
    if proposal["status"] not in ("pending", "pending-attachments"):
        raise SiteAdminConflict(f"Návrh {proposal_id} už je {proposal['status']}.")
    return proposal


def accept(service, project, proposal_id, expected_revision):
    """Zapíše dokument návrhu (člověk na stránce); vrací `(uložený dokument, poznámky, návrh)`."""
    with service.lock_for(project):
        proposal_apply.guard(service, project, proposal_id)
        path = _path(service, project, proposal_id)
        if not path.is_file():
            raise SiteFileMissing(f"Proposal {proposal_id} does not exist.")
        stored = _load(path)
        if stored.get("attachments"):
            if stored["status"] not in ("pending-attachments", "accepted"):
                raise SiteAdminConflict(f"Proposal is {stored['status']}.")
            return proposal_apply.accept(service, project, stored, expected_revision)
        proposal = _pending_one(service, project, proposal_id)
        current = store.read(service, project)["revision"]
        if proposal["baseRevision"] != current:
            raise SiteAdminConflict(f"Návrh vyšel z revize {proposal['baseRevision']}, uložená je {current}; "
                                    "srdce musí navrhnout znovu.")
        saved, notes = store.write(service, project, expected_revision, proposal["document"],
                                   note=f"Přijatý návrh {proposal['by']} {proposal_id}")
        proposal = {**proposal, "status": "accepted", "decidedAt": _now()}
        _save(service, project, proposal)
    return saved, notes, proposal


def reject(service, project, proposal_id):
    with service.lock_for(project):
        proposal_apply.guard(service, project)
        proposal = {**_pending_one(service, project, proposal_id), "status": "rejected", "decidedAt": _now()}
        _save(service, project, proposal)
    return proposal
