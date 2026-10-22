"""Rules affecting a card, including local ancestor rules and explicit provenance."""


def effective_rules(graph, state, node_id):
    by_id = {node["id"]: node for node in graph["nodes"]}
    lineage, cursor = [], node_id
    while cursor in by_id and cursor not in lineage:
        lineage.append(cursor)
        cursor = by_id[cursor]["parentId"]
    path = (by_id.get(node_id, {}).get("sourceRef") or {}).get("path", "")

    def origin(owner, storage, scope=None, target=""):
        node = by_id.get(owner, {})
        return {"scope": scope or ("sector" if node.get("kind") == "sector" else "card"),
                "nodeId": owner, "name": node.get("name", ""), "path": target, "storage": storage}

    rows = []
    for rule in state["rules"]:
        if rule.get("by") == "agent":
            continue  # návrh agenta neplatí, dokud ho neschválí člověk (upgrade-opora #37)
        scope, target = rule["scope"], rule["target"]
        if scope == "project":
            source = origin("", "project", "project")
        elif scope == "path" and path and (path == target or path.startswith(target + "/")):
            source = origin("", "project", "path", target)
        elif scope == "node" and target in lineage:
            source = origin(target, "project")
        else:
            continue
        rows.append({**rule, "origin": source, "inherited": source["nodeId"] != node_id})
    for owner in reversed(lineage):
        for rule in state["nodes"].get(owner, {}).get("rules", []):
            rows.append({**rule, "origin": origin(owner, "node"), "inherited": owner != node_id})
    return rows


STATE_ENDPOINT = "/api/desktop-v3/state"


def proposed_rules(scoped_rules, all_rules, project, workspace):
    """Návrhy pravidel agentů pro brief: jen ty v rozsahu karty, zbytek odkazem.

    Rozsah je stejný jako u schválených pravidel (`memory_for`): `scope: project`, `scope: path`
    nad cestou karty a `scope: node` s cílem na kartě nebo předkovi. Dřív brief nesl všechny
    návrhy prostoru (měřeno 23. 10.: 115 ze 115 patřilo jiným kartám, 25,6 kB). Nic se nemaže:
    úplný seznam je ve stavu prostoru, `proposedRulesElsewhere` nese počet a kde ho přečíst.
    """
    proposed = [rule for rule in scoped_rules if rule.get("by") == "agent"]
    total = sum(1 for rule in all_rules if rule.get("by") == "agent")
    return {
        "proposedRules": proposed,
        "proposedRulesElsewhere": {
            "count": total - len(proposed), "endpoint": STATE_ENDPOINT,
            "params": {"project": project, "workspace": workspace}, "select": "state.rules[by=agent]",
            "note": "Návrhy pravidel jiných karet; nedopadají na tuto kartu a neplatí, dokud je neschválí člověk.",
        },
    }
