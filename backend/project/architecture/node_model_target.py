"""Cíl z MODELu pro agenta: `node-brief.architecture.model` (`docs/studio.md` §4a).

MODEL říká, kam se aplikace musí dostat; kartě OPORY se z něj předá zadaný cíl, nikdy výsledek simulace (rps,
využití, latence). Čtení modelu je jediné I/O (`read_model_target`); výřez z načteného modelu je čistá funkce.

- Doména karty = aplikace karty: karta sama, když je aplikací (`site.kind == "application"`), jinak nejbližší
  aplikace mezi předky po `parentId` (stejně jako `domainOf` ve frontendu `studio-tree.ts`). Model se čte jen
  z této domény (`studio_models`), nikdy z domén scénářů `scenario:*`. Karta mimo aplikaci cíl nedostane.
- Uzel modelu s `binding.nodeId == karta`; víc uzlů na jednu kartu → první podle `id` uzlu.
- `targets`: klíče `config.model` uzlu, tedy parametry, které zapsal člověk v inspektoru (inspektor zapisuje jen
  změněný klíč). Výjimka: výchozí hodnoty, které frontend uloží už při vzniku komponenty (`withSimulationDefaults`
  v `frontend/project/studio/model/simulation/logic/model-adapter.ts`: Service `telemetryRate: 0.01`, Kubernetes
  Deployment `crashAfterTicks: 3`), do `targets` jdou jen, když se od nich liší. Obecné výchozí hodnoty
  (`simulation-config.ts` `defaults`) se neukládají, proto se s nimi neporovnává: klíč v `config.model` je zadaný.
- `mustSurvive`: druhy plánovaných incidentů `modelDefinition.incidents[]` s uzlem v `nodeIds`, každý jednou,
  v pořadí prvního výskytu; `restore` není incident, který by uzel musel vydržet, proto se vynechá.
- `links`: zapnuté hrany uzlu v pořadí `id`, nejvýš `LINKS_LIMIT`: `{to, type}` u odchozí, `{from, type}`
  u příchozí; protějšek je název uzlu (bez názvu jeho id).
- Bez výchozích hodnot: prázdné `targets`, `mustSurvive` i `links` se vynechají. `tech` z příkladu kontraktu
  backend nemá odkud vzít (katalog typů žije ve frontendu), proto se nepíše; `type` je id typu z katalogu.
"""

from backend.project.studio.studio_model import read_model

SOURCE = "MODEL – cíl, ne měření"
SCENARIO_PREFIX = "scenario:"
LINKS_LIMIT = 5
# Výchozí `config.model`, které frontend zapíše už při vzniku komponenty (`withSimulationDefaults`).
CREATION_DEFAULTS = {"service": {"telemetryRate": 0.01}, "kubernetes-deployment": {"crashAfterTicks": 3}}
NOT_SURVIVED = {"restore"}


def _is_application(node):
    return isinstance(node.get("site"), dict) and node["site"].get("kind") == "application"


def domain_of(graph, node_id):
    """Id aplikace karty (karta sama nebo nejbližší předek), nebo None, když karta pod aplikací neleží."""
    by_id = {node["id"]: node for node in graph.get("nodes") or []}
    seen, current = set(), node_id
    while current in by_id and current not in seen:
        if _is_application(by_id[current]):
            return current
        seen.add(current)
        current = by_id[current].get("parentId")
    return None


def _targets(node):
    given = (node.get("config") or {}).get("model")
    if not isinstance(given, dict):
        return {}
    seeded = CREATION_DEFAULTS.get(node.get("type"), {})
    return {key: value for key, value in given.items() if key not in seeded or seeded[key] != value}


def _must_survive(model, node_id):
    definition = model.get("modelDefinition")
    incidents = definition.get("incidents") if isinstance(definition, dict) else None
    kinds = []
    for incident in incidents if isinstance(incidents, list) else []:
        if not isinstance(incident, dict) or node_id not in (incident.get("nodeIds") or []):
            continue
        kind = incident.get("kind")
        if isinstance(kind, str) and kind not in NOT_SURVIVED and kind not in kinds:
            kinds.append(kind)
    return kinds


def _links(model, node_id):
    names = {node["id"]: node.get("name") or node["id"] for node in model.get("nodes") or []}
    links = []
    for edge in sorted(model.get("edges") or [], key=lambda e: e["id"]):
        if not edge.get("enabled"):
            continue
        if edge["from"]["nodeId"] == node_id:
            links.append({"to": names.get(edge["to"]["nodeId"], edge["to"]["nodeId"]), "type": edge["type"]})
        elif edge["to"]["nodeId"] == node_id:
            links.append({"from": names.get(edge["from"]["nodeId"], edge["from"]["nodeId"]), "type": edge["type"]})
    return links[:LINKS_LIMIT]


def model_target(model, card_id):
    """Cíl z modelu domény pro kartu `card_id`, nebo None, když na kartu žádný uzel modelu neváže."""
    bound = sorted((node for node in model.get("nodes") or []
                    if isinstance(node.get("binding"), dict) and node["binding"].get("nodeId") == card_id),
                   key=lambda node: node["id"])
    if not bound:
        return None
    node = bound[0]
    parts = {"targets": _targets(node), "mustSurvive": _must_survive(model, node["id"]),
             "links": _links(model, node["id"])}
    return {"source": SOURCE, "domain": model["domainId"], "revision": model["revision"],
            "type": node["type"], "name": node["name"], **{key: value for key, value in parts.items() if value}}


def read_model_target(service, project, graph, card_id):
    """Cíl z MODELu domény karty (§4a), nebo None: karta mimo aplikaci, doména scénáře nebo bez vazby."""
    domain = domain_of(graph, card_id)
    if domain is None or domain.startswith(SCENARIO_PREFIX):
        return None
    return model_target(read_model(service, project, domain), card_id)
