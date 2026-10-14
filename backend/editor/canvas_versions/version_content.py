"""Workspace-owned revision stores captured by an existing canvas version."""
import json

from backend.canvas.graph import digest

# name: table, identity columns, data columns (JSON columns are decoded below).
STORES = {
    "specs": ("node_spec_revisions", ("node_id",), ("fields",)),
    "texts": ("node_text_revisions", ("node_id",), ("text",)),
    "journals": ("node_journal_revisions", ("node_id", "day"), ("text",)),
    "drawings": ("drawing_revisions", ("layer_id",), ("scene",)),
    "agentWorkspaces": ("agent_workspace_revisions", ("node_id",), ("sections", "by")),
    "documents": ("workspace_documents", ("path",), ("fields", "node_id", "source_version")),
    "briefFragments": ("brief_fragment_revisions", ("fragment_id",), ("parent_id", "scope_node_id", "ord", "kind", "title",
                                                                     "text", "stage", "mvp", "note", "by", "actor", "deleted",
                                                                     "track")),
    "briefDetails": ("brief_fragment_details", ("fragment_id",), ("fields",)),
    # Zamrazená kola karet (card_rounds.py); stav nese `nodes[].round`, záznamy kol tato část.
    "cardRounds": ("card_rounds", ("node_id", "round"), ("record",)),
}
# Části přidané až po verzích, které je neznají: starší snímek je čte jako prázdné a jejich
# prázdný seznam nemění digest obsahu (stará verze projde kontrolou integrity a není „změněná“).
LATER_STORES = ("briefFragments", "briefDetails", "cardRounds")
JSON_COLUMNS = {"fields", "scene", "sections", "record"}
# Sloupce přidané do části až po verzích, které je neznají (hodnota „nic“). Starší snímek je při obnově
# dostane s touto hodnotou a digest obsahu je s touto hodnotou vynechá, takže stará verze zůstane platná.
LATER_COLUMNS = {"briefFragments": {"track": None}}
SCHEMA = "opora.canvas-version/2"
EXCLUDED = ["source-code", "git-history", "project-settings", "external-references", "immutable-agent-evidence"]


def read_records(db, project, workspace):
    result = {}
    for name, (table, keys, columns) in STORES.items():
        p, w = ("project", "workspace") if name == "documents" else ("project_id", "workspace_id")
        rows = db.execute(f"SELECT * FROM {table} WHERE {p}=? AND {w}=? ORDER BY {','.join(keys)},revision DESC", (project, workspace))
        seen, items = set(), []
        for row in rows:
            key = tuple(row[column] for column in keys)
            if key in seen:
                continue
            seen.add(key)
            data = {column: json.loads(row[column]) if column in JSON_COLUMNS else row[column] for column in columns}
            items.append({"key": list(key), "revision": row["revision"], "data": data})
        result[name] = items
    return result


def empty_data(name):
    from backend.editor.agent_memory.agent_workspace import SECTIONS
    from backend.editor.brief_vault.brief_vault_model import TOMBSTONE
    from backend.editor.node.node_specs import EMPTY_FIELDS
    from backend.project.workspace.workspace_documents import FIELDS
    return {
        "specs": {"fields": dict(EMPTY_FIELDS)}, "texts": {"text": ""}, "journals": {"text": ""},
        "drawings": {"scene": {"elements": []}},
        "agentWorkspaces": {"sections": dict.fromkeys(SECTIONS, ""), "by": "human"},
        "documents": {"fields": dict.fromkeys(sorted(FIELDS), ""), "node_id": None, "source_version": None},
        "briefFragments": dict(TOMBSTONE),
        "briefDetails": {"fields": {}},
        "cardRounds": {"record": {}},
    }[name]


def with_later_stores(records):
    """Snímek uložený před přidáním části ji dostane jako prázdnou (obnova pak skryje novější fragmenty)
    a řádky bez později přidaného sloupce ho dostanou s výchozí hodnotou (`LATER_COLUMNS`)."""
    records = {**{name: [] for name in LATER_STORES}, **records}
    return {name: [{**row, "data": {**LATER_COLUMNS[name], **row["data"]}} for row in rows] if name in LATER_COLUMNS else rows
            for name, rows in records.items()}


def _digest_data(name, data):
    """Data řádku pro digest bez později přidaných sloupců s výchozí hodnotou (stejný digest jako dřív)."""
    later = LATER_COLUMNS.get(name, {})
    return {key: value for key, value in data.items() if key not in later or value != later[key]}


