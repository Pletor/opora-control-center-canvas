import json
import os
import subprocess
from pathlib import Path

from backend.service import CanvasService

root = Path(os.environ["OPORA_CANVAS_DATA"]).resolve()
upstream = root / "fixture-upstream"
upstream.mkdir(parents=True)


def git(*args):
    return subprocess.check_output(["git", "-C", str(upstream), *args], text=True).strip()


git("init", "-b", "main")
git("config", "user.name", "Canvas fixture")
git("config", "user.email", "fixture@example.invalid")
graph = {
    "nodes": [
        {
            "id": "sector1",
            "parentId": None,
            "kind": "sector",
            "name": "Fixture sector",
            "purpose": "Original main purpose",
            "x": 0,
            "y": 0,
        }
    ],
    "edges": [],
}
(upstream / "opora-canvas.json").write_text(json.dumps(graph), encoding="utf-8")
git("add", ".")
git("commit", "-m", "Fixture only")
service = CanvasService(root)
repo = root / "projects" / "fixture" / "main"
repo.parent.mkdir(parents=True)
subprocess.run(["git", "clone", str(upstream), str(repo)], check=True, capture_output=True)
service.register_repository("fixture", "E2E fixture", str(repo), str(upstream), "main")
service.create_workspace("fixture", "sector1", "Agent A")
service.create_workspace("fixture", "sector1", "Agent B")
service.close()
