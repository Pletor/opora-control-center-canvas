"""Obrázky kresby: soubory vložené do Excalidraw (screenshot, přetažení, nástroj Obrázek).

Scéna nese jen `fileId`; samotná data obrázku leží zde, jednou na projekt, a kresby různých vrstev je sdílejí.
"""

import base64
import binascii
import re
from datetime import UTC, datetime

FILE_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_IDS_PER_REQUEST = 200


def valid_file_id(value):
    return isinstance(value, str) and FILE_ID.fullmatch(value) is not None


def decode_file(file):
    """Ověří {id, mimeType, dataURL} a vrátí (id, mimeType, bajty)."""
    if not isinstance(file, dict) or set(file) != {"id", "mimeType", "dataURL"}:
        raise ValueError("Neplatný formát obrázku kresby.")
    file_id, mime_type, data_url = file["id"], file["mimeType"], file["dataURL"]
    if not valid_file_id(file_id):
        raise ValueError("Neplatné ID obrázku kresby.")
    if mime_type not in MIME_TYPES:
        raise ValueError("Podporované jsou jen obrázky PNG, JPEG, WebP a GIF.")
    prefix = f"data:{mime_type};base64,"
    if not isinstance(data_url, str) or not data_url.startswith(prefix):
        raise ValueError("Obrázek kresby musí být data URL odpovídajícího typu.")
    encoded = data_url[len(prefix):]
    if len(encoded) > (MAX_FILE_BYTES // 3 + 1) * 4:
        raise ValueError("Obrázek kresby je větší než 10 MB.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Obrázek kresby není platně zakódovaný.") from exc
    if not data:
        raise ValueError("Obrázek kresby je prázdný.")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Obrázek kresby je větší než 10 MB.")
    if not looks_like(mime_type, data):
        raise ValueError("Obsah souboru neodpovídá udanému typu obrázku (PNG, JPEG, WebP, GIF).")
    return file_id, mime_type, data


def looks_like(mime_type, data):
    """Hlavička souboru odpovídá typu: base64 sám o sobě obrázek nedokazuje."""
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if mime_type == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    return False


def parse_ids(value):
    """`a,b,c` → seznam unikátních platných ID (nejvýše 200)."""
    if not isinstance(value, str):
        raise ValueError("Neplatný seznam obrázků kresby.")  # noqa: TRY004 - klientská validační chyba mapovaná na HTTP 409
    ids = list(dict.fromkeys(item for item in value.split(",") if item))
    if len(ids) > MAX_IDS_PER_REQUEST:
        raise ValueError("Najednou lze načíst nejvýše 200 obrázků kresby.")
    if not all(valid_file_id(item) for item in ids):
        raise ValueError("Neplatné ID obrázku kresby.")
    return ids


class DrawingFileStore:
    def __init__(self, canvas):
        self.canvas = canvas

    def put(self, pid, file):
        file_id, mime_type, data = decode_file(file)
        db = self.canvas.db_for(pid)
        # Stejné ID znovu je v pořádku: Excalidraw ID odvozuje z obsahu, druhé nahrání nic nezdvojí.
        # Stejné ID s jiným obsahem je chyba: tiché ponechání starých bajtů by podvrhlo obrázek pod cizí ID.
        row = db.execute("SELECT data FROM drawing_files WHERE project_id=? AND file_id=?", (pid, file_id)).fetchone()
        if row is not None and bytes(row[0]) != data:
            raise ValueError("Obrázek s tímto ID už v projektu existuje s jiným obsahem.")
        db.execute(
            "INSERT OR IGNORE INTO drawing_files VALUES(?,?,?,?,?)",
            (pid, file_id, mime_type, data, datetime.now(UTC).isoformat()),
        )
        db.commit()
        return {"id": file_id}

    def get(self, pid, ids):
        if not isinstance(ids, list) or len(ids) > MAX_IDS_PER_REQUEST:
            raise ValueError("Najednou lze načíst nejvýše 200 obrázků kresby.")
        if not ids:
            return []
        if not all(valid_file_id(item) for item in ids):
            raise ValueError("Neplatné ID obrázku kresby.")
        rows = self.canvas.db_for(pid).execute(
            f"""SELECT file_id,mime_type,data,created_at FROM drawing_files
                WHERE project_id=? AND file_id IN ({",".join("?" * len(ids))})""",
            (pid, *ids),
        ).fetchall()
        return [
            {
                "id": row["file_id"],
                "mimeType": row["mime_type"],
                "dataURL": f"data:{row['mime_type']};base64,"
                + base64.b64encode(row["data"]).decode("ascii"),
                "created": int(datetime.fromisoformat(row["created_at"]).timestamp() * 1000),
            }
            for row in rows
        ]

    def missing(self, db, pid, ids):
        """ID, která v projektu chybí; čte přes předané spojení (uvnitř transakce ukládání)."""
        if not ids:
            return set()
        found = {
            row[0]
            for row in db.execute(
                f"SELECT file_id FROM drawing_files WHERE project_id=? AND file_id IN ({','.join('?' * len(ids))})",
                (pid, *ids),
            )
        }
        return set(ids) - found
