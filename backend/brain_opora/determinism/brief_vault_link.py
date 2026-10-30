"""Výslech ve Schránce, řez 1 (docs/navrhy/2026-10-31-vyslech-ve-schrance.md §2, §7): write-through spisu do Schránky.

Spis výslechu (`intake_briefs`) zůstává zdrojem pravdy pro `clarity`; Schránka dostává jeho zrcadlo:
- kořenový fragment `brief` požadavku s doslovným textem zakládajícího vstupu (`ensure_root`). Pochází-li vstup ze
  Schránky (zdroj `brief_fragment`), kořenem je ten fragment. Odkaz a rozsah kořene jsou v `situation.fragmentId`
  a `situation.fragmentScope`;
- části syntézy jako podfragmenty kořene (`create` s `parentId`, ne `split`: části nejsou výřezy textu požadavku),
  spárované pořadím přes `situation.partFragments`; změněná část = `revise` s `expectedRevision`;
- předpoklady jako otázky K upřesnění „Platí, že …?“ (`question`), spárované textem (`situation.assumptionFragments`);
- otázky výslechu (`ask`) jako `question` (`situation.questionFragments`) a odpověď člověka z Velínu jako `answer`.

Každý zápis jde přes `BriefVault.apply(..., intake=False)`: nový fragment tak nezaloží vstup vstupní brány (požadavek
už vstup má; jinak by výslech plodil nové požadavky). Volá se mimo zámek spisu a chyba se jen zaloguje (`safely`):
zrcadlení výslech nikdy nezastaví.
"""
import logging

from database.repositories.intake_briefs import IntakeBriefs
from database.repositories.intake_entries import IntakeEntries
from database.repositories.intake_requirements import IntakeRequirements

LOGGER = logging.getLogger(__name__)
KEYS = ("fragmentId", "fragmentScope", "partFragments", "assumptionFragments", "questionFragments")
ROOT_DISCIPLINE = "cx"  # kořen nese disciplínu vždy; požadavek je záměr člověka, přeřadí ho `set-discipline`
AGENT = "srdce"
TITLE = 160  # MAX_TITLE Schránky


def carry(old, new):
    """Nový spis (`situation`) s odkazy do Schránky ze starého, aby obnova spisu kořen neztratila."""
    old = old if isinstance(old, dict) else {}
    return {**(new or {}), **{key: old[key] for key in KEYS if key in old}}


def safely(call, *args):
    """Zrcadlení do Schránky nikdy nezastaví výslech: chyba se zaloguje a vrátí None."""
    try:
        return call(*args)
    except Exception:  # noqa: BLE001 - Schránka je zrcadlo, spis už platí
        LOGGER.exception("Výslech ve Schránce: zápis %s selhal, výslech pokračuje.", getattr(call, "__name__", call))
        return None


def _title(text):
    line = " ".join(str(text or "").split())
    return line if len(line) <= TITLE else line[: TITLE - 1] + "…"


def _vault(service):
    from backend.editor.brief_vault.brief_vault import BriefVault

    return BriefVault(service)


def _op(service, project, workspace, op, actor="agent", **fields):
    payload = {"project": project, "workspace": workspace, "op": op, **fields}
    return _vault(service).apply(payload, actor=actor, agent=AGENT, intake=False)


def _rows(service, project, workspace, ids=None):
    from backend.editor.brief_vault.brief_vault_model import latest_rows

    with service.reading(project):
        return latest_rows(service.db_for(project), project, workspace, ids)


def _live(service, project, workspace, fragment_id):
    if not isinstance(fragment_id, str):
        return None
    row = _rows(service, project, workspace, [fragment_id]).get(fragment_id)
    return None if row is None or row["deleted"] else row


def _scope_of(rows, fragment_id):
    """Rozsah Schránky (`scopeNodeId` kořene stromu), ve kterém fragment leží: "" plátno, jinak karta či sektor."""
    cursor, seen = rows.get(fragment_id), set()
    while cursor is not None and cursor["parent_id"] is not None and cursor["fragment_id"] not in seen:
        seen.add(cursor["fragment_id"])
        cursor = rows.get(cursor["parent_id"])
    return (cursor or {}).get("scope_node_id") or ""


def _situation(service, project, requirement_id):
    with service.reading(project):
        found = IntakeBriefs(service.db_for(project)).get(requirement_id)
    return (found or {}).get("situation") or {}


def _remember(service, project, requirement_id, **links):
    """Odkazy do Schránky do `situation` spisu (krátká vlastní transakce; spis bez řádku se nezakládá)."""
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = IntakeBriefs(db)
            found = store.get(requirement_id)
            if found is not None:
                store.save({**found, "situation": {**(found.get("situation") or {}), **links}})


def _founding(service, project, requirement_id):
    """`(požadavek, zakládající vstup)` – vstup s `source`, `sourceRef` a doslovným textem, nebo None."""
    with service.reading(project):
        db = service.db_for(project)
        requirement = IntakeRequirements(db).get(requirement_id)
        entries = IntakeBriefs(db).entries_of(requirement_id)
        entry = IntakeEntries(db).get(entries[0]["id"]) if entries else None
    return requirement, entry


