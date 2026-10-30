"""Požadavky vstupní brány (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5), bez modelu.

Srdce při potvrzení stanoviska (`opora_heart.py intake … --requirement rq_…|new`) vstup naváže na požadavek:
- `new` založí požadavek v oblasti vstupu. U `later_extension` je `deferred` s podmínkou otevření
  (`--open-condition`, jinak aktivní milník oblasti); jinak `open` a patří k aktivnímu milníku oblasti.
- existující `rq_…` vstup jen připojí (víc vstupů = jeden požadavek, žádné duplicitní zadání).
Odložený požadavek otevře srdce, až spouštěč `milestone.done` ukáže splněný milník; tady se stav nepřepíná.
"""
import uuid

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from database.repositories.intake_entries import IntakeEntries
from database.repositories.intake_milestones import IntakeMilestones
from database.repositories.intake_requirements import IntakeRequirements

TITLE, CONDITION = 200, 200  # znaků názvu požadavku a podmínky otevření
HINT = 'python opora_heart.py intake --entry ie_… --verdict V --requirement new --title "…" [--open-condition ms_…]'


def _text(value, limit, name):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise invalid(f"{name} je neprázdný text do {limit} znaků.", HINT)
    return value.strip()


def check(requirement, title, open_condition):
    """Tvar voleb před zápisem: `new` chce `title`; `title` a `open_condition` jdou jen s `new`."""
    if requirement is None:
        if title is not None or open_condition is not None:
            raise invalid("title a openCondition patří jen k requirement new.", HINT)
        return
    if requirement == "new":
        _text(title, TITLE, "title")
        if open_condition is not None:
            _text(open_condition, CONDITION, "openCondition")
    elif not isinstance(requirement, str) or not requirement.startswith("rq_"):
        raise invalid("requirement je rq_… nebo new.", HINT)
    elif title is not None or open_condition is not None:
        raise invalid("title a openCondition patří jen k requirement new; existující požadavek se jen připojí.", HINT)


def attach(db, entry, verdict, requirement, title, open_condition, now):
    """Naváže vstup na požadavek (po `check`, uvnitř transakce volajícího); vrací ID požadavku nebo None."""
    if requirement is None:
        return None
    store, workspace, area = IntakeRequirements(db), entry["workspaceId"], entry.get("areaId")
    if requirement != "new":
        found = store.get(requirement)
        if found is None or found["workspaceId"] != workspace:
            raise GateError(404, "intake_requirement_not_found", "Požadavek v tomto pracovním prostoru neexistuje.",
                            "ID požadavku (rq_…) je v GET /api/intake; jinak --requirement new --title \"…\".")
        IntakeEntries(db).set_requirement(entry["id"], requirement, found["milestoneId"])
        return requirement
    active = IntakeMilestones(db).active(workspace, area) if area else None
    later = verdict == "later_extension"
    if not later and open_condition is not None:
        raise invalid("openCondition patří jen k later_extension (odložený požadavek).", HINT)
    condition = (open_condition.strip() if open_condition else active["id"] if active else None) if later else None
    if later and condition is None:
        raise invalid("Odložený požadavek potřebuje podmínku otevření a oblast vstupu nemá aktivní milník.",
                      "Přidejte --open-condition ms_… (ID milníku, po jehož splnění se požadavek otevře).")
    created = {"id": "rq_" + uuid.uuid4().hex, "workspaceId": workspace, "areaId": area,
               "milestoneId": None if later or active is None else active["id"], "title": title.strip(),
               "status": "deferred" if later else "open", "openCondition": condition, "createdAt": now}
    store.insert(created)
    IntakeEntries(db).set_requirement(entry["id"], created["id"], created["milestoneId"])
    return created["id"]
