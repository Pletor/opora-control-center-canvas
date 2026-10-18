"""Schránka zadání: doslovné a verzované fragmenty zadání (docs/navrh-schranka-zadani.md).

Fragment má stálé `fragment_id` a řadu revizí v `brief_fragment_revisions` (append-only jako
`node_text_revisions`, CAS přes `expectedRevision`). Text se nikdy nepřepisuje: každá změna je
nová revize s poznámkou. Kořen schránky je připnutý k plátnu (`scopeNodeId: ""`), sektoru nebo
kartě; dítě má jen rodiče (fraktál do libovolné hloubky). `split` hlídá, že se zadání neztratí.
`mvp: yes|no`, smazání a obnova staré revize patří člověku (`HUMAN_OPS`, 403 / 428).
Disciplína (`discipline`: id z docs/schranka-neurony.md §2 | null = dědí) jde s fragmentem do každé další
revize; kořen ji nese vždy a přeřadí ji jen `set-discipline` (nová revize se stejným textem).
"""

import uuid
from datetime import UTC, datetime

from backend.canvas.activity_log import require_human
from backend.canvas.graph import valid_id
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.brief_vault import brief_vault_develop as develop
from backend.editor.brief_vault import brief_vault_gates as gates
from backend.editor.brief_vault import brief_vault_mirror as vault_mirror
from backend.editor.brief_vault import brief_vault_placement as placement
from backend.editor.brief_vault.brief_vault_details import latest_details
from backend.editor.brief_vault.brief_vault_model import (
    COLUMNS,
    MAX_BY,
    MAX_DEPTH,
    MAX_NOTE,
    MAX_TEXT,
    MAX_TITLE,
    STAGES,
    bad_request,
    data_of,
    discipline_of,
    fail,
    history_rows,
    latest_rows,
    public,
    text_of,
    validate_record,
)
from backend.editor.brief_vault.brief_vault_plan import dry_plan
from backend.editor.brief_vault.brief_vault_read import VaultReader
from backend.editor.brief_vault.brief_vault_split import split_parts
from backend.integrations import mirror_client

SCOPE_KEYS = {"project", "workspace", "op"}
# Pole každé operace: (povinná, volitelná).
OPS = {
    "create": ({"title", "text"}, {"scopeNodeId", "parentId", "stage", "note", "discipline"}),
    "revise": ({"fragmentId", "expectedRevision", "note"}, {"text", "title", "stage"}),
    "split": ({"fragmentId", "expectedRevision"}, {"parts", "splitter", "note"}),
    "research": ({"fragmentId", "title", "text"}, {"note", "question", "status"}),
    "promote": ({"fragmentId", "expectedRevision", "note"}, {"text"}),
    "propose-mvp": ({"fragmentIds"}, {"note"}),
    "set-mvp": ({"fragmentIds", "mvp"}, {"note"}),
    "delete": ({"fragmentId", "expectedRevision", "note"}, set()),
    "restore": ({"fragmentId", "expectedRevision", "revision", "note"}, set()),
    "set-discipline": ({"fragmentId", "expectedRevision", "discipline", "note"}, set()),
    **develop.OPS,
    **gates.OPS,
}
HUMAN_OPS = {"set-mvp": "MVP potvrzuje nebo zamítá jen člověk; agent ho navrhuje přes propose-mvp.",
             "delete": "Fragment zadání maže jen člověk.",
             "restore": "Starou revizi fragmentu obnovuje jen člověk.",
             **develop.HUMAN_OPS, **gates.HUMAN_OPS}
MAX_IDS = 500


def _now():
    return datetime.now(UTC).isoformat()


def _payload(payload):
    if not isinstance(payload, dict) or payload.get("op") not in OPS:
        fail("op musí být jedna z " + ", ".join(OPS) + ".")
    required, optional = OPS[payload["op"]]
    keys = set(payload) - SCOPE_KEYS
    if not SCOPE_KEYS <= set(payload) or required - keys or keys - required - optional:
        fail(f"op {payload['op']} očekává {', '.join(sorted(required))}"
             + (f" a volitelně {', '.join(sorted(optional))}" if optional else "") + ".")
    for key in ("expectedRevision", "revision"):
        if key in payload and (type(payload[key]) is not int or payload[key] < 0):
            fail(f"{key} musí být nezáporné celé číslo.")
    if "note" in payload:
        text_of(payload["note"], MAX_NOTE, "note", allow_empty=payload["op"] in ("create", "split", "research",
                                                                                 "propose-mvp", "set-mvp", "question",
                                                                                 "answer", "link-decisions", "from-idea"))
    return payload["op"]


