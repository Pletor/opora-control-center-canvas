"""Knihovna pláten toku napříč projekty (kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §1, §3).

Knihovna je globální (bez `project_id`) a má dvě části: `human` píše člověk, `agent` srdce a dělníci (kdo smí psát,
hlídá router). Složka `flow_library_folders` je jedna úroveň; plátno toku je workflow `kind = library_flow`
s `owner_ref = opora:library:<část>:<slug složky>/<slug>` a verzemi engine (`workflows.py`).
Rodokmen: převzetí do projektu (`adopt`) i uložení vylepšení (`contribute`) založí nové workflow, jehož první verze
nese `derived_from = {workflowId, versionId}` zdroje a rovnou je aktivní. Funkce dostávají spojení na registry.sqlite
a zámek drží volající.
"""

import json
import re
import sqlite3
import uuid

from backend.flow.transactions import transaction

from backend.flow.brief import brief
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import (
    LIBRARY_OWNER,
    FlowConflict,
    FlowNotFound,
    _now,
    activate,
    create_draft,
    create_workflow,
    list_versions,
    set_candidate,
)

KIND = "library_flow"
PARTS = ("human", "agent")
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
# Kategorie dnešního panelu Komponenty (`component-shelf.ts`) a „AI a RAG“; Skills, Tools a Harness zůstávají v Brainu.
DEFAULT_FOLDERS = (
    ("database", "Databáze"), ("backend", "Backend"), ("devops", "DevOps"), ("cache", "Cache"), ("docker", "Docker"),
    ("functions", "Funkce a metody"), ("infrastructure", "Infrastruktura"), ("security", "Security"),
    ("monitoring", "Monitoring"), ("tests", "Testy"), ("auth", "Autentizace"), ("events", "Fronta a události"),
    ("storage", "Úložiště"), ("notifications", "Notifikace"), ("payments", "Platby"), ("ai-rag", "AI a RAG"),
    ("other", "Další"),
)


def owner_ref(part, folder_slug, slug):
    return f"opora:library:{part}:{folder_slug}/{slug}"


def _slug(value):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise FlowInvalid("Slug je malými písmeny, číslice a pomlčky (a-z0-9-), nejvýš 64 znaků.")
    return value


def _folder(row):
    return {"id": row["id"], "owner": row["owner"], "slug": row["slug"], "title": row["title"],
            "description": row["description"], "order": row["ord"]}


