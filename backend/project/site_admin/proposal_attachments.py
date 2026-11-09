"""Immutable staged binaries for the existing Site proposal authority."""
import hashlib
import os
import re
import uuid

from backend.project.site_admin import store
from backend.project.site_admin.tokens import SiteAdminInvalid, shape

MAX_FILES, BUNDLE_BYTES, STAGED_BYTES = 50, 100 * 1024 * 1024, 256 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}")


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def path(service, project, relative):
    store.site_dir(service, project)  # Validate the project before resolving any file.
    root = service.folder(project).path
    if root.is_symlink() or getattr(os.path, "isjunction", lambda _: False)(root):
        raise SiteAdminInvalid("Site proposal project cannot be a symbolic link or junction.")
    target = root / "site"
    for part in ("site", *relative.split("/")):
        if part in ("", ".", "..") or ":" in part or "\\" in part:
            raise SiteAdminInvalid("Invalid Site file path.")
    current = root
    for part in ("site", *relative.split("/")):
        current = current / part
        if current.is_symlink() or getattr(os.path, "isjunction", lambda _: False)(current):
            raise SiteAdminInvalid("Site proposal paths cannot use symbolic links or junctions.")
    target = target.joinpath(*relative.split("/"))
    if not target.resolve().is_relative_to(root.resolve()):
        raise SiteAdminInvalid("Site file escapes its project.")
    return target


def read(service, project, relative):
    target = path(service, project, relative)
    if target.exists() and target.stat().st_size > BUNDLE_BYTES:
        raise SiteAdminInvalid("Site proposal file exceeds the bounded bundle size.")
    return target.read_bytes() if target.exists() else None


def write(service, project, relative, data):
    target = path(service, project, relative)
    if data is None:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = path(service, project, relative + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def blob(service, project, key):
    shape(isinstance(key, str) and HASH.fullmatch(key), "Invalid staged blob digest.")
    raw = read(service, project, "proposals/blobs/" + key)
    shape(raw is not None and digest(raw) == key, "Staged blob is missing or changed.")
    return raw


def content(service, project, identifier, index):
    """Read one immutable attachment through the proposal's own scoped reference."""
    from backend.project.site_admin import proposals
    from backend.project.site_admin.store import SiteFileMissing
    target = proposals._path(service, project, identifier)
    if not target.is_file():
        raise SiteFileMissing('Staged proposal does not exist.')
    record = proposals._load(target)
    items = record.get('attachments', [])
    if type(index) is not int or index < 0 or index >= len(items) or items[index]['op'] != 'put':
        raise SiteFileMissing('Staged attachment does not exist.')
    item = items[index]
    return item, blob(service, project, item['sha256'])


def save_blob(service, project, raw):
    if raw is None:
        return None
    key = digest(raw)
    existing = read(service, project, "proposals/blobs/" + key)
    if existing is not None:
        shape(existing == raw, "Immutable staged blob changed.")
        return key
    folder = path(service, project, "proposals/blobs")
    total = sum(p.stat().st_size for p in folder.iterdir() if p.is_file()) if folder.exists() else 0
    shape(total + len(raw) <= STAGED_BYTES, "Site staged blob quota exceeded.")
    write(service, project, "proposals/blobs/" + key, raw)
    return key


def prepare(service, project, values):
    shape(isinstance(values, list) and 0 < len(values) <= MAX_FILES, "attachments must contain 1..50 operations.")
    found, paths, size = [], set(), 0
    for value in values:
        shape(isinstance(value, dict) and value.get("kind") in ("asset", "font") and value.get("op") in ("put", "delete"),
              "Attachment kind/op is invalid.")
        required = {"kind", "op", "name"} | ({"group"} if value["kind"] == "asset" else set()) | ({"data"} if value["op"] == "put" else set())
        shape(set(value) == required, "Attachment fields differ from its operation.")
        name = store._name(value["name"], "File")
        group = store._name(value["group"], "Group", store.GROUP) if value["kind"] == "asset" else None
        relative = f"assets/{group}/{name}" if group else f"fonts/{name}"
        shape(relative.casefold() not in paths, "A bundle cannot change one target twice.")
        paths.add(relative.casefold())
        before = read(service, project, relative)
        raw, media = None, None
        if value["op"] == "put":
            shape(isinstance(value["data"], str) and len(value["data"]) <= 4 * store.ASSET_LIMIT // 3 + 1024,
                  "Attachment encoded size exceeds its limit.")
            raw = store._decode(value["data"])
            media = store._checked(name, raw, store.ASSET_TYPES if group else store.FONT_TYPES,
                                   store.ASSET_LIMIT if group else store.FONT_LIMIT)
        else:
            shape(before is not None, "Deleted attachment must exist at proposal creation.")
        shape(before != raw, "Attachment does not change its target.")
        size += len(before or b"") + len(raw or b"")
        shape(size <= BUNDLE_BYTES, "Site attachment bundle exceeds 100 MiB including backups.")
        found.append({"kind": value["kind"], "op": value["op"], "name": name,
                      **({"group": group} if group else {}), "path": relative, "baseDigest": digest(before),
                      "sha256": digest(raw), "size": len(raw or b""), "type": media, "_raw": raw})
    quota(service, project, found)
    for item in found:
        save_blob(service, project, item.pop("_raw"))
    return found


def quota(service, project, attachments):
    folder = path(service, project, "assets")
    existing = {p.relative_to(folder).as_posix().casefold() for p in folder.rglob("*") if p.is_file()} if folder.exists() else set()
    for item in attachments:
        if item["kind"] == "asset":
            key = item["path"][len("assets/"):].casefold()
            existing.discard(key)
            if item["op"] == "put":
                existing.add(key)
    shape(len(existing) <= store.MAX_ASSETS, "Site asset quota exceeded.")
