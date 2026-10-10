"""Pracovní prostor agenta u jedné karty (`agent-workspace`): mezipaměť modelu, ne zadání.

Kontrakt je `docs/karta-pro-agenty.md`, sekce „Pracovní prostor agenta“; tento modul ho jen
provádí. Pět pojmenovaných sekcí — rámec a směr (`frame`), pracovní postup (`log`), co se
nepovedlo (`failures`), úspěšné opravy (`fixes`) a předávka (`handoff`) — je volný text do
12 000 znaků. Uloženo per `project + workspace + nodeId` a revizované jako text uzlu:
každý zápis přidá novou revizi, prázdný prostor má revizi 0, prázdné řetězce a `by: "human"`.

Zápis je částečný: uvedené sekce se přepíšou, neuvedené si drží svou hodnotu. Karta je
stejná na každé úrovni (uzel, sektor i oblast), takže prostor má každá karta v grafu.
Uzavřená karta (`done.confirmed`) zápis odmítne a main je pouze pro čtení, stejně jako
u textu uzlu. Nic v prostoru není příkaz modelu: člověk do něj smí psát, ale patří modelu.
"""

import json

from backend.canvas.canvas_service import now
from backend.canvas.graph import valid_id
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_done

SECTIONS = ("frame", "log", "failures", "fixes", "handoff")
# Předávka mezi kartami se čte zkráceně: rámec (kam se jde) a předávka (kde pokračovat).
HANDOFF_SECTIONS = ("frame", "handoff")
ACTORS = ("human", "agent")
MAX_SECTION = 12000
SAVE_KEYS = {"project", "workspace", "nodeId", "expectedRevision", "sections", "by"}


def empty_workspace():
    return {**dict.fromkeys(SECTIONS, ""), "updatedAt": "", "by": "human"}


def handoff_of(workspace):
    """Zkrácený prostor pro potomka, rodiče a souseda v oblasti: jen rámec a předávka."""
    return {key: workspace[key] for key in HANDOFF_SECTIONS}


def _fail(message):
    raise ValueError("Neplatný pracovní prostor agenta: " + message)


def _scope_ids(project, workspace):
    if not isinstance(project, str) or (project != "draft" and not valid_id(project)) or not valid_id(workspace):
        _fail("neplatný identifikátor projektu nebo pracovního prostoru.")


def _scope(project, workspace, node_id):
    _scope_ids(project, workspace)
    if not valid_id(node_id):
        _fail("neplatný identifikátor uzlu.")


def validate_save(payload):
    """Tvar celého požadavku; identita karty se proti grafu a stavu ověřuje až v `save`."""
    if not isinstance(payload, dict) or set(payload) != SAVE_KEYS:
        _fail("očekávám project, workspace, nodeId, expectedRevision, sections a by.")
    _scope(payload["project"], payload["workspace"], payload["nodeId"])
    if type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 0:
        _fail("expectedRevision musí být revize prostoru, kterou pisatel četl.")
    sections = payload["sections"]
    if not isinstance(sections, dict) or set(sections) - set(SECTIONS):
        _fail("sections smí obsahovat jen frame, log, failures, fixes a handoff.")
    for key, value in sections.items():
        if not isinstance(value, str) or "\0" in value or len(value) > MAX_SECTION:
            _fail(f"sekce {key} musí být text do {MAX_SECTION} znaků.")
    if payload["by"] not in ACTORS:
        _fail("by musí být human nebo agent.")
    return payload