def seed_folders(db):
    """Výchozí složky člověka, jen když část člověka ještě žádnou složku nemá (smazaná se nevrací)."""
    if db.execute("SELECT 1 FROM flow_library_folders WHERE owner='human'").fetchone():
        return
    with transaction(db):
        for order, (slug, title) in enumerate(DEFAULT_FOLDERS):
            db.execute("INSERT OR IGNORE INTO flow_library_folders(id,owner,slug,title,ord,created_at) "
                       "VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, "human", slug, title, order, _now()))


def get_folder(db, folder_id):
    row = db.execute("SELECT * FROM flow_library_folders WHERE id=?", (folder_id,)).fetchone()
    if row is None:
        raise FlowNotFound("Složka knihovny neexistuje.")
    return _folder(row)


def create_folder(db, part, slug, title, description="", order=None):
    if part not in PARTS:
        raise FlowInvalid("Část knihovny je human nebo agent.")
    if not title or not title.strip():
        raise FlowInvalid("Složka potřebuje titulek.")
    if order is None:
        order = db.execute("SELECT COALESCE(MAX(ord),-1)+1 FROM flow_library_folders WHERE owner=?",
                           (part,)).fetchone()[0]
    folder = {"id": uuid.uuid4().hex, "owner": part, "slug": _slug(slug), "title": title.strip(),
              "description": description or "", "ord": order, "created_at": _now()}
    try:
        with transaction(db):
            db.execute("INSERT INTO flow_library_folders(id,owner,slug,title,description,ord,created_at) "
                       "VALUES(:id,:owner,:slug,:title,:description,:ord,:created_at)", folder)
    except sqlite3.IntegrityError as error:
        raise FlowConflict(f"Složka {slug} v části {part} už je.", "folder_taken") from error
    return get_folder(db, folder["id"])


def update_folder(db, folder_id, title=None, description=None, order=None):
    """Titulek, popis a pořadí; slug je součást `owner_ref` pláten, proto se nemění."""
    folder = get_folder(db, folder_id)
    if title is not None and not title.strip():
        raise FlowInvalid("Složka potřebuje titulek.")
    with transaction(db):
        db.execute("UPDATE flow_library_folders SET title=?, description=?, ord=? WHERE id=?",
                   ((title or folder["title"]).strip(), folder["description"] if description is None else description,
                    folder["order"] if order is None else order, folder_id))
    return get_folder(db, folder_id)


def _flows(db, part, folder_slug=None):
    prefix = f"opora:library:{part}:" + (f"{folder_slug}/" if folder_slug else "")
    return db.execute(
        "SELECT w.*, v.id AS active_version_id, v.n AS active_n, v.meta AS active_meta FROM flow_workflows w "
        "LEFT JOIN flow_workflow_versions v ON v.workflow_id=w.id AND v.status='active' "
        "WHERE w.kind=? AND w.project_id IS NULL AND substr(w.owner_ref,1,?)=? ORDER BY w.created_at, w.id",
        (KIND, len(prefix), prefix)).fetchall()


def delete_folder(db, folder_id):
    folder = get_folder(db, folder_id)
    if _flows(db, folder["owner"], folder["slug"]):
        raise FlowConflict("Složka má plátna toku; nejdřív je přesuňte.", "folder_not_empty")
    with transaction(db):
        db.execute("DELETE FROM flow_library_folders WHERE id=?", (folder_id,))
    return {"deleted": folder_id}


def _derived(db, workflow_id):
    """Workflow, jejichž verze vychází z některé verze `workflow_id` (kopie v projektech i vylepšení v knihovně)."""
    rows = db.execute(
        "SELECT DISTINCT w.id, w.name, w.project_id, w.owner_ref FROM flow_workflow_versions v "
        "JOIN flow_workflows w ON w.id=v.workflow_id WHERE json_extract(v.derived_from,'$.workflowId')=? "
        "ORDER BY w.created_at, w.id", (workflow_id,)).fetchall()
    return [{"workflowId": r["id"], "name": r["name"], "projectId": r["project_id"], "ownerRef": r["owner_ref"]}
            for r in rows]


def _summary(db, row):
    """Karta plátna: aktivní verze, z čeho vychází (`derivedFrom`), počet odvozených a odkud se agent plátno naučil
    (`learnedFrom` aktivní verze, `{project, card, result}`, knihovna §5)."""
    match = LIBRARY_OWNER.fullmatch(row["owner_ref"] or "")
    source = db.execute("SELECT derived_from FROM flow_workflow_versions WHERE workflow_id=? AND derived_from IS NOT "
                        "NULL ORDER BY n LIMIT 1", (row["id"],)).fetchone()
    meta = json.loads(row["active_meta"]) if row["active_meta"] else {}
    return {"id": row["id"], "slug": match.group(3) if match else None, "title": row["name"],
            "description": row["description"], "ownerRef": row["owner_ref"], "projectId": row["project_id"],
            "activeVersionId": row["active_version_id"], "activeN": row["active_n"],
            "derivedCount": len(_derived(db, row["id"])), "derivedFrom": json.loads(source[0]) if source else None,
            "learnedFrom": meta.get("learnedFrom")}


def list_library(db, part):
    """Složky části knihovny v pořadí a v každé její plátna (titulek, popis, aktivní verze, počet odvozených)."""
    if part not in PARTS:
        raise FlowInvalid("Část knihovny je human nebo agent.")
    folders = [_folder(r) for r in db.execute("SELECT * FROM flow_library_folders WHERE owner=? ORDER BY ord, slug",
                                              (part,))]
    return [{**f, "flows": [_summary(db, r) for r in _flows(db, part, f["slug"])]} for f in folders]


def _workflow(db, workflow_id):
    row = db.execute(
        "SELECT w.*, v.id AS active_version_id, v.n AS active_n, v.meta AS active_meta FROM flow_workflows w "
        "LEFT JOIN flow_workflow_versions v ON v.workflow_id=w.id AND v.status='active' WHERE w.id=?",
        (workflow_id,)).fetchone()
    if row is None or row["kind"] != KIND:
        raise FlowNotFound("Plátno toku neexistuje.")
    return row


def part_of(db, workflow_id):
    """Část knihovny plátna bez projektu (`human` / `agent`); kopie v projektu = None."""
    match = LIBRARY_OWNER.fullmatch(_workflow(db, workflow_id)["owner_ref"] or "")
    return match.group(1) if match else None


def flow_detail(db, workflow_id):
    """Plátno s verzemi a rodokmenem: z čeho vychází, co z něj vychází a které projekty ho používají."""
    row = _workflow(db, workflow_id)
    versions = list_versions(db, workflow_id)
    source = next((v["derived_from"] for v in versions if v["derived_from"]), None)
    derived = _derived(db, workflow_id)
    projects = sorted({d["projectId"] for d in derived if d["projectId"]})
    return {**_summary(db, row), "versions": versions, "derivedFrom": source, "derived": derived,
            "projects": projects}


def flow_brief(db, workflow_id, n=None):
    """Zadání pro agenta (`backend/flow/brief.py`) z aktivní nebo zadané verze plátna (číslo `n`)."""
    row = _workflow(db, workflow_id)
    versions = list_versions(db, workflow_id)
    version = next((v for v in versions if v["n"] == n), None) if n is not None else next(
        (v for v in versions if v["status"] == "active"), None)
    if version is None:
        raise FlowNotFound(f"Plátno nemá verzi {n}." if n is not None else "Plátno nemá aktivní verzi.")
    return brief({"title": row["name"], "description": row["description"], "ownerRef": row["owner_ref"]}, version,
                 version["graph"])


def create_flow(db, folder_id, slug, title, description=None):
    folder = get_folder(db, folder_id)
    created = create_workflow(db, KIND, title, None, owner_ref(folder["owner"], folder["slug"], _slug(slug)),
                              description)
    return flow_detail(db, created["id"])


def _source_version(db, workflow_id):
    """Verze, ze které se kopíruje: aktivní, jinak nejnovější."""
    versions = list_versions(db, _workflow(db, workflow_id)["id"])
    active = [v for v in versions if v["status"] == "active"]
    if not versions:
        raise FlowConflict("Plátno toku nemá žádnou verzi, není co převzít.", "empty_flow")
    return (active or versions)[-1]


def _copy(db, workflow_id, name, project_id, ref, description):
    """Nové workflow s první verzí = graf zdroje, rodokmen na zdrojovou verzi, rovnou aktivní."""
    source = _source_version(db, workflow_id)
    created = create_workflow(db, KIND, name, project_id, ref, description)
    draft = create_draft(db, created["id"], source["graph"],
                         derived_from={"workflowId": workflow_id, "versionId": source["id"]})
    activate(db, set_candidate(db, draft["id"])["id"])
    return flow_detail(db, created["id"])


def adopt(db, workflow_id, project_id, node_id=None):
    """Převezme plátno knihovny do projektu jako odvozenou kopii (`opora:project-flow:<nodeId|slug>`)."""
    row = _workflow(db, workflow_id)
    match = LIBRARY_OWNER.fullmatch(row["owner_ref"] or "")
    if row["project_id"] is not None or not match:
        raise FlowInvalid("Převzít do projektu jde jen plátno z knihovny.")
    return _copy(db, workflow_id, row["name"], project_id, f"opora:project-flow:{node_id or match.group(3)}",
                 row["description"])


def contribute(db, workflow_id, folder_id, slug, title):
    """Uloží plátno (typicky kopii z projektu) do složky knihovny jako nový prvek s rodokmenem na zdroj."""
    folder = get_folder(db, folder_id)
    row = _workflow(db, workflow_id)
    return _copy(db, workflow_id, title, None, owner_ref(folder["owner"], folder["slug"], _slug(slug)),
                 row["description"])


def promote(db, workflow_id, folder_id=None):
    """Přesune plátno z knihovny agenta do složky člověka (zadané, jinak se stejným slugem)."""
    row = _workflow(db, workflow_id)
    match = LIBRARY_OWNER.fullmatch(row["owner_ref"] or "")
    if not match or match.group(1) != "agent":
        raise FlowConflict("Povýšit jde jen plátno z knihovny agenta.", "not_agent_flow")
    if folder_id is None:
        found = db.execute("SELECT id FROM flow_library_folders WHERE owner='human' AND slug=?",
                           (match.group(2),)).fetchone()
        if found is None:
            raise FlowNotFound(f"Knihovna člověka nemá složku {match.group(2)}; zadejte folder.")
        folder_id = found["id"]
    folder = get_folder(db, folder_id)
    if folder["owner"] != "human":
        raise FlowInvalid("Povýšení míří do složky člověka.")
    try:
        with transaction(db):
            db.execute("UPDATE flow_workflows SET owner_ref=? WHERE id=?",
                       (owner_ref("human", folder["slug"], match.group(3)), workflow_id))
    except sqlite3.IntegrityError as error:
        raise FlowConflict(f"Složka {folder['slug']} už plátno {match.group(3)} má.", "owner_taken") from error
    return flow_detail(db, workflow_id)
