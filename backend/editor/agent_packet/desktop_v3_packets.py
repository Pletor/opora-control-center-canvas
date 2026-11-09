"""Sdílené sestavení podkladů pro agenta (opora.packet/1) a neměnné snapshoty.

Jedna pravda pro Desktop v3 balíček: uložené kresby uzlu a všech předků s revizí,
texty a zadání, návrhové vztahy, pravidla/rozhodnutí/tickety z paměti projektu a
uložená dokumentace cest. `sessionId` je jen rozsah (tickety session v paměti);
žádný běh modelu se do podkladů nevkládá. Reference zůstávají referencemi (obsah
souborů se nečte); limit nikdy nevynechá obsah potichu, každý zdroj má položku
v sourceManifest.
"""

import hashlib
import json
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.graph import encode, valid_id
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.redact import redact_text
from backend.editor.node.node_journal import NodeJournal
from backend.project.workspace.workspace_documents import WorkspaceDocuments
from backend.project.workspace.workspace_sources import SourceMissing, relative_path

SCHEMA = "opora.packet/1"
MAX_PACKET_BYTES = 900_000
MAX_REFERENCES = 50
MAX_NOTE = 4000
MAX_JOURNAL_DAYS = 7
MAX_SESSION_ID = 120
EXCLUDED_PATHS = [".env", ".data", "node_modules", ".git", "keys", "transcripts"]
REQUEST_KEYS = {"project", "workspace", "nodeId", "path", "sessionId", "references", "note"}
ELEMENT_KEYS = (
    "id", "type", "x", "y", "width", "height", "angle", "strokeColor", "backgroundColor",
    "text", "points", "startBinding", "endBinding", "containerId", "frameId", "groupIds", "link",
)


