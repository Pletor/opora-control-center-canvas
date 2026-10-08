"""Nahrané podklady uzlu: obrázky ze schránky nebo z disku uložené do složky projektu.

Soubor leží v projects/<id>/canvas/materials/<uzel>/<jméno>; odkaz na něj (jméno souboru) si klient
zapíše do stavu Desktop v3 pod nodes[uzel].materials jako kind="upload". Modul nemění graf ani stav uzlu.
"""
from __future__ import annotations

import base64
import hashlib
import re
from datetime import UTC, datetime

from backend.canvas.graph import valid_id

MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
SUFFIX_MIME = {suffix: mime for mime, suffix in MIME_TYPES.items()}
MAX_BYTES = 8 * 1024 * 1024
FILE_NAME = re.compile(r"^[0-9]{8}-[0-9]{6}-[a-f0-9]{8}\.(png|jpg|gif|webp|svg)$")
DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|gif|webp|svg\+xml));base64,([A-Za-z0-9+/=\s]+)$")


class NodeMaterials:
    def __init__(self, canvas):
        self.canvas = canvas

    def _folder(self, project, node_id):
        if not valid_id(node_id):
            raise ValueError("Neplatné ID uzlu.")
        return self.canvas.folder(project).canvas / "materials" / node_id

    def save_upload(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "nodeId", "dataUrl"}:
            raise ValueError("Neplatný formát nahrání podkladu.")
        project, workspace, node_id, data_url = (payload[k] for k in ("project", "workspace", "nodeId", "dataUrl"))
        if not isinstance(data_url, str):
            raise ValueError("Podklad musí být obrázek jako data URL.")
        match = DATA_URL.match(data_url)
        if not match:
            raise ValueError("Podklad musí být obrázek (png, jpg, gif, webp, svg) jako data URL.")
        mime, encoded = match.groups()
        try:
            content = base64.b64decode(encoded, validate=False)
        except ValueError as error:
            raise ValueError("Obrázek se nepodařilo dekódovat.") from error
        if not content or len(content) > MAX_BYTES:
            raise ValueError("Obrázek je prázdný nebo větší než 8 MB.")
        with self.canvas.graph_lock:
            view = self.canvas.view(project, workspace)
            if not valid_id(node_id) or not any(n["id"] == node_id for n in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení; podklady se přidávají v pracovním prostoru.")
            folder = self._folder(project, node_id)
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            digest = hashlib.sha256(content).hexdigest()[:8]
            name = f"{stamp}-{digest}{MIME_TYPES[mime]}"
            (folder / name).write_bytes(content)
        return {"file": name, "bytes": len(content), "mime": mime}

    def file_path(self, project, node_id, name):
        """Cesta a MIME uloženého souboru; cizí jméno nebo cesta mimo složku končí FileNotFoundError."""
        if not isinstance(name, str) or not FILE_NAME.match(name):
            raise FileNotFoundError(name)
        target = self._folder(project, node_id) / name
        if not target.is_file():
            raise FileNotFoundError(name)
        return target, SUFFIX_MIME[target.suffix]

    def remove(self, project, node_id, name):
        with self.canvas.graph_lock:
            try:
                target, _ = self.file_path(project, node_id, name)
            except (FileNotFoundError, ValueError):
                return False
            target.unlink()
            return True
