"""Uložení verze plátna na kopii dat: čas a velikost nového snímku. ZAPISUJE do kopie.

`uv run python tools/perf/bench_vsave.py <kopie> [--project P]`
"""
import sqlite3
import time
from pathlib import Path

from perf_common import parser, use_repo


def main():
    args = parser("Uložení verze plátna na kopii dat.").parse_args()
    use_repo()
    from backend.canvas.canvas_service import CanvasService
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    from backend.editor.canvas_versions.canvas_versions import CanvasVersions

    service = CanvasService(args.data)
    state = DesktopV3State(service)
    service.desktop_v3_state = state
    versions = CanvasVersions(service, state)
    started = time.perf_counter()
    listed = versions.list(args.project, args.workspace)
    print(f"list {time.perf_counter() - started:.2f}s verzí={len(listed['versions'])}")
    current = service.view(args.project, args.workspace)["digest"]
    started = time.perf_counter()
    versions.save({"project": args.project, "workspace": args.workspace, "digest": current,
                   "author": "perf", "expectedToken": listed["currentToken"]}, actor="human")
    print(f"save {time.perf_counter() - started:.2f}s")
    database = Path(args.data) / "projects" / args.project / "project.sqlite"
    db = sqlite3.connect(database)
    try:
        size = db.execute("SELECT length(snapshot) FROM canvas_versions"
                          " ORDER BY created_at DESC LIMIT 1").fetchone()
    finally:
        db.close()
    print("bajty snímku nové verze", size[0] if size else None)


if __name__ == "__main__":
    main()
