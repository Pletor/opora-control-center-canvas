"""Referenced local assets and exception rollback for filesystem writes.

SQLite and files share exception rollback, not a power-loss transaction.
Missing source assets are recorded explicitly; external links are never fetched.
"""
import base64
import os
import uuid
from contextlib import contextmanager

from backend.canvas.graph import valid_id
from backend.editor.agent_memory.desktop_v3_state import UPLOAD_FILE
from backend.editor.node.drawing_files import decode_file


def material_path(canvas, project, node, filename):
    if not valid_id(node) or not isinstance(filename, str) or not UPLOAD_FILE.fullmatch(filename):
        raise ValueError("Neplatný soubor podkladu ve verzi.")
    root = canvas.folder(project).path.resolve()
    target = canvas.folder(project).canvas / "materials" / node / filename
    if not target.resolve().is_relative_to(root):
        raise ValueError("Podklad verze vede mimo složku projektu.")
    return target


def capture_assets(canvas, db, project, state, records):
    uploads = {}
    for node_id, node in state["nodes"].items():
        for item in node.get("materials", []):
            if item["kind"] == "upload":
                filename = item["path"]
                path = material_path(canvas, project, node_id, filename)
                uploads[(node_id, filename)] = {
                    "nodeId": node_id, "file": filename,
                    "data": base64.b64encode(path.read_bytes()).decode("ascii") if path.is_file() else None,
                }
    ids = set()
    for row in records["drawings"]:
        # Deleted Excalidraw elements remain undoable in the saved scene.
        ids.update(element["fileId"] for element in row["data"]["scene"]["elements"] if element.get("type") == "image")
    drawings = []
    for file_id in sorted(ids):
        row = db.execute("SELECT mime_type,data FROM drawing_files WHERE project_id=? AND file_id=?", (project, file_id)).fetchone()
        drawings.append({"id": file_id, "file": None if row is None else {
            "id": file_id, "mimeType": row["mime_type"],
            "dataURL": f"data:{row['mime_type']};base64," + base64.b64encode(row["data"]).decode("ascii"),
        }})
    return {"uploads": [uploads[key] for key in sorted(uploads)], "drawings": drawings}


def unavailable_assets(snapshot):
    if snapshot is None:
        return 0
    assets = snapshot["assets"]
    return sum(item["data"] is None for item in assets["uploads"]) + sum(item["file"] is None for item in assets["drawings"])


def prepare_assets(canvas, db, project, assets):
    """Validate all bytes before writes, and never overwrite a different shared asset."""
    files, drawings = {}, []
    for item in assets["uploads"]:
        path = material_path(canvas, project, item["nodeId"], item["file"])
        if item["data"] is None:
            continue
        data = base64.b64decode(item["data"], validate=True)
        if not data or len(data) > 8 * 1024 * 1024:
            raise ValueError("Neplatná velikost podkladu ve verzi.")
        if path.exists() and path.read_bytes() != data:
            raise ValueError("Sdílený podklad se změnil; obnovení by přepsalo obsah jiného prostoru.")
        if not path.exists():
            files[path] = data
    for item in assets["drawings"]:
        if item["file"] is None:
            continue
        file_id, mime, data = decode_file(item["file"])
        if file_id != item["id"]:
            raise ValueError("Neplatná identita obrázku ve verzi.")
        row = db.execute("SELECT mime_type,data FROM drawing_files WHERE project_id=? AND file_id=?", (project, file_id)).fetchone()
        if row is not None and (row["mime_type"] != mime or row["data"] != data):
            raise ValueError("Sdílený obrázek se změnil; obnovení by přepsalo jiný prostor.")
        if row is None:
            drawings.append((file_id, mime, data))
    return files, drawings


def replace_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".version-" + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def file_rollback(paths):
    previous = {path: path.read_bytes() if path.exists() else None for path in paths}
    try:
        yield
    except BaseException:
        for path, data in previous.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                replace_bytes(path, data)
        raise
