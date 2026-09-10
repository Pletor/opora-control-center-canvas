"""Scope-bound tools for one bounded documentation result."""

import hashlib
import os
import stat
from pathlib import Path

MAX_RESULT_BYTES = 64_000


def _reparse(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


class DocumentTools:
    def __init__(self, root, context):
        self.root = Path(root)
        self.context = context
        # Remember the actual directory identity; all later operations re-check it.
        self._root_stat = self._safe_root()

    def _safe_root(self):
        if _reparse(self.root) or not self.root.is_dir():
            raise ValueError("Izolovaný pracovní prostor byl přesměrován.")
        resolved = self.root.resolve(strict=True)
        if resolved != self.root.absolute() or not resolved.is_dir():
            raise ValueError("Izolovaný pracovní prostor byl přesměrován.")
        identity = resolved.stat()
        return identity.st_dev, identity.st_ino

    def _result_path(self):
        if self._safe_root() != self._root_stat:
            raise ValueError("Izolovaný pracovní prostor byl po vytvoření přesměrován.")
        path = self.root / "result.md"
        # lexists catches a dangling link, unlike Path.exists().
        if os.path.lexists(path) and _reparse(path):
            raise ValueError("Cesta result.md byla přesměrována.")
        if path.parent.resolve(strict=True) != self.root.resolve(strict=True):
            raise ValueError("Cesta result.md byla přesměrována.")
        return path

    def read_context(self, section):
        if section in {"map", "documents", "workspaceDocuments"}:
            return self.context[section]
        raise ValueError("Čtení mimo schválený kontext není povoleno.")

    def write_result(self, content):
        if not isinstance(content, str) or not content.strip():
            raise ValueError("result.md musí být neprázdný.")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_RESULT_BYTES:
            raise ValueError("result.md překročil limit 64000 bajtů UTF-8.")
        path = self._result_path()
        # O_EXCL avoids replacing a link created between validation and write.
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if _reparse(path):
                raise ValueError("Cesta result.md byla přesměrována.") from None
            raise ValueError("result.md již existuje.") from None
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        # A post-write recheck prevents reporting an outside result after a swap.
        if _reparse(path) or self._safe_root() != self._root_stat:
            path.unlink(missing_ok=True)
            raise ValueError("Cesta result.md byla přesměrována.")
        data = path.read_bytes()
        return {"path": "result.md", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