class _Write:
    """Jeden zápis v transakci: kdo, kdy a nová revize fragmentu."""

    def __init__(self, db, project, workspace, actor, agent, state_store=None):
        self.db, self.project, self.workspace, self.actor = db, project, workspace, actor
        self.by = (agent or "agent") if actor == "agent" else actor
        self.at = _now()
        self.state_store = state_store

    def state(self):
        """Stav plátna v téže transakci (rozhodnutí, Podněty)."""
        return self.state_store.current(self.project, self.workspace)

    def details(self, fragment_id):
        found = latest_details(self.db, self.project, self.workspace, [fragment_id]).get(fragment_id)
        return dict(found["fields"]) if found else {}

    def check_depth(self, parent_id):
        """Nové dítě rodiče `parent_id` nesmí překročit strop hloubky (bez rekurze, 409)."""
        depth, cursor, seen = 0, parent_id, set()
        while cursor is not None and depth <= MAX_DEPTH:
            if cursor in seen:
                break
            seen.add(cursor)
            row = self.db.execute("SELECT parent_id FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=?"
                                  " AND fragment_id=? ORDER BY revision DESC LIMIT 1",
                                  (self.project, self.workspace, cursor)).fetchone()
            if row is None:
                break
            depth += 1
            cursor = row["parent_id"]
        if depth + 1 > MAX_DEPTH or cursor in seen:
            fail(f"strom schránky má strop hloubky {MAX_DEPTH}; vložte fragment výš nebo rozdělte jinou větev.")

    def latest(self, fragment_id, *, live=True):
        if not isinstance(fragment_id, str) or not valid_id(fragment_id):
            fail("fragmentId má neplatný identifikátor.")
        row = latest_rows(self.db, self.project, self.workspace, [fragment_id]).get(fragment_id)
        if row is None:
            fail(f"fragment {fragment_id} v tomto pracovním prostoru neexistuje.")
        if live and row["deleted"]:
            fail(f"fragment {fragment_id} je smazaný; obnoví ho člověk (op restore).")
        return row

    def checked(self, payload):
        row = self.latest(payload["fragmentId"])
        if row["revision"] != payload["expectedRevision"]:
            fail(f"fragment se změnil (revize {row['revision']}, očekávána {payload['expectedRevision']}); načtěte ho znovu.")
        return row

    def children(self, parent_id):
        rows = [row for row in latest_rows(self.db, self.project, self.workspace).values()
                if row["parent_id"] == parent_id and not row["deleted"]]
        return sorted(rows, key=lambda row: row["ord"])

    def insert(self, fragment_id, revision, data, note):
        data = validate_record({**data, "note": note[:MAX_NOTE], "by": self.by[:MAX_BY], "actor": self.actor})
        self.db.execute(f"INSERT INTO brief_fragment_revisions(project_id,workspace_id,fragment_id,revision,{','.join(COLUMNS)},saved_at)"
                        f" VALUES({','.join('?' for _ in range(len(COLUMNS) + 5))})",
                        (self.project, self.workspace, fragment_id, revision, *(data[key] for key in COLUMNS), self.at))
        return self.latest(fragment_id, live=False)

    def revise(self, row, note, **changes):
        return self.insert(row["fragment_id"], row["revision"] + 1, {**data_of(row), **changes}, note)

    def new(self, *, parent, scope, title, text, kind="brief", stage="draft", note="", discipline=None):
        """Nový fragment; `discipline` None = dědí od rodiče (kořen ji dostane vždy, hlídá volající)."""
        siblings = self.children(parent) if parent is not None else []
        data = {"parent_id": parent, "scope_node_id": scope, "ord": max((row["ord"] for row in siblings), default=0) + 1,
                "kind": kind, "title": title, "text": text, "stage": stage, "mvp": "none", "deleted": 0, "discipline": discipline,
                "gates": None}
        return self.insert(uuid.uuid4().hex, 1, data, note)


def _stage(value):
    if value not in STAGES:
        fail("stage musí být draft, research nebo ready.")
    return value


def _ids(value):
    if not isinstance(value, list) or not value or len(value) > MAX_IDS or len(set(map(str, value))) != len(value):
        fail(f"fragmentIds musí být neprázdné pole nejvýše {MAX_IDS} různých id.")
    return value


