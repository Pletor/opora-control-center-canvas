"""Design náhled karty `evidence.preview` (docs/design-nahled.md): screenshoty na hlavu PR a lidské potvrzení vzhledu.

Vzor je PR Lens (`opora_review_lens.py`): pracovník posílá doklad s lease tokenem a epochou svého běhu, jen pro
aktuální hlavu otevřeného navázaného PR. Navíc (stejně jako propojení PR) platí i běh, který už nahlásil výsledek:
office dělá screenshoty často až po odevzdání. Na jednu hlavu běhu nejvýš 8 PNG, štítek je klíč (stejný štítek se
stejným obsahem = nic nového, jiný obsah = konflikt). Bajty PNG leží v `drawing_files` pod obsahovým ID.
Potvrzení vzhledu dává jen člověk; v bráně merge je to doklad, nikdy nový důvod blokace."""
import json
import re
from urllib.parse import urlencode

from backend.canvas import opora_design_mode as design_mode
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_design_preview_validation import (
    MAX_SHOTS,
    SHA,
    validate_preview,
    with_mode,
)
from backend.canvas.opora_execution_validation import validate
from backend.editor.node.drawing_files import valid_file_id
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests

EXECUTION = re.compile(r"[A-Za-z0-9_-]{1,80}")
COLUMNS = "execution_id,head_sha,pr_number,record,by,created_at,updated_at"


def _rows(db, project, workspace, node_id):
    rows = db.execute(f"SELECT {COLUMNS} FROM opora_design_previews WHERE project_id=? AND workspace_id=? AND node_id=?"
                      " ORDER BY created_at DESC, rowid DESC", (project, workspace, node_id)).fetchall()
    return [{"executionId": row[0], "headSha": row[1], "prNumber": row[2], "record": json.loads(row[3]), "by": row[4],
             "createdAt": row[5], "updatedAt": row[6]} for row in rows]


def _confirmations(db, project, workspace, node_id):
    rows = db.execute("SELECT head_sha,by,confirmed_at FROM opora_design_preview_confirmations"
                      " WHERE project_id=? AND workspace_id=? AND node_id=?", (project, workspace, node_id))
    return {row[0]: {"by": row[1], "at": row[2]} for row in rows}


def file_url(project, workspace, node_id, file_id):
    query = urlencode({"project": project, "workspace": workspace, "nodeId": node_id, "fileId": file_id})
    return "/api/oporahub/review-preview/file?" + query


def for_node(db, project, workspace, node_id):
    """`GET /review-preview`: režim karty a doklady po hlavách, nejnovější první (s URL souborů a potvrzením)."""
    confirmed, links, heads = _confirmations(db, project, workspace, node_id), {}, []
    for item in _rows(db, project, workspace, node_id):
        if item["executionId"] not in links:
            links[item["executionId"]] = ExecutionPullRequests(db, project, workspace).read(item["executionId"])
        link, record = links[item["executionId"]], item["record"]
        heads.append({
            "executionId": item["executionId"], "prNumber": item["prNumber"], "headSha": item["headSha"],
            "repository": link and link["repository"], "prState": link and link["state"],
            "current": bool(link) and link["head_sha"] == item["headSha"] and link["number"] == item["prNumber"],
            "mode": record["mode"], "designMdSha256": record["designMdSha256"],
            "proposedDesignMd": record.get("proposedDesignMd"), "by": item["by"], "createdAt": item["createdAt"],
            "updatedAt": item["updatedAt"], "confirmed": confirmed.get(item["headSha"]),
            "screenshots": [{**shot, "url": file_url(project, workspace, node_id, shot["fileId"])}
                            for shot in record["screenshots"]]})
    return {"nodeId": node_id, "design": design_mode.read(db, project, workspace, node_id), "heads": heads}


def for_link(db, project, workspace, link):
    """Čtení brány: doklad pro aktuální hlavu PR nebo None. Jen doklad, nikdy důvod blokace."""
    row = db.execute("SELECT node_id,record FROM opora_design_previews WHERE project_id=? AND workspace_id=?"
                     " AND execution_id=? AND head_sha=?",
                     (project, workspace, link["execution_id"], link["head_sha"])).fetchone()
    if row is None:
        return None
    record = json.loads(row[1])
    return {"headSha": link["head_sha"], "mode": record["mode"], "designMdSha256": record["designMdSha256"],
            "screenshots": len(record["screenshots"]), "labels": [shot["label"] for shot in record["screenshots"]],
            "proposedDesignMd": "proposedDesignMd" in record,
            "confirmed": _confirmations(db, project, workspace, row[0]).get(link["head_sha"])}


def png(db, project, workspace, node_id, file_id):
    """Bajty screenshotu, jen když `fileId` patří k dokladu této karty (ne libovolný obrázek projektu)."""
    if not valid_file_id(file_id) or not any(shot["fileId"] == file_id for item in _rows(db, project, workspace, node_id)
                                             for shot in item["record"]["screenshots"]):
        return None
    row = db.execute("SELECT data FROM drawing_files WHERE project_id=? AND file_id=? AND mime_type='image/png'",
                     (project, file_id)).fetchone()
    return bytes(row[0]) if row else None


