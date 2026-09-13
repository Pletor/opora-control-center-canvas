"""git mv backend modulů do balíčků + přepis `backend.<mod>` → `backend.<pkg>.<mod>` všude (backend, tests, tools)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = {
    "app": "app/factory",
    "agent_routes": "api", "archify_routes": "api", "graphify_routes": "api",
    "context_routes": "api", "desktop_v3_routes": "api", "task_handoff_routes": "api",
    "service": "domain", "graph": "domain/graph",
    "project_hub": "domain/project", "wireframe_context": "domain/project",
    "node_text": "domain/node", "node_specs": "domain/node", "node_links": "domain/node",
    "node_journal": "domain/node", "node_sessions": "domain/node", "node_session_sources": "domain/node",
    "removals": "domain/node", "drawings": "domain/node",
    "context_packets": "agents/packets", "desktop_v3_packets": "agents/packets", "desktop_v3_state": "agents/packets",
    "planning_context": "agents/packets",
    "coding_runs": "agents/runs", "coding_tools": "agents/runs", "coding_worker": "agents/runs",
    "coding_oracle": "agents/runs", "llm_runs": "agents/runs", "task_handoffs": "agents/runs",
    "task_handoff_tools": "agents/runs", "task_handoff_worker": "agents/runs", "external_agent_tasks": "agents/runs",
    "agent_sources": "agents/sources", "agent_bindings": "agents/sources", "agent_activity": "agents/sources",
    "agent_telemetry": "agents/sources", "agent_catalog": "agents/sources",
    "graphify_runtime": "maps", "graphify_worker": "maps", "map_artifacts": "maps", "map_refresh": "maps",
    "map_refresh_archify": "maps", "map_refresh_pipeline": "maps", "map_refresh_snapshot": "maps",
    "gitio": "integrations", "workspace_sources": "integrations", "workspace_documents": "integrations",
    "build_identity": "integrations",
}
PACKAGES = ["app", "api", "domain", "domain/graph", "domain/project", "domain/node", "agents", "agents/packets",
            "agents/runs", "agents/sources", "maps", "integrations"]


def dotted(mod: str) -> str:
    target = MAP[mod]
    if target.endswith("/factory"):
        return "backend." + target.replace("/", ".")
    return "backend." + target.replace("/", ".") + "." + mod


def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)


assert not (ROOT / "backend" / "app" / "__init__.py").exists(), "backend už je rozdělený; skript je jednorázový"

# 1) přesuny
for mod, target in MAP.items():
    src = Path("backend") / f"{mod}.py"
    dst = Path("backend") / "app" / "factory.py" if target.endswith("/factory") else Path("backend") / target / f"{mod}.py"
    (ROOT / dst).parent.mkdir(parents=True, exist_ok=True)
    git("mv", str(src), str(dst))

# 2) přepis importů: delší jména první, aby `node_sessions` nepřepsal `node_session_sources`
SKIP_DIRS = {".venv", "node_modules", "vendor", ".git", "dist", "__pycache__"}
SELF = Path(__file__).resolve()  # tento skript obsahuje literál `backend.app.factory`, nesmí přepsat sám sebe
files = [p for p in ROOT.rglob("*.py") if not SKIP_DIRS & set(p.parts) and p.resolve() != SELF]
for mod in sorted(MAP, key=len, reverse=True):
    pat = re.compile(rf"\bbackend\.{re.escape(mod)}\b(?!\w)")
    for path in files:
        data = path.read_bytes().decode("utf-8")
        new = pat.sub(dotted(mod), data)
        if new != data:
            path.write_bytes(new.encode("utf-8"))

# 3) __init__.py pro balíčky — AŽ PO přepisu, jinak by se re-export v app/__init__.py sám přepsal
for pkg in PACKAGES:
    init = ROOT / "backend" / pkg / "__init__.py"
    if not init.exists():
        init.write_bytes(b"")
(ROOT / "backend" / "app" / "__init__.py").write_bytes(
    b'from backend.app.factory import create_app\n\n__all__ = ["create_app"]\n')
print("done")