def _create(w, payload, node_ids):
    title = text_of(payload["title"], MAX_TITLE, "title", allow_empty=False)
    text = text_of(payload["text"], MAX_TEXT, "text")
    if ("scopeNodeId" in payload) == ("parentId" in payload):
        fail("create očekává buď scopeNodeId (kořen schránky), nebo parentId (dítě).")
    scope, parent = payload.get("scopeNodeId"), None
    if "parentId" in payload:
        parent = w.latest(payload["parentId"])["fragment_id"]
        w.check_depth(parent)
    elif scope != "" and scope not in node_ids:
        fail("scopeNodeId musí být \"\" (plátno) nebo id existující karty či sektoru.")
    discipline = discipline_of(payload.get("discipline"), allow_null=parent is not None)
    row = w.new(parent=parent, scope=scope, title=title, text=text, stage=_stage(payload.get("stage", "draft")),
                note=payload.get("note") or "Vloženo do schránky.", discipline=discipline)
    return {"fragment": public(row)}


def _revise(w, payload, node_ids):
    row = w.checked(payload)
    changes = {}
    if "text" in payload:
        changes["text"] = text_of(payload["text"], MAX_TEXT, "text")
    if "title" in payload:
        changes["title"] = text_of(payload["title"], MAX_TITLE, "title", allow_empty=False)
    if "stage" in payload:
        changes["stage"] = _stage(payload["stage"])
    if all(row[key] == value for key, value in changes.items()):
        fail("revize nic nemění; pošlete změněný text, title nebo stage.")
    return {"fragment": public(w.revise(row, payload["note"], **changes))}


def _split(w, payload, node_ids):
    row = w.checked(payload)
    if w.children(row["fragment_id"]):
        fail("fragment už má podfragmenty; rozdělte některý z nich, nebo je nejdřív smaže člověk.")
    parts = split_parts(payload, row["text"])
    w.check_depth(row["fragment_id"])
    note = (f"Rozděleno z {row['fragment_id']} r{row['revision']}. " + payload.get("note", "")).strip()
    children = [w.new(parent=row["fragment_id"], scope=None, title=part["title"], text=part["text"],
                      kind=row["kind"], note=note) for part in parts]
    return {"fragment": public(row), "children": [public(child) for child in children]}


def _promoted_text(w, payload, research):
    """Nový text rodiče: `text` z požadavku, jinak závěr výzkumu (`approach`). Otázka ani poznámka výzkumu
    zadání nepřepíše (kritik B3); bez obojího 409 a rodič zůstane beze změny."""
    if "text" in payload:
        return text_of(payload["text"], MAX_TEXT, "text", allow_empty=False)
    approach = (w.details(research["fragment_id"]).get("research") or {}).get("approach", "")
    if not approach.strip():
        fail("promote bez text potřebuje závěr výzkumu (approach z research-update); jinak pošlete celý nový text rodiče.")
    return text_of(approach, MAX_TEXT, "approach")


def _promote(w, payload, node_ids):
    research = w.latest(payload["fragmentId"])
    if research["kind"] != "research" or research["parent_id"] is None:
        fail("promote povyšuje jen research fragment do jeho rodiče.")
    parent = w.latest(research["parent_id"])
    if parent["revision"] != payload["expectedRevision"]:
        fail(f"rodič se změnil (revize {parent['revision']}, očekávána {payload['expectedRevision']}); načtěte ho znovu.")
    text = _promoted_text(w, payload, research)
    note = f"Povýšen research {research['fragment_id']} r{research['revision']}: {payload['note']}"
    promoted = w.revise(parent, note, text=text)
    done = w.revise(research, f"Povýšeno do {parent['fragment_id']} r{promoted['revision']}.", stage="ready")
    return {"fragment": public(promoted), "research": public(done)}


def _mvp(w, payload, value, note):
    changed, skipped = [], []
    for fragment_id in _ids(payload["fragmentIds"]):
        row = w.latest(fragment_id)
        if row["mvp"] == value or (value == "proposed" and row["mvp"] in ("yes", "no")):
            skipped.append(fragment_id)
            continue
        changed.append(public(w.revise(row, payload.get("note") or note, mvp=value)))
    return {"changed": changed, "skipped": skipped}


def _propose(w, payload, node_ids):
    return _mvp(w, payload, "proposed", "Návrh do MVP.")


def _set_mvp(w, payload, node_ids):
    if payload["mvp"] not in ("none", "yes", "no"):
        fail("set-mvp nastavuje yes, no nebo none.")
    return _mvp(w, payload, payload["mvp"], f"MVP: {payload['mvp']}.")


def _delete(w, payload, node_ids):
    return {"fragment": public(w.revise(w.checked(payload), payload["note"], deleted=1))}