def ensure_root(service, project, workspace, requirement_id):
    """Kořenový fragment požadavku, idempotentně: `situation.fragmentId`, nebo fragment zakládajícího vstupu ze
    Schránky, nebo nový kořen `brief` s doslovným textem vstupu. Vrací id kořene; bez spisu None."""
    situation = _situation(service, project, requirement_id)
    if _live(service, project, workspace, situation.get("fragmentId")):
        return situation["fragmentId"]
    requirement, entry = _founding(service, project, requirement_id)
    if requirement is None:
        return None
    root = None
    if entry and entry.get("source") == "brief_fragment":
        root = (_live(service, project, workspace, entry.get("sourceRef")) or {}).get("fragment_id")
    if root is None:
        text = (entry or {}).get("text") or requirement["title"]
        created = _op(service, project, workspace, "create", title=_title(requirement["title"]), text=text,
                      scopeNodeId="", discipline=ROOT_DISCIPLINE,
                      note=f"Kořen výslechu požadavku {requirement_id}: doslovný text zakládajícího vstupu.")
        root = created["fragment"]["id"]
    scope = _scope_of(_rows(service, project, workspace), root)
    _remember(service, project, requirement_id, fragmentId=root, fragmentScope=scope)
    return root


def _origin_note(part):
    note = f"Část syntézy výslechu · původ: {part.get('origin')}"
    return note + (f" · zdroj: {part['source']}" if str(part.get("source") or "").strip() else "") + "."


def _part(service, project, workspace, root, known, part):
    """Jedna část syntézy: revize spárovaného fragmentu, jen když se text změnil; jinak nový podfragment."""
    text, note = part["text"], _origin_note(part)
    row = _live(service, project, workspace, known)
    if row is not None:
        if row["text"] != text or row["title"] != _title(text):
            _op(service, project, workspace, "revise", fragmentId=known, expectedRevision=row["revision"],
                text=text, title=_title(text), note=note)
        return known
    created = _op(service, project, workspace, "create", parentId=root, title=_title(text), text=text, note=note)
    return created["fragment"]["id"]


def after_synthesis(service, project, workspace, requirement_id, synthesis):
    """Syntéza → Schránka: části jako podfragmenty kořene, předpoklady jako otázky K upřesnění."""
    root = ensure_root(service, project, workspace, requirement_id)
    if root is None:
        return None
    situation = _situation(service, project, requirement_id)
    known = list(situation.get("partFragments") or [])
    parts = [part for part in synthesis.get("parts") or [] if isinstance(part, dict)]
    mapped = [_part(service, project, workspace, root, known[index] if index < len(known) else None, part)
              for index, part in enumerate(parts)]
    assumptions = dict(situation.get("assumptionFragments") or {})
    for text in synthesis.get("assumptions") or []:
        if not isinstance(text, str) or not text.strip() or text.strip() in assumptions:
            continue
        sentence = text.strip().rstrip(".?!")
        created = _op(service, project, workspace, "question", fragmentId=root, title=_title(f"Platí, že {sentence}?"),
                      text=f"Předpoklad syntézy výslechu: {text.strip()}", askedFor="human",
                      note="Předpoklad výslechu potvrdí člověk.")
        assumptions[text.strip()] = created["fragment"]["id"]
    # Fragmenty částí, které syntéza vypustila, zůstanou (mazat smí jen člověk); páruje se dál podle pořadí.
    _remember(service, project, requirement_id, partFragments=mapped + known[len(mapped):],
              assumptionFragments=assumptions)
    return root


def after_ask(service, project, workspace, requirement_id, question):
    """Otázka výslechu → `question` pod kořenem (K upřesnění), s doporučením srdce jako návrhem."""
    root = ensure_root(service, project, workspace, requirement_id)
    links = dict(_situation(service, project, requirement_id).get("questionFragments") or {})
    if root is None or question["id"] in links:
        return None
    created = _op(service, project, workspace, "question", fragmentId=root, title=_title(question["text"]),
                  text=f"{question['text']}\n\nProč: {question['why']}", askedFor="human",
                  proposal=question["recommended"], note=f"Otázka výslechu {question['id']}.")
    links[question["id"]] = created["fragment"]["id"]
    _remember(service, project, requirement_id, questionFragments=links)
    return links[question["id"]]


def after_answer(service, project, workspace, requirement_id, question_id, text):
    """Odpověď člověka z Velínu → `answer` na zrcadlené otázce (jen člověk, `actor="human"`); už zodpovězená zůstane."""
    fragment = (_situation(service, project, requirement_id).get("questionFragments") or {}).get(question_id)
    row = _live(service, project, workspace, fragment)
    if row is None or row["stage"] == "ready":
        return None
    _op(service, project, workspace, "answer", actor="human", fragmentId=fragment, expectedRevision=row["revision"],
        answer=text, note=f"Odpověď člověka ve Velínu na otázku výslechu {question_id}.")
    return fragment