def redact_deep(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_deep(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_deep(item) for key, item in value.items()}
    return value


def _byte_len(value):
    return len(encode(value).encode("utf-8"))


def packet_digest(packet):
    return hashlib.sha256(encode(packet).encode("utf-8")).hexdigest()


def _manifest(kind, owner, revision, included, reason):
    return {"kind": kind, "ownerId": owner, "revision": revision, "included": included, "reason": reason}


def active_elements(drawing):
    scene = drawing.get("scene", {}) if isinstance(drawing, dict) else {}
    raw = scene.get("elements", []) if isinstance(scene, dict) else []
    return [
        item for item in raw
        if isinstance(item, dict) and isinstance(item.get("id"), str)
        and isinstance(item.get("type"), str) and not item.get("isDeleted")
    ]


def project_drawing(layer, drawing):
    """Deterministická projekce uložené kresby: aktivní prvky, geometrie šipek, popisky."""
    elements = active_elements(drawing)
    bound_text = {
        item["containerId"]: item["text"] for item in elements
        if isinstance(item.get("containerId"), str) and isinstance(item.get("text"), str)
    }
    projected = []
    for item in elements:
        record = {key: item[key] for key in ELEMENT_KEYS if key in item}
        label = item.get("name") or item.get("text") or bound_text.get(item["id"])
        record["label"] = label if isinstance(label, str) else ""
        custom = item.get("customData")
        metadata = custom.get("oporaWireframe") if isinstance(custom, dict) else None
        if isinstance(metadata, dict):
            record["wireframe"] = metadata
        projected.append(record)
    return {
        "layer": layer,
        "revision": drawing.get("revision", 0),
        "savedAt": drawing.get("saved_at"),
        "available": bool(drawing.get("available", True)),
        "elementCount": len(projected),
        "elements": projected,
    }


def ancestor_ids(by_id, node_id):
    chain = []
    current = by_id[node_id]["parentId"] if node_id else None
    while current is not None and current in by_id and current not in chain:
        chain.append(current)
        current = by_id[current]["parentId"]
    return chain


def drawing_layers(by_id, node_id):
    layers = [node_id] if node_id else []
    layers.extend(ancestor_ids(by_id, node_id))
    layers.append("")
    return list(dict.fromkeys(layers))


def _path_matches(target, paths):
    return any(path == target or path.startswith(target + "/") for path in paths)


def memory_for(stored, node_ids, paths, session_id):
    """Výřez paměti projektu, který dopadá na uzel (a předky), cesty a session; redigovaný."""
    state = stored["state"]
    node_ids = [item for item in node_ids if item]
    paths = [item for item in paths if item]
    focus = node_ids[0] if node_ids else ""
    rules = [
        rule for rule in state["rules"]
        if rule["scope"] == "project"
        or (rule["scope"] == "path" and _path_matches(rule["target"], paths))
        or (rule["scope"] == "node" and rule["target"] in node_ids)
    ]
    decisions = [
        item for item in state["decisions"]
        if item["pinned"]
        or (item["nodeId"] and item["nodeId"] in node_ids)
        or (item["path"] and _path_matches(item["path"], paths))
    ]
    tickets = [
        item for item in state["tickets"]
        if (item["nodeId"] and item["nodeId"] == focus)
        or (item["sessionId"] and item["sessionId"] == session_id)
    ]
    # Fáze, kritéria a kroky jsou tolerovaná stará data stavu; balíček je nenese.
    node_state = state["nodes"].get(focus, {})
    return redact_deep({
        "revision": stored["revision"],
        "settings": list(state["settings"]),
        "rules": rules,
        "decisions": decisions,
        "tickets": tickets,
        # Bloky z portů karty: pořadí akcí je pořadí pipeline; starší uzel bez bloků má prázdné pole.
        "actions": node_state.get("actions", []),
        "nodeRules": node_state.get("rules", []),
        "blocks": node_state.get("blocks", []),
        # Podklady z portu karty: jen odkazy (soubor, cesta, URL) a popisky; obsah se nevkládá.
        "materials": [{**m, "contentIncluded": False} for m in node_state.get("materials", [])],
    })


def _branch_label(branch, blocks, by_id, actions):
    kind, target = branch["kind"], branch["targetId"]
    if kind == "block":
        return next((b["title"] for b in blocks if b["id"] == target), target)
    if kind == "node":
        return by_id[target]["name"] if target in by_id else target
    if kind == "action":
        return next((a["label"] for a in actions if a["id"] == target), target)
    return ""


def _number_key(number):
    return tuple(int(part) for part in number.split("."))


def big_picture(blocks):
    """Celý obraz: každý blok jen s číslem, názvem, stavem a štítky; texty patří jen aktuálnímu kroku."""
    return [
        {"id": b["id"], "number": b["number"], "title": b["title"], "status": b["state"]["status"],
         "tags": list(b["tags"]), "parentBlockId": b["parentBlockId"]}
        for b in sorted(blocks, key=lambda b: _number_key(b["number"]))
    ]


def current_step(blocks, by_id, actions, block_id=""):
    """Jeden krok pro agenta: vyžádaný blok, jinak první otevřený v pořadí čísel; None bez bloků."""
    ordered = sorted(blocks, key=lambda b: _number_key(b["number"]))
    if block_id:
        chosen = next((b for b in ordered if b["id"] == block_id), None)
        if chosen is None:
            raise ValueError(f"Blok {block_id} v tomto uzlu neexistuje.")
    else:
        chosen = next((b for b in ordered if b["state"]["status"] == "open"), None)
    if chosen is None:
        return None
    return {
        "id": chosen["id"], "number": chosen["number"], "title": chosen["title"], "text": chosen["text"],
        "tags": list(chosen["tags"]), "parentBlockId": chosen["parentBlockId"],
        "todos": [dict(t) for t in chosen["todos"]],
        # Obrázek je inspirace jako reference: cesta a popisek, obsah se do podkladů nečte.
        "images": [{**i, "contentIncluded": False} for i in chosen["images"]],
        "state": {
            "status": chosen["state"]["status"], "condition": chosen["state"]["condition"],
            "onMet": {**chosen["state"]["onMet"], "label": _branch_label(chosen["state"]["onMet"], blocks, by_id, actions)},
            "onUnmet": {**chosen["state"]["onUnmet"], "label": _branch_label(chosen["state"]["onUnmet"], blocks, by_id, actions)},
        },
    }


def edge_port(edge):
    """Vazba bez portu je starší zápis a znamená `next`."""
    return edge.get("port", "next")


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) not in (REQUEST_KEYS, REQUEST_KEYS | {"blockId"}):
        raise ValueError("Neplatný formát požadavku na podklady (project, workspace, nodeId, path, sessionId, references, note[, blockId]).")
    block_id = payload.get("blockId", "")
    if block_id != "" and not valid_id(block_id):
        raise ValueError("Neplatný identifikátor bloku.")
    project, workspace, node = payload["project"], payload["workspace"], payload["nodeId"]
    if not isinstance(project, str) or (project != "draft" and not valid_id(project)) or not valid_id(workspace):
        raise ValueError("Neplatný identifikátor projektu nebo pracovního prostoru.")
    if node != "" and not valid_id(node):
        raise ValueError("Neplatný identifikátor uzlu.")
    try:
        relative_path(payload["path"])
    except ValueError:
        raise ValueError("Neplatná cesta podkladů; použijte relativní cestu nebo prázdný koncept.")
    session = payload["sessionId"]
    if not isinstance(session, str) or len(session) > MAX_SESSION_ID or "\0" in session:
        raise ValueError("Neplatné ID session.")
    references = payload["references"]
    if not isinstance(references, list) or len(references) > MAX_REFERENCES:
        raise ValueError(f"Reference musí být pole nejvýše {MAX_REFERENCES} cest.")
    for item in references:
        try:
            if not isinstance(item, str) or item == "":
                raise ValueError
            relative_path(item)
        except ValueError:
            raise ValueError("Reference musí být platné relativní cesty.")
    note = payload["note"]
    if not isinstance(note, str) or len(note) > MAX_NOTE or "\0" in note:
        raise ValueError(f"Poznámka může mít nejvýše {MAX_NOTE} znaků.")
    return payload


