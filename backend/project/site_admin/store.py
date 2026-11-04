"""Úložiště Správy webu: `projects/<id>/site/` ve složce projektu (vedle `project.json`, `ProjectFolder`).

- `site/design-system.json`: dokument projektu s revizí. Zápis nese `expectedRevision`; jiná než uložená (nový
  dokument = 0) je `SiteAdminConflict` (HTTP 409). Uložený dokument dostane `revision + 1` a `lastChange`.
  Zápis je atomický (`.tmp` + `os.replace`) pod zámkem dat projektu.
- `site/assets/<skupina>/<soubor>` a `site/fonts/<soubor>`: binární soubory. Typ se pozná z prvních bajtů a musí
  sedět s příponou; limity: asset 10 MB, SVG 2 MB (bez skriptů a obsluh událostí), font 2 MB, nejvýš 5000 assetů.
"""

import base64
import binascii
import json
import os
import re
from datetime import UTC, datetime

from backend.canvas.canvas_service import ProjectNotFound
from backend.project.site_admin.design_system import GROUP, MAX_ASSETS, empty, normalize
from backend.project.site_admin.tokens import SiteAdminInvalid

FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,126}[A-Za-z0-9_-]\.[A-Za-z0-9]{2,5}$|^[A-Za-z0-9]\.[A-Za-z0-9]{2,5}$")
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
ASSET_LIMIT, SVG_LIMIT, FONT_LIMIT = 10 * 1024 * 1024, 2 * 1024 * 1024, 2 * 1024 * 1024
UNSAFE_SVG = re.compile(rb"<script|<foreignobject|[\s/\"']on[a-z]+\s*=|javascript:|&#|<iframe|<embed|<object", re.IGNORECASE)
ASSET_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
               "webp": "image/webp", "svg": "image/svg+xml", "mp4": "video/mp4", "webm": "video/webm",
               "pdf": "application/pdf"}
FONT_TYPES = {"woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf", "otf": "font/otf",
              "ttc": "font/collection"}


class SiteAdminConflict(Exception):
    """Dokument mezitím uložil někdo jiný (HTTP 409)."""


class SiteFileMissing(LookupError):
    """Soubor assetu nebo fontu neexistuje (HTTP 404)."""


def site_dir(service, project):
    if not isinstance(project, str) or not service.project_exists(project):
        raise ProjectNotFound(project)
    return service.folder(project).path / "site"


def _document_path(service, project):
    return site_dir(service, project) / "design-system.json"


def read(service, project):
    """Uložený dokument, nebo prázdný s `revision: 0`. Poškozený soubor se čte jako prázdný."""
    path = _document_path(service, project)
    try:
        stored = json.loads(path.read_text("utf-8"))
        document, _ = normalize(stored)
        return {**document, "revision": stored["revision"], "lastChange": stored.get("lastChange")}
    except (OSError, ValueError, KeyError, TypeError):
        return empty()


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write(service, project, expected_revision, document, note=None):
    """Ověří dokument a uloží ho nad `expected_revision`; vrací `(uložený dokument, poznámky)`."""
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise SiteAdminInvalid("expectedRevision musí být celé číslo ≥ 0.")
    if note is not None and (not isinstance(note, str) or len(note) > 280):
        raise SiteAdminInvalid("note je jeden řádek do 280 znaků.")
    with service.lock_for(project):
        stored = read(service, project)
        current = stored["revision"]
        if expected_revision != current:
            raise SiteAdminConflict(f"Dokument mezitím uložil někdo jiný (revize {current}, zápis nad {expected_revision}).")
        normalized, notes = normalize(document, stored)
        change = {"by": "human", "via": "page", "at": datetime.now(UTC).isoformat(timespec="seconds")}
        saved = {**normalized, "revision": current + 1, "lastChange": change | ({"note": note} if note else {})}
        _atomic(_document_path(service, project), json.dumps(saved, ensure_ascii=False, indent=2).encode("utf-8"))
    return saved, notes


