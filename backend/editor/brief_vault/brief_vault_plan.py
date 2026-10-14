"""Plán struktury Schránky na serveru (docs/schranka-neurony.md §4, §9 body 1, 2 a 7).

Jediné pravidlo, jak z fragmentů vznikne dávka `/api/canvas-plan`. Pro vybraný fragment F s disciplínou D
ve skupině G ve vrstvě, kde visí kořen jeho schránky (sektor = dovnitř sektoru, karta = vedle ní, plátno =
kořen): oblast G (značka `briefGroup` ve stavu uzlu, jinak nová) → sektor D v oblasti (značka `briefDiscipline`,
jinak nový) → karta za F (list) nebo za každého přímého potomka F druhu `brief` (tvar karty
`brief_vault_plan_cards`). Každá karta jde do sektoru své disciplíny (dítě s přepsanou disciplínou do svého).
Sourozenci z jednoho F se spojí vazbou `next`; vazbu na `fe` plán nezakládá. Karta, kterou fragment ve vrstvě
už má (první `fragmentRef` míří na něj), se nezakládá znovu: plán ji aktualizuje položkou `extend`
(`brief_vault_plan_update`), vazbu `next` mezi dvěma existujícími kartami nepřidává.
Sektor se hledá v oblasti skupiny podle jejího id (členství v oblasti je geometrické, `areas.area_of`);
označený sektor mimo oblast své skupiny je 409 (druhý sektor by byl duplicitní značkou).

Výběr se normalizuje (potomci vybraných předků vypadnou) a řadí v pořadí stromu. Disciplína je pro strukturu
povinná a `done` bere karta z platné brány `synthesized` fragmentu F; chybí-li, 409 s výčtem v textu i strukturovaně
(`fragments: [{id, title, reason}]`, reason `not-live | no-discipline | no-synthesized | duplicate-card | card-closed`). Duplicitní značka
v kontejneru je 409. Dávka má nejvýš 200 uzlů; co se nevejde, ohlásí `skipped`. Otisk plánu = sha256
kanonického JSON (klíče seřazené, kolekce v pořadí generátoru, jen refy dávky a id existujících uzlů, bez časů;
položky `extend` nesou i revizi stavu a specu karty, takže změna karty mezi `planned` a `placed` = nové `planned`).
Nic nezapisuje: `dry_plan` dávku jen ověří přes `apply_plan` s `dryRun`.
"""

import hashlib
import json
import math

from backend.canvas.areas import area_of
from backend.canvas.graph import valid_id
from backend.editor.brief_vault.brief_vault_details import latest_details
from backend.editor.brief_vault.brief_vault_disciplines import (
    BY_ID,
    DISCIPLINES,
    GROUP_LABELS,
    group_of,
)
from backend.editor.brief_vault.brief_vault_gate_rules import gate_state, input_hash
from backend.editor.brief_vault.brief_vault_marks import marked
from backend.editor.brief_vault.brief_vault_model import (
    bad_request,
    blocked,
    effective_disciplines,
    fail,
    latest_rows,
    text_revisions,
)
from backend.editor.brief_vault.brief_vault_plan_cards import card_of
from backend.editor.brief_vault.brief_vault_plan_update import (
    existing_card,
    live_cards,
    research_steps,
    update_of,
)
from backend.editor.brief_vault.brief_vault_tree import live_ids, path_of

GENERATOR = 1
MAX_IDS = 500
MAX_PLAN_NODES = 200  # strop dávky `/api/canvas-plan` (canvas_plan_build.MAX_NODES)
# Nová oblast pojme sektory všech disciplín své skupiny v mřížce: karta 360 × 240, mezera 96, okraj 48.
CARD_W, CARD_H, GAP, PAD, AREA_COLUMNS = 360, 240, 96, 48, 4
MAX_LISTED = 20


def area_size(group):
    count = sum(1 for item in DISCIPLINES if item.group == group)
    columns = min(AREA_COLUMNS, count)
    rows = math.ceil(count / columns)
    return {"w": 2 * PAD + columns * CARD_W + (columns - 1) * GAP, "h": 2 * PAD + rows * CARD_H + (rows - 1) * GAP}


def plan_hash(plan):
    """sha256 kanonického JSON dávky."""
    raw = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _listed(rows):
    names = [f"„{row['title']}“ ({row['fragment_id']})" for row in rows[:MAX_LISTED]]
    return ", ".join(names) + (f" a dalších {len(rows) - MAX_LISTED}" if len(rows) > MAX_LISTED else "")


def _blockers(rows, reason):
    return [{"id": row["fragment_id"], "title": row["title"], "reason": reason} for row in rows]


def _ords(rows, fragment_id):
    path, cursor = [], fragment_id
    while cursor is not None:
        path.append(rows[cursor]["ord"])
        cursor = rows[cursor]["parent_id"]
    return tuple(reversed(path))


