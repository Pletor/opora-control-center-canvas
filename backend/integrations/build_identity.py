import hashlib
import os
from pathlib import Path

from backend.integrations.gitio import git
from backend.paths import REPO_ROOT


SOURCE_SUFFIXES = {
    "backend": {".py", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".sql"},
    "frontend": {".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json", ".yaml", ".yml"},
    "database": {".py", ".sql", ".json", ".yaml", ".yml"},
    "library": {".json", ".yaml", ".yml", ".md"},
    "shared": {".json"},
}
EXCLUDED_SOURCE_DIRS = {".cache", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "cache", "dist", "generated", "node_modules"}


def _is_link_or_junction(path):
    return path.is_symlink() or getattr(os.path, "isjunction", lambda _: False)(path)


def _source_files(root):
    sources = []
    for source_root, suffixes in SOURCE_SUFFIXES.items():
        directory = root / source_root
        if not directory.is_dir() or _is_link_or_junction(directory):
            continue
        for current, directories, filenames in os.walk(directory, followlinks=False):
            current_path = Path(current)
            directories[:] = [
                name
                for name in directories
                if name not in EXCLUDED_SOURCE_DIRS and not _is_link_or_junction(current_path / name)
            ]
            for name in filenames:
                path = current_path / name
                if path.suffix.lower() not in suffixes or _is_link_or_junction(path):
                    continue
                try:
                    path.resolve().relative_to(root)
                except ValueError:
                    continue
                if path.is_file():
                    sources.append(path)
    return sorted(sources, key=lambda path: path.relative_to(root).as_posix())


def build_identity(data_root):
    root = REPO_ROOT
    digest = hashlib.sha256()
    for path in _source_files(root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    index = root / "dist" / "index.html"
    return {"product": "Opora Canvas", "commit": git(root, "rev-parse", "HEAD"), "sourceSha256": digest.hexdigest(), "frontendIndexSha256": hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else None, "runtimeRoot": str(root), "dataRoot": str(Path(data_root).resolve()), "features": ["project-home", "saved-wireframe-context", "fractal-node-text"]}
