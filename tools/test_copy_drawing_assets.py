import json
import shutil
import subprocess

import pytest

from backend.paths import REPO_ROOT


@pytest.mark.parametrize("dependency_location", ["local", "hoisted"])
def test_drawing_fonts_resolve_installed_package_in_worktree(tmp_path, dependency_location):
    """Sestavení najde balíček lokálně i v nadřazeném node_modules."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js je nutný pro skutečné spuštění asset skriptu.")
    repository = tmp_path / "repo with spaces"
    workspace = repository / ".worktrees" / "editor"
    scripts = workspace / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(
        REPO_ROOT / "tools" / "copy-drawing-assets.mjs",
        scripts / "copy-drawing-assets.mjs",
    )
    dependency_root = workspace if dependency_location == "local" else repository
    package = dependency_root / "node_modules" / "@excalidraw" / "excalidraw"
    fonts = package / "dist" / "prod" / "fonts" / "FixtureFont"
    fonts.mkdir(parents=True)
    (fonts / "fixture.woff2").write_bytes(b"fixture font bytes")
    # package.json záměrně není exportován, stejně jako u reálného balíčku.
    (package / "package.json").write_text(
        json.dumps({
            "name": "@excalidraw/excalidraw",
            "type": "module",
            "exports": {".": {"default": "./dist/prod/index.js"}},
        }),
        encoding="utf-8",
    )
    (package / "dist" / "prod" / "index.js").write_text(
        'throw new Error("Asset copying must not execute the package");',
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(scripts / "copy-drawing-assets.mjs")],
        cwd=workspace,
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    copied = workspace / "dist" / "drawing-assets" / "fonts" / "FixtureFont" / "fixture.woff2"
    assert copied.read_bytes() == b"fixture font bytes"
    assert (fonts / "fixture.woff2").read_bytes() == b"fixture font bytes"
