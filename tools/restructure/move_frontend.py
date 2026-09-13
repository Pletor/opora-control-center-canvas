# tools/restructure/move_frontend.py
"""git mv src → frontend podle MAP a přepis aliasů @/<stará> → @/<nová> ve všech ts/tsx/css/html. Jednorázový."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
assert (ROOT / "src").is_dir() and not (ROOT / "frontend").exists(), "src/ už je přesunutý; skript je jednorázový"

MAP = {
    "main.tsx": "app", "App.tsx": "app", "style.css": "app", "DesktopThemeControls.tsx": "app", "vite-env.d.ts": "app",
    "TopBar.tsx": "layout/top-bar",
    "ModeRail.tsx": "layout/mode-rail", "EnvironmentSwitch.tsx": "layout/mode-rail",
    "ProjectLayout.tsx": "layout/shell", "project-layout.css": "layout/shell",
    "EditorWorkbench.tsx": "layout/shell", "desktop-workspaces.css": "layout/shell",
    "Board.tsx": "canvas", "natural-canvas.css": "canvas", "LayerContext.tsx": "canvas",
    "DrawingWorkspace.tsx": "canvas/drawing", "DrawingTools.tsx": "canvas/drawing",
    "drawing-state.ts": "canvas/drawing", "drawing.css": "canvas/drawing",
    "NodePanel.tsx": "node-detail",
    "NodeTextEditor.tsx": "node-detail/content", "TextWorkspace.tsx": "node-detail/content",
    "text-workspace.css": "node-detail/content", "BlockOutline.tsx": "node-detail/content", "block-commands.ts": "node-detail/content",
    "NodeSpecEditor.tsx": "node-detail/assignment",
    "NodeLinksPanel.tsx": "node-detail/links",
    "NodeJournal.tsx": "node-detail/journal",
    "NodeActivity.tsx": "node-detail/work",
    "ProjectHome.tsx": "project-detail", "project-home.css": "project-detail", "ProjectWorkspace.tsx": "project-detail",
    "ArchifyMap.tsx": "project-detail/maps", "archify-map.css": "project-detail/maps", "GraphifyMap.tsx": "project-detail/maps",
    "MapUpdateMenu.tsx": "project-detail/maps", "map-update-menu.css": "project-detail/maps",
    "AgentContextMap.tsx": "project-detail/inspector", "agent-context-map.css": "project-detail/inspector",
    "WireframeInspector.tsx": "project-detail/inspector", "wireframe-model.ts": "project-detail/inspector",
    "WireframePreview.tsx": "project-detail/inspector", "WireframeTools.tsx": "project-detail/inspector",
    "SourceExplorer.tsx": "project-detail/inspector",
    "WorkspaceBoundary.tsx": "project-detail/workspace", "WorkspaceDocumentEditor.tsx": "project-detail/workspace",
    "workspace-modes.css": "project-detail/workspace", "workspace-selection.ts": "project-detail/workspace",
    "workspace-settings.ts": "project-detail/workspace", "WorkspaceSettings.tsx": "project-detail/workspace",
    "AgentsWorkspace.tsx": "agents", "agents.css": "agents", "agent-types.ts": "agents", "LiveRunDetail.tsx": "agents",
    "CodingPanel.tsx": "agents/panels", "PlanPanel.tsx": "agents/panels", "TaskHandoffPanel.tsx": "agents/panels",
    "ContextShelf.tsx": "agents/panels", "context-actions.tsx": "agents/panels",
    "RemovalDialog.tsx": "components/removal-dialog",
    "ScopeContext.tsx": "shared/contexts", "use-pending-edits.ts": "shared/hooks", "types.ts": "shared/types",
    "desktop-v3.css": "design",
}
DIRS = {"desktop-v3": "agents/desktop-v3"}

def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)

renames: dict[str, str] = {}   # stará alias cesta (bez "@/") → nová alias cesta (bez "@/")
for name, folder in MAP.items():
    dst = ROOT / "frontend" / folder / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    git("mv", f"src/{name}", f"frontend/{folder}/{name}")
    renames[name] = f"{folder}/{name}"
for name, folder in DIRS.items():
    (ROOT / "frontend" / folder).parent.mkdir(parents=True, exist_ok=True)
    git("mv", f"src/{name}", f"frontend/{folder}")
    renames[name] = folder

leftover = [p for p in (ROOT / "src").rglob("*") if p.is_file()]
assert not leftover, f"unmapped files in src: {leftover}"

def alias_key(path_no_prefix: str) -> str:
    """Jak se soubor objevuje v importu: .ts/.tsx bez přípony, .css a .d.ts s příponou, složka beze změny."""
    if path_no_prefix.endswith((".d.ts", ".css")):
        return path_no_prefix
    if path_no_prefix.endswith((".ts", ".tsx")):
        return path_no_prefix.rsplit(".", 1)[0]
    return path_no_prefix

files = [p for p in (ROOT / "frontend").rglob("*") if p.suffix in (".ts", ".tsx", ".css")] + [ROOT / "index.html"]
for old in sorted(renames, key=len, reverse=True):
    old_key, new_key = alias_key(old), alias_key(renames[old])
    # `@/desktop-v3` i `@/desktop-v3/api`; ale `@/types` nesmí chytit `@/types-foo` ani `@/desktop-v3/types`
    pat = re.compile(rf"""(['"])@/{re.escape(old_key)}(?=['"/])""")
    for path in files:
        text = path.read_bytes().decode("utf-8")
        out = pat.sub(lambda m, new_key=new_key: f"{m.group(1)}@/{new_key}", text)
        if out != text:
            path.write_bytes(out.encode("utf-8"))
print("done")