def selection(rows, fragment_ids):
    """Živé fragmenty `brief` z výběru bez potomků vybraných předků, v pořadí stromu."""
    if (not isinstance(fragment_ids, list) or not fragment_ids or len(fragment_ids) > MAX_IDS
            or any(not isinstance(item, str) or not valid_id(item) for item in fragment_ids)
            or len(set(fragment_ids)) != len(fragment_ids)):
        bad_request(f"fragmentIds musí být neprázdné pole nejvýše {MAX_IDS} různých id.")
    live = live_ids(rows)
    missing = [fid for fid in fragment_ids if fid not in live or rows[fid]["kind"] != "brief"]
    if missing:
        blocked("plán bere jen živé fragmenty druhu brief; neplatné: " + ", ".join(missing[:MAX_LISTED]) + ".",
                [{"id": fid, "title": (rows.get(fid) or {}).get("title", ""), "reason": "not-live"} for fid in missing])
    chosen = set(fragment_ids)

    def under_chosen(fid):
        cursor = rows[fid]["parent_id"]
        while cursor is not None:
            if cursor in chosen:
                return True
            cursor = rows[cursor]["parent_id"]
        return False

    kept = [fid for fid in fragment_ids if not under_chosen(fid)]
    root = {fid: path_of(rows, fid)[0]["id"] for fid in kept}
    return sorted(kept, key=lambda fid: (rows[root[fid]]["scope_node_id"] or "", _ords(rows, fid), fid))


def _children(rows):
    result = {}
    for row in rows.values():
        if not row["deleted"] and row["kind"] == "brief" and row["parent_id"] is not None:
            result.setdefault(row["parent_id"], []).append(row)
    for items in result.values():
        items.sort(key=lambda row: (row["ord"], row["fragment_id"]))
    return result


def _layer(graph, scope):
    """Vrstva plánu pro kořen schránky: sektor = dovnitř, karta (a jiné) = vedle ní, plátno = kořen (None)."""
    if not scope:
        return None
    node = next((item for item in graph["nodes"] if item["id"] == scope), None)
    if node is None:
        fail(f"schránka visí na uzlu {scope}, který na plátně už není; plán nemá kam karty vložit.")
    return node["id"] if node["kind"] == "sector" else node["parentId"]


def _cycles(rows, fragment_ids):
    """(F, karty, payload synthesized) pro každý vybraný F; nezařazené a chybějící synthesized = 409 s výčtem."""
    disciplines, kids = effective_disciplines(rows), _children(rows)
    cycles, unassigned, unsynthesized = [], [], []
    for fid in selection(rows, fragment_ids):
        units = kids.get(fid) or [rows[fid]]
        for row in (rows[fid], *units):
            if disciplines.get(row["fragment_id"]) is None and row not in unassigned:
                unassigned.append(row)
        discipline = disciplines.get(fid)
        state = gate_state(rows[fid], discipline) if discipline else None
        if state is not None and "synthesized" not in state["on"]:
            unsynthesized.append(rows[fid])
        synthesized = state["entries"]["synthesized"]["payload"] if state and "synthesized" in state["on"] else None
        cycles.append((fid, units, synthesized))
    # Text chyby jmenuje první důvod (jako dřív); `fragments` nese všechny dotčené fragmenty s důvodem.
    found = _blockers(unassigned, "no-discipline") + _blockers(unsynthesized, "no-synthesized")
    if unassigned:
        blocked("disciplína je pro strukturu povinná; nezařazené fragmenty: " + _listed(unassigned) + ".", found)
    if unsynthesized:
        blocked("chybí platná brána synthesized (done mikrokroku) u: " + _listed(unsynthesized) + ".", found)
    return cycles, disciplines, kids


