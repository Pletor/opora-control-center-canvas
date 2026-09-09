import hashlib
from pathlib import Path

from .gitio import git


def build_identity(data_root):
    root = Path(__file__).resolve().parent.parent
    sources = sorted([*root.joinpath("backend").glob("*.py"), *root.joinpath("src").glob("*")])
    digest = hashlib.sha256()
    for path in sources:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    index = root / "dist" / "index.html"
    return {"product": "Opora Canvas", "commit": git(root, "rev-parse", "HEAD"), "sourceSha256": digest.hexdigest(), "frontendIndexSha256": hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else None, "runtimeRoot": str(root), "dataRoot": str(Path(data_root).resolve()), "features": ["project-home", "saved-wireframe-context", "proposal-only-hermes", "fractal-node-text", "hermes-isolated-addition-oracle"], "codingScope": "calculator.py in server-created isolated Git workspaces; immutable Docker oracle only"}
