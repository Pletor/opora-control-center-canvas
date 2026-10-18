"""Značky struktury Schránky ve stavu uzlu (docs/schranka-neurony.md §4, §9 bod 1).

Plán struktury pozná svou oblast a svůj sektor podle značky ve stavu uzlu Desktop v3, ne podle názvu:
oblast skupiny nese `briefGroup` (`kresleni` | `logika` | `provoz`), sektor disciplíny `briefDiscipline`
(id z §2). Značku zapisuje dávka `/api/canvas-plan` (pole uzlu dávky se stejným jménem) stejně jako
`fragmentRef`; `validate_state` hlídá hodnotu. V jednom kontejneru (vrstva = `parentId`) smí být každá
značka nejvýš jednou: dávka, která by vyrobila druhou, je 409 a plán Schránky existující duplicitu odmítne.
"""

from backend.editor.brief_vault.brief_vault_disciplines import DISCIPLINE_IDS, GROUPS

# Značka → druh uzlu, který ji smí nést.
MARK_KINDS = {"briefGroup": "area", "briefDiscipline": "sector"}
MARK_VALUES = {"briefGroup": GROUPS, "briefDiscipline": DISCIPLINE_IDS}


def validate_marks(node, node_id):
    """Hodnoty značek ve stavu uzlu (volá `validate_state`)."""
    for key, allowed in MARK_VALUES.items():
        if key in node and (not isinstance(node[key], str) or node[key] not in allowed):
            raise ValueError(f"Neplatný stav Desktop v3: {key}[{node_id}] musí být jedna z {', '.join(allowed)}.")


def plan_marks(built, item, node_id):
    """Značky z položky dávky plánu → stav nového uzlu (oblast dostane minimální stav uzlu)."""
    for key, kind in MARK_KINDS.items():
        if key not in item:
            continue
        if item["kind"] != kind:
            raise ValueError(f"{item['ref']}: {key} nese jen uzel druhu {kind}.")
        validate_marks({key: item[key]}, item["ref"])
        node = built.state["nodes"].setdefault(node_id, {"phase": "discover", "criteria": [], "steps": []})
        node[key] = item[key]
        built.state_changed = True


def marked(graph, state):
    """{(značka, kontejner, hodnota): [id uzlů]} pro uzly správného druhu se značkou ve stavu."""
    found = {}
    nodes_state = (state or {}).get("nodes", {})
    for node in graph["nodes"]:
        for key, kind in MARK_KINDS.items():
            value = nodes_state.get(node["id"], {}).get(key)
            if node["kind"] == kind and value is not None:
                found.setdefault((key, node["parentId"], value), []).append(node["id"])
    return found


def duplicates(graph, state, only=None):
    """Značky, které v kontejneru nese víc uzlů; `only` = jen skupiny, kterých se týkají tato id."""
    return [(key, container, value, ids) for (key, container, value), ids in marked(graph, state).items()
            if len(ids) > 1 and (only is None or set(ids) & only)]


def check_unique(graph, state, new_ids):
    """Dávka nesmí založit druhou oblast se stejnou `briefGroup` (či sektor se stejnou `briefDiscipline`)
    ve stejném kontejneru; ValueError = 409."""
    clash = duplicates(graph, state, set(new_ids))
    if clash:
        key, container, value, _ids = clash[0]
        where = "na plátně" if container is None else f"v kontejneru {container}"
        raise ValueError(f"Značka {key}={value} už {where} existuje; použijte existující uzel (@id).")