def _restore(w, payload, node_ids):
    row = w.latest(payload["fragmentId"], live=False)
    if row["revision"] != payload["expectedRevision"]:
        fail("fragment se změnil; načtěte ho znovu.")
    old = next((item for item in history_rows(w.db, w.project, w.workspace, row["fragment_id"])
                if item["revision"] == payload["revision"]), None)
    if old is None or old["deleted"]:
        fail("obnovit lze jen existující nesmazanou revizi fragmentu.")
    note = f"Obnovena revize r{old['revision']}: {payload['note']}"
    # Disciplína je zařazení a brány jsou stav cyklu, ne obsah: obnova vrátí text a metadata, disciplínu a brány nechá
    # aktuální (brány s jiným otiskem vstupů se pak hlásí jako zneplatněné, §9 bod 4).
    data = {**data_of(old), "discipline": row["discipline"], "gates": row["gates"]}
    return {"fragment": public(w.insert(row["fragment_id"], row["revision"] + 1, data, note))}


def _set_discipline(w, payload, node_ids):
    """Přeřazení fragmentu (a s ním podstromu, který disciplínu dědí) do jiné disciplíny; text beze změny."""
    row = w.checked(payload)
    discipline = discipline_of(payload["discipline"], allow_null=row["parent_id"] is not None)
    if row["discipline"] == discipline:
        fail("set-discipline nic nemění; fragment už má tuto disciplínu.")
    return {"fragment": public(w.revise(row, payload["note"], discipline=discipline))}


HANDLERS = {"create": _create, "revise": _revise, "split": _split, "research": develop.research, "promote": _promote,
            "propose-mvp": _propose, "set-mvp": _set_mvp, "delete": _delete, "restore": _restore, "set-discipline": _set_discipline,
            **develop.HANDLERS, **gates.HANDLERS}


class BriefVault(VaultReader):
    """Zápis jedné operace schránky; čtení (strom, fragment, balíček pro LLM, historie) dědí z `VaultReader`."""

    def __init__(self, canvas, state_store=None, mirror=None):
        super().__init__(canvas, state_store or getattr(canvas, "desktop_v3_state", None) or DesktopV3State(canvas))
        # Zrcadlo (docs/zrcadlo.md): `mirror(project)` vrací klienta, nebo None; výchozí čte prostředí při každém volání.
        self.mirror = mirror or (lambda project: mirror_client.client_for(project))

    def apply(self, payload, *, actor="unknown", agent=""):
        """Jedna operace schránky v jedné transakci; ValueError = nic se nezapsalo (HTTP 409).

        Po potvrzení transakce (mimo zámek) volá Zrcadlo; jeho výsledek ani porucha odpověď nemění."""
        result = self._apply(payload, actor=actor, agent=agent)
        vault_mirror.after_gate(self.canvas, payload, result, self.mirror)
        return result

    def mirror_overview(self, project, workspace):
        """Přesnost Zrcadla po disciplínách a poslední hormony pro Přehled Schránky (docs/zrcadlo.md)."""
        return vault_mirror.overview(self.canvas, project, workspace, self.mirror(project))

    def _apply(self, payload, *, actor, agent):
        op = _payload(payload)
        if op in HUMAN_OPS:
            require_human(actor, HUMAN_OPS[op])
        project, workspace = payload["project"], payload["workspace"]
        with self.canvas.graph_lock_for(project):
            view = self.canvas.view(project, workspace)
            if view["readOnly"]:
                fail("main je pouze pro čtení; schránka se mění v pracovním prostoru.")
            node_ids = {node["id"] for node in view["graph"]["nodes"]}

            def make_write(db):
                return _Write(db, project, workspace, actor, agent, self.state)

            if placement.wants(payload):
                # Brány plánu: plán a zápis na plátno skládá server mimo transakci schránky (§9 body 1–2).
                return placement.run(self, payload, view, node_ids, make_write, actor)
            db = self.canvas.db_for(project)
            with self.canvas.lock_for(project), db:
                db.execute("BEGIN IMMEDIATE")
                return {"ok": True, "op": op, **HANDLERS[op](make_write(db), payload, node_ids)}

    def plan(self, payload, *, actor="unknown"):
        """`POST /api/brief-vault/plan {project, workspace, fragmentIds}`: jen čtení, dávka ověřená dryRun."""
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "fragmentIds"}:
            bad_request("plan očekává project, workspace a fragmentIds.")
        found = dry_plan(self.canvas, self.state, payload["project"], payload["workspace"], payload["fragmentIds"], actor)
        return {"plan": found["plan"], "summary": found["summary"], "hash": found["hash"], "skipped": found["skipped"],
                "digest": found["digest"], "scopes": found["scopes"], "generator": found["generator"],
                "sourceRevisions": found["sourceRevisions"]}