def _merge(existing, value):
    """Další odeslání pro stejnou hlavu: režim a otisk DESIGN.md se nemění, štítky přibývají (nejvýš 8)."""
    if existing["mode"] != value["mode"] or existing["designMdSha256"] != value["designMdSha256"]:
        raise ValueError("Preview for this head was already recorded with a different design mode or DESIGN.md.")
    proposals = {existing.get("proposedDesignMd"), value.get("proposedDesignMd")} - {None}
    if len(proposals) > 1:
        raise ValueError("Preview for this head already holds a different proposedDesignMd.")
    shots, added = list(existing["screenshots"]), []
    for shot in value["screenshots"]:
        same = next((old for old in shots if old["label"] == shot["label"]), None)
        if same is None:
            shots.append(shot)
            added.append(shot["label"])
        elif same != shot:
            raise ValueError(f"Screenshot '{shot['label']}' for this head was already recorded with different content.")
    if len(shots) > MAX_SHOTS:
        raise ValueError(f"A head holds at most {MAX_SHOTS} screenshots.")
    merged = {**existing, "screenshots": shots}
    if proposals:
        merged["proposedDesignMd"] = proposals.pop()
    return merged, added


class PreviewAddenda:
    """`POST /review-jobs/preview`: doklad od běhu samotného (lease token + epocha), pro hlavu otevřeného PR."""

    def __init__(self, jobs):
        self.executions = jobs.executions

    def authorize(self, repo, record):
        """Běžící běh s platným leasem, nebo běh s nahlášeným výsledkem (jako propojení PR)."""
        if record["state"] == "running":
            try:
                self.executions.active(repo, record)
                return
            except ValueError:
                pass
        if record["state"] == "reported" or repo.receipts(record["executionId"]):
            return
        raise ValueError("Execution has no active lease and no reported result; it is no longer authoritative.")

    def submit(self, payload, by):
        project, workspace = validate(payload, {"executionId", "token", "epoch", "preview"})
        execution_id = payload["executionId"]
        if not isinstance(execution_id, str) or EXECUTION.fullmatch(execution_id) is None:
            raise ValueError("Invalid executionId.")
        value, files = validate_preview(payload["preview"])
        with self.executions.transaction(project, workspace) as repo:
            record = repo.read(execution_id)
            self.executions.authenticate(record, payload["token"], payload["epoch"])
            self.authorize(repo, record)
            link = ExecutionPullRequests(repo.db, project, workspace).read(execution_id)
            if link is None or link["state"] != "open":
                raise ValueError("The execution has no open linked pull request.")
            if link["head_sha"] != value["headSha"] or link["number"] != value["prNumber"]:
                raise ValueError("Preview evidence must be for the current head of the linked pull request.")
            node_id = record["nodeId"]
            value = with_mode(value, design_mode.read(repo.db, project, workspace, node_id)["mode"])
            key = (project, workspace, execution_id, value["headSha"])
            row = repo.db.execute("SELECT record,created_at FROM opora_design_previews WHERE project_id=?"
                                  " AND workspace_id=? AND execution_id=? AND head_sha=?", key).fetchone()
            now = stamp()
            if row is None:
                merged, added, created = value, [shot["label"] for shot in value["screenshots"]], now
            else:
                (merged, added), created = _merge(json.loads(row[0]), value), row[1]
            for shot in value["screenshots"]:
                if shot["label"] in added:
                    repo.db.execute("INSERT OR IGNORE INTO drawing_files VALUES(?,?,?,?,?)",
                                    (project, shot["fileId"], "image/png", files[shot["fileId"]], now))
            changed = row is None or merged != json.loads(row[0])
            if changed:
                repo.db.execute("INSERT OR REPLACE INTO opora_design_previews VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (*key, node_id, value["prNumber"], json.dumps(merged, ensure_ascii=False,
                                 sort_keys=True), by, created, now))
            return {"executionId": execution_id, "headSha": value["headSha"], "mode": value["mode"],
                    "added": added, "screenshots": len(merged["screenshots"]), "recorded": changed}


def confirm(service, payload, by):
    """„Potvrdit vzhled“: člověk potvrdí screenshoty karty pro jednu hlavu PR (`evidence.preview.confirmed`)."""
    project, workspace = validate(payload, {"nodeId", "headSha"})
    node_id, head = payload["nodeId"], payload["headSha"]
    if not isinstance(head, str) or SHA.fullmatch(head) is None:
        raise ValueError("headSha must be a full lowercase commit SHA.")
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        with db:
            if not any(item["headSha"] == head for item in _rows(db, project, workspace, node_id)):
                raise ValueError("No preview screenshots are recorded for this card and head.")
            at = stamp()
            recorded = db.execute("INSERT OR IGNORE INTO opora_design_preview_confirmations VALUES(?,?,?,?,?,?)",
                                  (project, workspace, node_id, head, by, at)).rowcount == 1
            return {"nodeId": node_id, "headSha": head, "recorded": recorded,
                    "confirmed": _confirmations(db, project, workspace, node_id)[head]}