def build_plan(rows, graph, state, texts, fragment_ids, details=None, revision=0, spec_revision=None):
    """Dávka `{nodes, edges, extend?}` pro výběr fragmentů + `skipped`, zdroje a vrstvy; ValueError = 409.

    `details` = {id: podrobnosti} (výzkum pro bloky karty), `revision` = revize stavu Desktop v3 a
    `spec_revision(id)` = revize specu existující karty (obojí jen pro položky `extend`)."""
    cycles, disciplines, kids = _cycles(rows, fragment_ids)
    details, spec_revision = details or {}, spec_revision or (lambda node_id: 0)
    marks = marked(graph, state)
    nodes, edges, extend, skipped, scopes, cards = [], [], [], 0, [], {}
    areas, sectors, sources = {}, {}, {}

    def existing(key, layer, value):
        ids = marks.get((key, layer, value), [])
        if len(ids) > 1:
            where = "na plátně" if layer is None else f"v kontejneru {layer}"
            fail(f"značku {key}={value} nese {where} víc uzlů ({', '.join(ids)}); nechte jeden, pak plánujte znovu.")
        return "@" + ids[0] if ids else None

    by_id = {node["id"]: node for node in graph["nodes"]}

    def sector_in(area, layer, discipline):
        """Označený sektor disciplíny v oblasti `area` (`@id`); mimo ni (nebo bez oblasti) = 409, ne druhý sektor."""
        found = existing("briefDiscipline", layer, discipline)
        if found is None:
            return None
        inside = area_of(by_id[found[1:]], graph["nodes"]) if area and area.startswith("@") else None
        if inside is None or inside["id"] != area[1:]:
            fail(f"sektor {found[1:]} se značkou briefDiscipline={discipline} leží mimo oblast skupiny "
                 f"{GROUP_LABELS[group_of(discipline)]}; přesuňte ho do ní, pak plánujte znovu.")
        return found

    for fid, units, synthesized in cycles:
        layer = _layer(graph, rows[path_of(rows, fid)[0]["id"]]["scope_node_id"])
        if layer not in scopes:
            scopes.append(layer)
            cards[layer] = live_cards(graph, state, layer)
        previous = None
        for row in (rows[fid], *units, *(kid for unit in units for kid in kids.get(unit["fragment_id"], []))):
            sources[row["fragment_id"]] = row
        for unit in units:
            uid = unit["fragment_id"]
            discipline = disciplines[uid]
            unit_kids = kids.get(uid, [])
            steps = [] if unit_kids else research_steps(rows, uid, details)
            path = [item["title"] for item in path_of(rows, uid)]
            current = existing_card(cards[layer], unit, state)
            if current is not None:
                if len(extend) >= MAX_PLAN_NODES:
                    skipped, previous = skipped + 1, None
                    continue
                card = card_of("u", "@" + current, unit, unit_kids, path, discipline,
                               texts.get(uid, unit["revision"]), synthesized, steps)
                extend.append(update_of(card, current, revision, spec_revision(current)))
                if previous is not None and not previous.startswith("@"):
                    edges.append({"from": previous, "to": "@" + current, "port": "next"})
                previous = "@" + current
                continue
            group = group_of(discipline)
            # Nejdřív oblast skupiny, pak sektor disciplíny v ní (podle skutečného id oblasti, ne jen vrstvy).
            area = areas.get((layer, group)) or existing("briefGroup", layer, group)
            sector = sectors.get((layer, discipline)) or sector_in(area, layer, discipline)
            new = []
            if area is None:
                area = f"a{len([n for n in nodes if n['kind'] == 'area']) + 1}"
                new.append({"ref": area, "kind": "area", "parent": None if layer is None else "@" + layer,
                            "name": GROUP_LABELS[group], "size": area_size(group), "briefGroup": group})
            if sector is None:
                sector = f"s{len([n for n in nodes if n['kind'] == 'sector']) + 1}"
                new.append({"ref": sector, "kind": "sector", "parent": area, "name": BY_ID[discipline].label,
                            "briefDiscipline": discipline})
            if len(nodes) + len(new) + 1 > MAX_PLAN_NODES:
                skipped, previous = skipped + 1, None
                continue
            for item in new:
                (areas if item["kind"] == "area" else sectors)[
                    (layer, group if item["kind"] == "area" else discipline)] = item["ref"]
            nodes.extend(new)
            ref = f"f{len([n for n in nodes if n['kind'] == 'node']) + 1}"
            nodes.append(card_of(ref, sector, unit, unit_kids, path, discipline,
                                 texts.get(uid, unit["revision"]), synthesized, steps))
            if previous is not None:
                edges.append({"from": previous, "to": ref, "port": "next"})
            previous = ref
    plan = {"nodes": nodes, "edges": edges, **({"extend": extend} if extend else {})}
    return {"plan": plan, "skipped": skipped, "scopes": ["" if s is None else s for s in scopes],
            "sourceRevisions": {fid: row["revision"] for fid, row in sources.items()},
            "sourceHashes": {fid: input_hash(row["title"], row["text"], disciplines.get(fid)) for fid, row in sources.items()}}


def read_plan(canvas, store, project, workspace, view, fragment_ids):
    """Plán nad aktuálním stavem; volající drží zámek grafu."""
    with canvas.lock_for(project):
        db = canvas.db_for(project)
        rows, texts = latest_rows(db, project, workspace), text_revisions(db, project, workspace)
        current = store.current(project, workspace)
        research = [fid for fid, row in rows.items() if row["kind"] == "research" and not row["deleted"]]
        details = {fid: item["fields"] for fid, item in latest_details(db, project, workspace, research).items()}
    return build_plan(rows, view["graph"], current["state"], texts, fragment_ids, details, current["revision"],
                      lambda node_id: canvas.specs.read((project, workspace, node_id))["revision"])


def dry_plan(canvas, store, project, workspace, fragment_ids, actor="system"):
    """`POST /api/brief-vault/plan`: plán + ověření dávky přes canvas-plan (`dryRun`), nic se nezapíše."""
    from backend.canvas.canvas_plan import apply_plan
    with canvas.graph_lock_for(project):
        view = canvas.view(project, workspace)
        if view["readOnly"]:
            fail("main je pouze pro čtení; plán se skládá v pracovním prostoru.")
        built = read_plan(canvas, store, project, workspace, view, fragment_ids)
        checked = apply_plan(canvas, {"project": project, "workspace": workspace, "digest": view["digest"],
                                      "dryRun": True, "plan": built["plan"]}, actor=actor)
        return {**built, "hash": plan_hash(built["plan"]), "summary": checked["summary"], "digest": view["digest"],
                "generator": GENERATOR}
