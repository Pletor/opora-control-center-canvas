"""Technický model domény Studia (`docs/studio.md` §4): čtení a uložení s optimistickou revizí.

Model `opora.studio-model/1` je vlastní definice na doménu, oddělená od grafu práce agentů: nikdy se nepíše do grafu
(`/api/graph`), graf se jen čte kvůli `binding.nodeId`. Leží v `studio_models` v `project.sqlite` (schéma
`database/schema/studio_model_schema.py`, přístup `database/repositories/studio_models.py`), jedna aktuální verze
na doménu, bez historie.

- Validace (chyba = `StudioModelInvalid`, HTTP 422) hlídá jen tvar: `schema`, `domainId` shodné s doménou dotazu,
  `revision` celé ≥ 0, ≤ 1000 uzlů a ≤ 5000 hran, jedinečná `id` (1–128 znaků) uzlů i hran, uzel
  `{id, type, name, position: {x, y}, config: {}, binding?: {nodeId}}`, hrana
  `{id, from: {nodeId, portId}, to: {nodeId, portId}, type, enabled, label?, condition?}` s `type` z 12 datových
  typů portu a konci na existujících uzlech. Typy komponent, jejich porty a pravidla rolí backend nevaliduje:
  katalog žije ve frontendu (`frontend/project/studio/model/`). Velikost těla ≤ 1 MiB hlídá router.
- `binding.nodeId` musí být uzel přijatého grafu projektu (`architecture_graph`), jinak 422.
- Zápis nese `revision`, ze které model vychází; jiná než uložená (nový model = 0) je `StudioModelConflict` (409).
  Uložený model dostane `revision + 1` a `updatedAt`.
"""

import math
from datetime import UTC, datetime

from backend.project.architecture.work_status import architecture_graph
from database.repositories.studio_models import StudioModelStore

SCHEMA = "opora.studio-model/1"
BODY_LIMIT = 1024 * 1024
MAX_NODES, MAX_EDGES = 1000, 5000
PORT_TYPES = {"http-request", "cache-command", "record-command", "health", "sql-query", "event", "telemetry",
              "search-query", "data", "job", "sql-result", "sql-replication"}
SERVER_KEYS = {"revision", "updatedAt"}


class StudioModelInvalid(ValueError):
    """Model nemá předepsaný tvar nebo váže neexistující kartu (HTTP 422)."""


class StudioModelConflict(Exception):
    """Model mezitím uložil někdo jiný (HTTP 409)."""


def _text(value, name, limit, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value) <= limit:
        raise StudioModelInvalid(f"{name} musí být text o {minimum}–{limit} znacích.")
    return value


def _object(value, name):
    if not isinstance(value, dict):
        raise StudioModelInvalid(f"{name} musí být objekt.")
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise StudioModelInvalid(f"{name} musí být konečné číslo.")


def _unique(items, name, limit):
    if not isinstance(items, list):
        raise StudioModelInvalid(f"{name} musí být pole.")
    if len(items) > limit:
        raise StudioModelInvalid(f"Překročen limit {MAX_NODES} komponent / {MAX_EDGES} vazeb.")
    seen = set()
    for item in items:
        identity = _text(_object(item, name).get("id"), f"{name}.id", 128)
        if identity in seen:
            raise StudioModelInvalid(f"{name}: duplicitní id {identity}.")
        seen.add(identity)
    return seen


def _node(node):
    _text(node.get("type"), "Typ komponenty", 128)
    _text(node.get("name"), "Název komponenty", 200)
    position = _object(node.get("position"), "position")
    _number(position.get("x"), "position.x")
    _number(position.get("y"), "position.y")
    _object(node.get("config"), "config")
    if "binding" in node:
        _text(_object(node["binding"], "binding").get("nodeId"), "binding.nodeId", 128)


def _edge(edge, nodes):
    for end in ("from", "to"):
        ref = _object(edge.get(end), end)
        if _text(ref.get("nodeId"), f"{end}.nodeId", 128) not in nodes:
            raise StudioModelInvalid(f"Vazba {edge['id']} vede na neexistující komponentu.")
        _text(ref.get("portId"), f"{end}.portId", 128)
    if edge.get("type") not in PORT_TYPES:
        raise StudioModelInvalid(f"Vazba {edge['id']} nemá datový typ portu.")
    if not isinstance(edge.get("enabled"), bool):
        raise StudioModelInvalid("enabled vazby musí být true nebo false.")
    if "label" in edge:
        _text(edge["label"], "label", 200, minimum=0)
    if "condition" in edge:
        _text(edge["condition"], "condition", 2000, minimum=0)


def validate_model(body, domain):
    """Ověří tvar modelu domény `domain`; vrací množinu `binding.nodeId`."""
    _object(body, "Model")
    if body.get("schema") != SCHEMA:
        raise StudioModelInvalid(f"schema musí být {SCHEMA}.")
    if body.get("domainId") != domain:
        raise StudioModelInvalid("domainId modelu se neshoduje s doménou dotazu.")
    revision = body.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise StudioModelInvalid("revision musí být celé číslo ≥ 0.")
    nodes = _unique(body.get("nodes"), "nodes", MAX_NODES)
    _unique(body.get("edges"), "edges", MAX_EDGES)
    for node in body["nodes"]:
        _node(node)
    for edge in body["edges"]:
        _edge(edge, nodes)
    return {node["binding"]["nodeId"] for node in body["nodes"] if "binding" in node}


def empty_model(domain):
    return {"schema": SCHEMA, "domainId": domain, "revision": 0, "nodes": [], "edges": [], "updatedAt": None}


def read_model(service, project, domain):
    """Aktuální model domény; když ho nikdo neuložil, prázdný model s `revision: 0`."""
    with service.reading(project):
        current = StudioModelStore(service.db_for(project), project).get(domain)
    if current is None:
        return empty_model(domain)
    revision, model, updated_at = current
    return {**model, "revision": revision, "updatedAt": updated_at}


def write_model(service, project, domain, body):
    """Ověří model a uloží ho nad revizí, ze které vychází; vrací uložený model s novou revizí."""
    bindings = validate_model(body, domain)
    if bindings:
        known = {node["id"] for node in architecture_graph(service, project)["nodes"]}
        missing = sorted(bindings - known)
        if missing:
            raise StudioModelInvalid(f"binding.nodeId neexistuje v grafu projektu: {', '.join(missing)}.")
    model = {key: value for key, value in body.items() if key not in SERVER_KEYS}
    updated_at = datetime.now(UTC).isoformat(timespec="microseconds")
    db = service.db_for(project)
    with service.lock_for(project), db:
        db.execute("BEGIN IMMEDIATE")
        store = StudioModelStore(db, project)
        current = store.get(domain)
        stored = current[0] if current else 0
        if body["revision"] != stored:
            raise StudioModelConflict(f"Model domény mezitím uložil někdo jiný (revize {stored}, zápis nad {body['revision']}).")
        store.put(domain, stored + 1, model, updated_at)
    return {**model, "revision": stored + 1, "updatedAt": updated_at}