def content_digest(graph, state, snapshot):
    records = {name: [{"key": row["key"], "data": _digest_data(name, row["data"])} for row in rows
                      if _digest_data(name, row["data"]) != _digest_data(name, empty_data(name))]
               for name, rows in snapshot["records"].items()}
    records = {name: rows for name, rows in records.items() if rows or name not in LATER_STORES}
    return digest({"graph": graph, "state": state, "records": records, "assets": snapshot["assets"]})


def current_token(graph, stored, snapshot):
    revisions = {name: [[row["key"], row["revision"]] for row in rows] for name, rows in snapshot["records"].items()
                 if rows or name not in LATER_STORES}
    return digest({"content": content_digest(graph, stored["state"], snapshot), "stateRevision": stored["revision"], "revisions": revisions,
                   "projectGoalContext": snapshot["projectGoal"]})


def restore_records(db, project, workspace, target, current, timestamp):
    """Append new revisions, including empty values for content created after the version."""
    for name, (table, keys, columns) in STORES.items():
        old = {tuple(row["key"]): row for row in current[name]}
        desired = {tuple(row["key"]): row for row in target[name]}
        for key in sorted(old.keys() | desired.keys()):
            data = desired[key]["data"] if key in desired else empty_data(name)
            if key in old and old[key]["data"] == data:
                continue
            revision = old.get(key, {}).get("revision", 0) + 1
            values = [json.dumps(data[column], ensure_ascii=False) if column in JSON_COLUMNS else data[column] for column in columns]
            p, w = ("project", "workspace") if name == "documents" else ("project_id", "workspace_id")
            names = (p, w, *keys, "revision", *columns, "saved_at")
            operation = "INSERT OR REPLACE" if name == "documents" else "INSERT"
            db.execute(f"{operation} INTO {table}({','.join(names)}) VALUES({','.join('?' for _ in names)})",
                       (project, workspace, *key, revision, *values, timestamp))


def validate_records(records, project, workspace):
    from backend.canvas.graph import valid_id
    from backend.editor.agent_memory.agent_workspace import validate_save
    from backend.editor.agent_memory.card_rounds import validate_record as validate_round_record
    from backend.editor.brief_vault.brief_vault_details import validate_details
    from backend.editor.brief_vault.brief_vault_model import validate_record
    from backend.editor.node.drawings import validate_scene
    from backend.editor.node.node_journal import valid_day
    from backend.editor.node.node_specs import validate_payload
    from backend.project.workspace.workspace_documents import FIELDS
    from backend.project.workspace.workspace_sources import relative_path
    if not isinstance(records, dict) or set(records) != set(STORES):
        raise ValueError("Verze neobsahuje všechny deklarované části pracovního prostoru.")
    for name, rows in records.items():
        seen = set()
        for row in rows:
            key, data = row["key"], row["data"]
            if len(key) != len(STORES[name][1]) or tuple(key) in seen or set(data) != set(STORES[name][2]):
                raise ValueError("Neplatný obsah uložené verze.")
            seen.add(tuple(key))
            if name != "documents" and not (name == "drawings" and key[0] == "") and not valid_id(key[0]):
                raise ValueError("Neplatný uzel uložené verze.")
            if name == "specs":
                validate_payload({"project": project, "workspace": workspace, "node": key[0], "expected_revision": 0, "fields": data["fields"]})
            elif name in ("texts", "journals"):
                if not isinstance(data["text"], str) or len(data["text"]) > 64000 or "\0" in data["text"] or (name == "journals" and not valid_day(key[1])):
                    raise ValueError("Neplatný text nebo deník uložené verze.")
            elif name == "drawings":
                validate_scene(data["scene"])
            elif name == "agentWorkspaces":
                validate_save({"project": project, "workspace": workspace, "nodeId": key[0], "expectedRevision": 0, "sections": data["sections"], "by": data["by"]})
            elif name == "briefFragments":
                validate_record(data)
            elif name == "briefDetails":
                validate_details(data["fields"])
            elif name == "cardRounds":
                if type(key[1]) is not int or key[1] < 1:
                    raise ValueError("Neplatné kolo karty v uložené verzi.")
                validate_round_record(data["record"], key[0], key[1])
            elif name == "documents":
                relative_path(key[0])
                if set(data["fields"]) != FIELDS or any(not isinstance(value, str) or len(value) > 16000 for value in data["fields"].values()):
                    raise ValueError("Neplatná dokumentace uložené verze.")
                if data["node_id"] is not None and not valid_id(data["node_id"]):
                    raise ValueError("Neplatná vazba dokumentace.")
                if key[0] == "" and data["fields"]["goal"]:
                    raise ValueError("Verze nesmí obnovit globální cíl projektu přes dokumentaci.")
