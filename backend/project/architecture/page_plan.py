"""Plán stránky na plátně 2 (`docs/navrhy/2026-11-10-platno-2.md`, verze 3): layout z boxů a prvky logiky.

Nic nového mimo graf: box = sekce stránky `site.sections[]`, prvek logiky = uzel s `element.kind` pod stránkou
(`card.section` = box, bez něj celá stránka). Čtení skládá layout, skici boxů (vrstva kresby `box/<pageId>/<sectionId>`)
a prvky logiky s milníkem; zápis layoutu jde přes `CanvasService.save_graph` (stránka patří architektuře, takže
layout jde měnit i na čistém mainu) s otiskem plánu `digest` jen ze sekcí stránky, ať změna jiné karty nezpůsobí 409.

Pravidla agenta: box, který agent přidá nebo změní, má `status: "proposed"`; `approved` box nesmí změnit ani smazat
(403 s větou proč). `source` (kdo box naposledy zapsal) doplní server: nezměněný box si nechá uložený, změněný
dostane `human` / `agent`, a `scan`, když je přesně box z hotového skenu `scanId`. Stav boxu `approved` / `draft`
přepíná jen člověk (`set_status`).
"""
import hashlib
import json

from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.opora_event_stage import confirmed_nodes

PLAN_KEYS = {"project", "workspace", "pageId", "expectedDigest", "sections"}
HUMAN_STATUSES = ("approved", "draft")
# Milník prvku (Návrh → Realizace → Ověření), na kterém prvek právě je: uzavřená karta čeká na Ověření,
# karta `card.status: ready` je v Realizaci, jinak Návrh. Stejné pořadí jako `plan-progress.ts` ve frontendu.
MILESTONES = ("Návrh", "Realizace", "Ověření")