def _sniff(data):
    """Typ souboru podle prvních bajtů (přípona se jen porovná)."""
    signatures = ((b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg"), (b"GIF87a", "gif"), (b"GIF89a", "gif"),
                  (b"%PDF-", "pdf"), (b"\x1a\x45\xdf\xa3", "webm"), (b"wOF2", "woff2"), (b"wOFF", "woff"),
                  (b"\x00\x01\x00\x00", "ttf"), (b"true", "ttf"), (b"OTTO", "otf"), (b"ttcf", "ttc"))
    for prefix, kind in signatures:
        if data.startswith(prefix):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp":
        return "mp4"
    head = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith((b"<svg", b"<?xml", b"<!--")) and b"<svg" in head:
        return "svg"
    return None


def _name(value, label, pattern=FILE):
    if not isinstance(value, str) or not pattern.match(value) or value.split(".")[0].lower() in RESERVED:
        raise SiteAdminInvalid(f"{label} {value!r}: písmena, číslice, mezera, _ . - (bez tečky a mezery na konci).")
    return value


def _decode(data):
    if not isinstance(data, str):
        raise SiteAdminInvalid("data musí být base64 obsahu souboru.")
    try:
        return base64.b64decode(data.split(",", 1)[1] if data.startswith("data:") else data, validate=True)
    except (binascii.Error, ValueError) as error:
        raise SiteAdminInvalid("data nejsou platné base64.") from error


def _checked(name, data, types, limit):
    extension = name.rsplit(".", 1)[-1].lower()
    kind = _sniff(data)
    if extension not in types or kind is None or ASSET_TYPES.get(kind, FONT_TYPES.get(kind)) != types[extension]:
        raise SiteAdminInvalid(f"{name}: obsah neodpovídá povolenému typu ({', '.join(sorted(types))}).")
    if not data or len(data) > (SVG_LIMIT if kind == "svg" else limit):
        raise SiteAdminInvalid(f"{name}: soubor je prázdný nebo větší než limit.")
    if kind == "svg" and UNSAFE_SVG.search(data):
        raise SiteAdminInvalid(f"{name}: SVG nesmí obsahovat skripty, obsluhy událostí ani vnořený obsah.")
    return types[extension]


def put_asset(service, project, group, name, data):
    """Uloží asset; vrací záznam do `design.assetGroups[].files[]`."""
    _name(group, "Skupina", GROUP)
    _name(name, "Soubor")
    raw = _decode(data)
    media = _checked(name, raw, ASSET_TYPES, ASSET_LIMIT)
    root = site_dir(service, project) / "assets"
    with service.lock_for(project):
        count = sum(1 for path in root.rglob("*") if path.is_file()) if root.exists() else 0
        target = root / group / name
        if count >= MAX_ASSETS and not target.exists():
            raise SiteAdminInvalid(f"Nejvýš {MAX_ASSETS} assetů.")
        _atomic(target, raw)
    return {"name": name, "blob": f"assets/{group}/{name}", "size": len(raw), "type": media}


def put_font(service, project, name, data):
    """Uloží font; vrací `{file, size, type}` (`file` patří do `design.tokens.type.fonts[].file`)."""
    _name(name, "Font")
    raw = _decode(data)
    media = _checked(name, raw, FONT_TYPES, FONT_LIMIT)
    with service.lock_for(project):
        _atomic(site_dir(service, project) / "fonts" / name, raw)
    return {"file": f"fonts/{name}", "size": len(raw), "type": media}


def _file(service, project, parts, types):
    media = types.get(parts[-1].rsplit(".", 1)[-1].lower())
    if media is None:
        raise SiteFileMissing(f"Soubor {parts[-1]} neexistuje.")
    return site_dir(service, project).joinpath(*parts), media


def asset_path(service, project, group, name):
    path, media = _file(service, project, ("assets", _name(group, "Skupina", GROUP), _name(name, "Soubor")), ASSET_TYPES)
    if not path.is_file():
        raise SiteFileMissing(f"Asset {group}/{name} neexistuje.")
    return path, media


def font_path(service, project, name):
    path, media = _file(service, project, ("fonts", _name(name, "Font")), FONT_TYPES)
    if not path.is_file():
        raise SiteFileMissing(f"Font {name} neexistuje.")
    return path, media


def delete_asset(service, project, group, name):
    path, _ = asset_path(service, project, group, name)
    with service.lock_for(project):
        path.unlink()
        if not any(path.parent.iterdir()):
            path.parent.rmdir()


def delete_font(service, project, name):
    path, _ = font_path(service, project, name)
    with service.lock_for(project):
        path.unlink()