class AgentWorkspace:
    def __init__(self, canvas, state_store=None):
        self.canvas = canvas
        self.state = state_store or DesktopV3State(canvas)

    # ---- čtení ---------------------------------------------------------------------

    def current(self, project, workspace, node_id):
        """Poslední revize prostoru bez ověření rozsahu; volající drží zámky a rozsah ověřil."""
        row = self.canvas.db_for(project).execute(
            "SELECT revision,sections,by,saved_at FROM agent_workspace_revisions"
            " WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY revision DESC LIMIT 1",
            (project, workspace, node_id),
        ).fetchone()
        if row is None:
            return {"revision": 0, "workspace": empty_workspace()}
        return {"revision": row["revision"], "workspace": self._shape(row)}

    def _shape(self, row):
        stored = json.loads(row["sections"])
        return {
            **{key: stored.get(key, "") for key in SECTIONS},
            "updatedAt": row["saved_at"],
            "by": row["by"],
        }

    def read(self, project, workspace, node_id):
        """Prostor jedné karty; None = karta v tomto rozsahu neexistuje (i na read-only mainu)."""
        _scope(project, workspace, node_id)
        with self.canvas.reading(project):
            view = self.canvas.view(project, workspace)
            if not any(item["id"] == node_id for item in view["graph"]["nodes"]):
                return None
            if view["readOnly"]:
                return {"revision": 0, "workspace": empty_workspace(), "readOnly": True}
            with self.canvas.reading(project):
                return {**self.current(project, workspace, node_id), "readOnly": False}

    def read_many(self, project, workspace, node_ids):
        """Prostory několika karet najednou (podklad pro balíček); chybějící je prázdný."""
        wanted = [item for item in dict.fromkeys(node_ids) if valid_id(item)]
        found = {}
        if wanted:
            rows = self.canvas.db_for(project).execute(
                "SELECT node_id,sections,by,saved_at FROM agent_workspace_revisions AS w"
                " WHERE project_id=? AND workspace_id=? AND revision=(SELECT MAX(revision)"
                " FROM agent_workspace_revisions WHERE project_id=w.project_id"
                " AND workspace_id=w.workspace_id AND node_id=w.node_id)",
                (project, workspace),
            ).fetchall()
            keep = set(wanted)
            found = {row["node_id"]: self._shape(row) for row in rows if row["node_id"] in keep}
        return {item: found.get(item, empty_workspace()) for item in wanted}

    def summaries(self, project, workspace):
        """Vyplněnost prostoru všech karet v rozsahu jedním dotazem; komentáře se nepočítají."""
        _scope_ids(project, workspace)
        with self.canvas.reading(project):
            view = self.canvas.view(project, workspace)
            node_ids = [item["id"] for item in view["graph"]["nodes"] if item.get("kind") != "comment"]
            if view["readOnly"]:
                return {
                    "readOnly": True,
                    "items": {node_id: {"filled": 0, "by": "human", "updatedAt": ""} for node_id in node_ids},
                }
            with self.canvas.reading(project):
                records = self.read_many(project, workspace, node_ids)
        return {
            "readOnly": False,
            "items": {
                node_id: {
                    "filled": sum(1 for key in SECTIONS if record[key].strip()),
                    "by": record["by"],
                    "updatedAt": record["updatedAt"],
                }
                for node_id, record in records.items()
            },
        }

    # ---- zápis ---------------------------------------------------------------------

    def save(self, payload):
        """Přepíše uvedené sekce novou revizí; při chybě nezapíše nic a vrací nový tvar čtení."""
        validate_save(payload)
        project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        expected, sections = payload["expectedRevision"], payload["sections"]
        with self.canvas.graph_lock_for(project):
            view = self.canvas.view(project, workspace)
            if not any(item["id"] == node_id for item in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení; pracovní prostor agenta patří do pracovního prostoru.")
            with self.canvas.lock_for(project):
                stored = self.state.current(project, workspace)
                node = stored["state"]["nodes"].get(node_id, {})
                if node.get("done", default_done())["confirmed"]:
                    raise ValueError("Karta je uzavřená; pracovní prostor agenta se do ní nezapisuje.")
                db = self.canvas.db_for(project)
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    value = self.current(project, workspace, node_id)
                    if value["revision"] != expected:
                        raise ValueError(
                            "Konflikt: pracovní prostor se změnil jinde. Rozepsaný text zůstal zachovaný."
                        )
                    # Částečný zápis: neuvedená sekce si drží hodnotu z poslední revize.
                    merged = {key: sections.get(key, value["workspace"][key]) for key in SECTIONS}
                    db.execute(
                        "INSERT INTO agent_workspace_revisions VALUES(?,?,?,?,?,?,?)",
                        (project, workspace, node_id, expected + 1,
                         json.dumps(merged, ensure_ascii=False), payload["by"], now()),
                    )
                return {**self.current(project, workspace, node_id), "readOnly": False}

    def delete(self, project, workspace, node_id):
        """Smazaná karta si bere svůj prostor s sebou; prostor se nikdy nekopíruje jinam."""
        if not valid_id(node_id):
            return
        with self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute(
                    "DELETE FROM agent_workspace_revisions WHERE project_id=? AND workspace_id=? AND node_id=?",
                    (project, workspace, node_id),
                )