class DesktopV3Packets:
    def __init__(self, canvas, state_store=None):
        self.canvas = canvas
        self.state = state_store or DesktopV3State(canvas)
        self.journal = NodeJournal(canvas)
        self.documents = WorkspaceDocuments(canvas, canvas.workspace_sources)

    # ---- sestavení -----------------------------------------------------------------

    def _path_status(self, project, workspace, path):
        try:
            root = self.canvas.workspace_sources.root(project, workspace)
        except SourceMissing:
            return False, "source_unavailable"
        except ValueError:
            return False, "source_invalid"
        if root is None:
            return False, "no_source_root"
        try:
            self.canvas.workspace_sources.target(root, path)
        except FileNotFoundError:
            return False, "not_found"
        except (OSError, ValueError):
            return False, "source_invalid"
        return True, "exists"

    def _document(self, project, workspace, path):
        try:
            item = self.documents.read(project, workspace, path)
        except SourceMissing:
            return None, "source_unavailable"
        except ValueError:
            return None, "no_saved_document"
        if item["revision"] == 0:
            return None, "no_saved_document"
        return {
            "path": item["path"], "nodeId": item["nodeId"], "revision": item["revision"],
            "savedAt": item["savedAt"], "status": item["status"], "fields": item["fields"],
        }, "saved_document"

    def _assemble(self, payload):
        project, workspace, node = payload["project"], payload["workspace"], payload["nodeId"]
        path, session, references, note = payload["path"], payload["sessionId"], payload["references"], payload["note"]
        view = self.canvas.view(project, workspace)
        if view["readOnly"]:
            raise ValueError("Podklady se sestavují z pracovního prostoru; main je pouze pro čtení.")
        graph = view["graph"]
        by_id = {item["id"]: item for item in graph["nodes"]}
        if node and node not in by_id:
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        config = self.canvas.project_hub.settings(project)
        ancestors = ancestor_ids(by_id, node)
        lineage = [node, *ancestors] if node else []
        lineage_set = set(lineage)

        def summary(nid):
            if nid == "":
                # Projekt/cesta je rozsah zadání, nikoli vymyšlený uzel grafu.
                return {"nodeId": "", "name": path or config["project"]["name"],
                        "kind": "path" if path else "project", "purpose": config["settings"]["goal"],
                        "parentId": None, "sourceRef": None}
            item = by_id[nid]
            return {
                "nodeId": nid, "name": item["name"], "kind": item["kind"],
                "purpose": item["purpose"], "parentId": item["parentId"],
                "sourceRef": item.get("sourceRef"),
            }

        focus = by_id[node] if node else {}
        focus_path = (focus.get("sourceRef") or {}).get("path", "")
        lineage_paths = [(by_id[nid].get("sourceRef") or {}).get("path", "") for nid in lineage]
        rule_paths = list(dict.fromkeys(item for item in [path, focus_path] if item))
        manifest, warnings = [], []
        manifest.append(_manifest("graph", "", None, True, "saved_graph"))
        stored = self.state.current(project, workspace)
        memory = memory_for(stored, lineage, rule_paths, session)
        manifest.append(_manifest("memory", "", stored["revision"], True, "saved_state" if stored["revision"] else "empty_default"))

        spec = self.canvas.specs.read((project, workspace, node))
        text = self.canvas.texts.read((project, workspace, node))
        manifest.append(_manifest("spec", node, spec["revision"], spec["revision"] > 0, "saved_spec" if spec["revision"] else "no_saved_spec"))
        manifest.append(_manifest("text", node, text["revision"], text["revision"] > 0, "saved_text" if text["revision"] else "no_saved_text"))
        if path:
            exists, reason = self._path_status(project, workspace, path)
            manifest.append(_manifest("path", path, None, exists, reason))
            if not exists:
                warnings.append(f"Cesta {path} není ve zdroji dostupná ({reason}); podklady ji vedou jen jako referenci.")
        for reference in list(dict.fromkeys(references)):
            manifest.append(_manifest("reference", reference, None, False, "reference_only"))

        packet = {
            "schema": SCHEMA,
            "scope": {"project": project, "workspace": workspace, "nodeId": node, "path": path, "sessionId": session},
            "task": {
                **summary(node),
                "path": path,
                "note": note,
                "references": [{"path": item, "mode": "reference", "contentIncluded": False} for item in dict.fromkeys(references)],
                "spec": {"revision": spec["revision"], "fields": spec["fields"]},
                "text": {"revision": text["revision"], "text": text["text"]},
                # Jen `next` určuje pořadí práce; rule/action/block/flow jsou jiné souvislosti.
                # Neuložená fáze není důkaz discover ani dokončení: zůstává null.
                "depends_on": [
                    {**summary(nid), "status": stored["state"]["nodes"].get(nid, {}).get("phase"),
                     "statusSource": "desktop-v3/state", "stateRevision": stored["revision"]}
                    for nid in sorted({edge["source"] for edge in graph["edges"]
                                       if edge["target"] == node and not edge.get("relation") and edge_port(edge) == "next"})
                ],
                # Co má agent na uzlu vykonat (pipeline v pořadí) a jaká pravidla pro uzel platí.
                "actions": memory["actions"],
                "rules": memory["nodeRules"],
                # Velký obraz (všechny bloky bez textů) a jeden aktuální krok (plný obsah).
                "bigPicture": big_picture(memory["blocks"]),
                "currentStep": current_step(memory["blocks"], by_id, memory["actions"], payload.get("blockId", "")),
                "processes": {"actions": memory["actions"], "rules": memory["nodeRules"]},
                # Odchozí vazby z portu `next`: kam workflow pokračuje po tomto uzlu.
                "next": [
                    {"nodeId": edge["target"], "name": by_id[edge["target"]]["name"], "edgeId": edge["id"], "port": "next"}
                    for edge in graph["edges"]
                    if edge["source"] == node and not edge.get("relation") and edge_port(edge) == "next" and edge["target"] in by_id
                ],
            },
            "context": {
                "project": {key: config["project"].get(key) for key in ("id", "name", "sourceKind")},
                "projectSettings": {"revision": config["revision"], "goal": config["settings"]["goal"], "platform": config["settings"]["platform"]},
                "memory": memory,
                "graph": {"digest": view["digest"], "source": view["source"], "totalNodes": len(graph["nodes"])},
                "ancestors": [summary(nid) for nid in ancestors],
                "children": [summary(item["id"]) for item in graph["nodes"] if item["parentId"] == (node or None)],
                "relations": [{**edge, "port": edge_port(edge)} for edge in graph["edges"] if edge["source"] in lineage_set or edge["target"] in lineage_set],
                "texts": [],
                "specs": [],
                "drawings": [],
                "documents": [],
                "journal": [],
                "excluded": list(EXCLUDED_PATHS),
            },
            "sourceManifest": manifest,
            "warnings": warnings,
            "policy": {"autostart": False, "requiresConfirmation": True, "provider": None, "proposalOnly": True},
            "report": {
                "evidenceRequired": ["test", "commit", "review", "merge"],
                "note": "Věta agenta není důkaz. Neznámá hodnota je null, nikdy 0. "
                        "Pracuj jen na currentStep; ostatní bloky (bigPicture) jsou kontext, ne úkol.",
            },
        }
        packet = redact_deep(packet)
        if _byte_len(packet) > MAX_PACKET_BYTES:
            raise ValueError(
                f"Povinné podklady uzlu překročily limit {MAX_PACKET_BYTES} bajtů; zkraťte zadání, text nebo paměť projektu."
            )

        def offer(section, item, entry):
            packet["context"][section].append(item)
            if _byte_len(packet) > MAX_PACKET_BYTES:
                packet["context"][section].pop()
                entry.update(included=False, reason="limit_exceeded")
                packet["warnings"].append(
                    f"Zdroj {entry['kind']} {entry['ownerId'] or '(kořen)'} překročil limit {MAX_PACKET_BYTES} bajtů a není zahrnut."
                )
            packet["sourceManifest"].append(entry)

        for layer in drawing_layers(by_id, node):
            drawing = redact_deep(project_drawing(layer, self.canvas.drawing(project, workspace, layer)))
            if not drawing["available"]:
                packet["sourceManifest"].append(_manifest("drawing", layer, None, False, "unavailable"))
                continue
            if drawing["revision"] == 0:
                packet["sourceManifest"].append(_manifest("drawing", layer, 0, False, "no_saved_drawing"))
                continue
            offer("drawings", drawing, _manifest("drawing", layer, drawing["revision"], True, "saved_drawing"))
        for nid in ancestors:
            a_text = self.canvas.texts.read((project, workspace, nid))
            entry = _manifest("text", nid, a_text["revision"], a_text["revision"] > 0, "saved_text" if a_text["revision"] else "no_saved_text")
            if a_text["revision"]:
                offer("texts", redact_deep({"nodeId": nid, "revision": a_text["revision"], "text": a_text["text"]}), entry)
            else:
                packet["sourceManifest"].append(entry)
            a_spec = self.canvas.specs.read((project, workspace, nid))
            entry = _manifest("spec", nid, a_spec["revision"], a_spec["revision"] > 0, "saved_spec" if a_spec["revision"] else "no_saved_spec")
            if a_spec["revision"]:
                offer("specs", redact_deep({"nodeId": nid, "revision": a_spec["revision"], "fields": a_spec["fields"]}), entry)
            else:
                packet["sourceManifest"].append(entry)
        for doc_path in dict.fromkeys([*rule_paths, *lineage_paths, ""]):
            document, reason = self._document(project, workspace, doc_path)
            if document is None:
                packet["sourceManifest"].append(_manifest("document", doc_path, None, False, reason))
                continue
            offer("documents", redact_deep(document), _manifest("document", doc_path, document["revision"], True, reason))
        for day in self.journal.days(project, workspace, node)[:MAX_JOURNAL_DAYS]:
            entry_data = self.journal.read((project, workspace, node, day["day"]))
            offer(
                "journal",
                redact_deep({"nodeId": node, "day": day["day"], "revision": entry_data["revision"], "text": entry_data["text"]}),
                _manifest("journal", f"{node}:{day['day']}", entry_data["revision"], True, "saved_journal"),
            )
        return packet

    def build(self, payload):
        validate_request(payload)
        with self.canvas.reading(payload["project"]):
            packet = self._assemble(payload)
        return {"digest": packet_digest(packet), "packet": packet}

    # ---- snapshoty -----------------------------------------------------------------

    def snapshot(self, payload):
        if not isinstance(payload, dict) or set(payload) != REQUEST_KEYS | {"digest"}:
            raise ValueError("Snapshot vyžaduje stejný rozsah jako náhled a jeho digest.")
        request = {key: payload[key] for key in REQUEST_KEYS}
        validate_request(request)
        expected = payload["digest"]
        if not isinstance(expected, str):
            raise ValueError("Digest náhledu musí být text.")  # noqa: TRY004 - klientská validační chyba mapovaná na HTTP 409
        with self.canvas.graph_lock_for(request["project"]), self.canvas.lock_for(request["project"]):
            packet = self._assemble(request)
            digest = packet_digest(packet)
            if digest != expected:
                raise ValueError("Podklady se od náhledu změnily; obnovte náhled a snapshot vytvořte znovu.")
            snapshot_id = uuid.uuid4().hex
            created_at = now()
            db = self.canvas.db_for(request["project"])
            with db:
                db.execute(
                    "INSERT INTO desktop_v3_snapshots VALUES(?,?,?,?,?,?,?,?)",
                    (snapshot_id, request["project"], request["workspace"], request["nodeId"], digest,
                     encode(request), encode(packet), created_at),
                )
        return {"id": snapshot_id, "digest": digest, "packet": packet, "createdAt": created_at}

    def load(self, snapshot_id, project, workspace):
        if not valid_id(snapshot_id):
            raise ValueError("Neplatné ID snapshotu podkladů.")
        with self.canvas.reading(project):
            row = self.canvas.db_for(project).execute(
                "SELECT * FROM desktop_v3_snapshots WHERE id=?", (snapshot_id,)
            ).fetchone()
        if row is None or row["project_id"] != project or row["workspace_id"] != workspace:
            raise ValueError("Snapshot podkladů v tomto rozsahu neexistuje.")
        return {
            "id": row["id"], "digest": row["digest"], "packet": json.loads(row["packet"]),
            "request": json.loads(row["request"]), "createdAt": row["created_at"],
        }

    def current_digest(self, snapshot):
        """Digest podkladů sestavených teď ze stejného rozsahu; liší se = zdroje se změnily."""
        with self.canvas.reading(snapshot["request"]["project"]):
            return packet_digest(self._assemble(snapshot["request"]))