def plan_digest(sections):
    """Otisk layoutu stránky (jen `site.sections`); souběh zápisu plánu se hlídá jím, ne digestem celého pohledu."""
    return hashlib.sha256(json.dumps(sections or [], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def find_page(graph, page_id):
    page = next((node for node in graph["nodes"] if node["id"] == page_id), None)
    if page is None or not isinstance(page.get("site"), dict) or page["site"].get("kind") != "page":
        raise GateError(404, "page_not_found", f"Stránka {page_id!r} v tomto prostoru není.",
                        "pageId je id uzlu se site.kind page (GET /api/view nebo node-brief).")
    return page


def page_elements(graph, page_id):
    """Prvky logiky stránky: přímé uzly s `element` pod stránkou, bez podstránek (jako `pageElements` ve frontendu)."""
    return [node for node in graph["nodes"] if node.get("parentId") == page_id and node["kind"] == "node"
            and "element" in node and (node.get("site") or {}).get("kind") != "page"]


def domain_pages(graph, domain_id):
    """Stránky, jejichž nejbližší doména (`site.kind application`) nad nimi je `domain_id` (i podstránky)."""
    by_id = {node["id"]: node for node in graph["nodes"]}

    def domain_of(item):
        cursor = by_id.get(item.get("parentId"))
        while cursor is not None and (cursor.get("site") or {}).get("kind") != "application":
            cursor = by_id.get(cursor.get("parentId"))
        return cursor and cursor["id"]

    return [item for item in graph["nodes"]
            if (item.get("site") or {}).get("kind") == "page" and domain_of(item) == domain_id]


def _milestone(node, done):
    if done:
        return MILESTONES[2]
    return MILESTONES[1] if (node.get("card") or {}).get("status") == "ready" else MILESTONES[0]


def read(service, pid, wid, page_id):
    """`{page, sections, logic, digest}` podle kontraktu; skica boxu = `{revision}` uložené kresby, jinak None."""
    with service.reading(pid):
        view = service.view(pid, wid)
        page = find_page(view["graph"], page_id)
        sections = page["site"].get("sections") or []
        sketches = {}
        if not view["readOnly"]:
            for section in sections:
                revision = service.drawings.read((pid, wid, f"box/{page_id}/{section['id']}"))["revision"]
                sketches[section["id"]] = {"revision": revision} if revision else None
        elements = page_elements(view["graph"], page_id)
        done = confirmed_nodes(service.db_for(pid), pid, wid, [node["id"] for node in elements])
    return {
        "page": {"id": page["id"], "name": page["name"], "path": page["site"]["path"],
                 "goal": page["site"].get("goal")},
        "sections": [{**section, "sketch": sketches.get(section["id"])} for section in sections],
        "logic": [{"id": node["id"], "kind": node["element"]["kind"], "name": node["name"], "purpose": node["purpose"],
                   "section": (node.get("card") or {}).get("section"), "milestone": _milestone(node, node["id"] in done)}
                  for node in elements],
        "digest": plan_digest(sections),
        "readOnly": view["readOnly"],
    }


def _bare(section):
    return {key: value for key, value in section.items() if key != "source"}


def _refuse(message, hint):
    raise GateError(403, "agent_box_refused", message, hint)


def merge_sections(old, sections, by, scan_sections=()):
    """Nový layout s `source` od serveru; pravidla agenta (modul docstring). `by` = `human` | `agent`."""
    if not isinstance(sections, list) or not all(isinstance(item, dict) for item in sections):
        raise GateError(422, "invalid_payload", "sections je seznam boxů (objektů).",
                        "Pošlete sections jako v GET /api/page-plan bez sketch; prázdný seznam layout smaže.")
    before = {item["id"]: item for item in old}
    scanned = [_bare(item) for item in scan_sections]
    result = []
    for item in sections:
        body = {key: value for key, value in _bare(item).items() if key != "sketch"}
        stored = before.get(body.get("id"))
        if stored is not None and _bare(stored) == body:
            result.append(stored)
            continue
        if by == "agent":
            if body.get("status") != "proposed":
                _refuse(f"Agent zapisuje jen návrh: box {body.get('id')!r} musí mít status proposed.",
                        "Nový nebo změněný box pošlete se status proposed; schvaluje člověk.")
            if stored is not None and stored.get("status") == "approved":
                _refuse(f"Box {body.get('id')!r} schválil člověk; agent ho nemění.",
                        "Navrhněte nový box se status proposed, nebo požádejte člověka.")
        result.append({**body, "source": "scan" if body in scanned else by})
    if by == "agent":
        kept = {item.get("id") for item in result}
        for stored in old:
            if stored["id"] not in kept and stored.get("status") == "approved":
                _refuse(f"Box {stored['id']!r} schválil člověk; agent ho nesmaže.",
                        "Schválené boxy pošlete beze změny.")
    return result


def save(service, payload, by, scan_sections=()):
    """Zapíše layout stránky; 409 `plan_changed` při jiném `expectedDigest`. Vrací totéž co `read`."""
    if not isinstance(payload, dict) or not PLAN_KEYS <= set(payload) <= PLAN_KEYS | {"scanId"}:
        raise GateError(422, "invalid_payload", "Tělo je {project, workspace, pageId, expectedDigest, sections, scanId?}.",
                        "expectedDigest je digest z GET /api/page-plan.")
    pid, wid, page_id = payload["project"], payload["workspace"], payload["pageId"]
    with service.graph_lock_for(pid):
        view = service.view(pid, wid)
        page = find_page(view["graph"], page_id)
        old = page["site"].get("sections") or []
        if plan_digest(old) != payload["expectedDigest"]:
            raise GateError(409, "plan_changed", "Layout stránky se mezitím změnil.",
                            "Načtěte GET /api/page-plan a pošlete změnu znovu s novým digest.")
        sections = merge_sections(old, payload["sections"], by, scan_sections)
        before = {item["id"]: item.get("inspiration") for item in old}
        changed = [item["inspiration"] for item in sections
                   if "inspiration" in item and item["inspiration"] != before.get(item.get("id"))]
        if changed and view["readOnly"]:
            raise GateError(409, "workspace_required", "Inspirace boxu potřebuje pracovní prostor; main je jen ke čtení.",
                            "Layout a stav boxu jdou měnit i na mainu, obrázky a odkaz ve worktree domény.")
        files = sorted({file for item in changed for file in item.get("files", [])})
        missing = service.drawing_files.missing(service.db_for(pid), pid, files)
        if missing:
            raise GateError(422, "file_not_found", "Obrázek inspirace není nahraný: " + ", ".join(sorted(missing)),
                            "Nahrajte ho přes POST /api/drawing-file a pošlete jeho id.")
        site = {key: value for key, value in page["site"].items() if key != "sections"}
        if sections:
            site["sections"] = sections
        graph = {"nodes": [{**node, "site": site} if node["id"] == page_id else node for node in view["graph"]["nodes"]],
                 "edges": view["graph"]["edges"]}
        service.save_graph(pid, wid, graph, view["digest"], actor=by)
        return read(service, pid, wid, page_id)


def set_status(service, payload, page_id, section_id):
    """Stav boxu `approved` / `draft` (jen člověk; volající to ověřil). `expectedDigest` je nepovinný."""
    if (not isinstance(payload, dict) or not {"project", "workspace", "status"} <= set(payload)
            <= {"project", "workspace", "status", "expectedDigest"} or payload["status"] not in HUMAN_STATUSES):
        raise GateError(422, "invalid_payload", "Tělo je {project, workspace, status: approved|draft, expectedDigest?}.",
                        "proposed zapisuje agent nebo sken přes POST /api/page-plan.")
    pid, wid = payload["project"], payload["workspace"]
    with service.graph_lock_for(pid):
        view = service.view(pid, wid)
        old = find_page(view["graph"], page_id)["site"].get("sections") or []
        if payload.get("expectedDigest", plan_digest(old)) != plan_digest(old):
            raise GateError(409, "plan_changed", "Layout stránky se mezitím změnil.", "Načtěte GET /api/page-plan znovu.")
        if not any(item["id"] == section_id for item in old):
            raise GateError(404, "box_not_found", f"Stránka nemá box {section_id!r}.", "Id boxu je id sekce z GET /api/page-plan.")
        sections = [{**item, "status": payload["status"]} if item["id"] == section_id else item for item in old]
        return save(service, {"project": pid, "workspace": wid, "pageId": page_id, "expectedDigest": plan_digest(old),
                              "sections": sections}, "human")


def brief(graph, page_id):
    """Zkrácený plán stránky pro node-brief: řádek na box a řádek na prvek logiky; None, když stránka nic nemá."""
    page = find_page(graph, page_id)
    names = {}
    layout = []
    for item in page["site"].get("sections") or []:
        names[item["id"]] = item["name"]
        box = item.get("box")
        where = f" [{box['x']},{box['y']} {box['w']}×{box['h']}]" if box else ""
        inside = f" v {item['parent']}" if item.get("parent") else ""
        layout.append(f"{item['id']}: {item['role']} „{item['name']}“{where}{inside} {item.get('status', 'draft')}"
                      + (f" – {item['intent']}" if item["intent"] else ""))
    logic = [f"{node['element']['kind']} „{node['name']}“ → "
             + names.get((node.get("card") or {}).get("section"), "celá stránka")
             for node in page_elements(graph, page_id)]
    if not layout and not logic:
        return None
    return {"layout": layout, "logic": logic,
            "read": f"GET /api/page-plan?project=…&workspace=…&pageId={page_id}"}
