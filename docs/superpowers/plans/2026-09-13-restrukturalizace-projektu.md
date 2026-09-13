# Restrukturalizace projektu Opora Canvas – implementační plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nový čistý worktree `restructure/clean-core` obsahující jen kód, který používá náhled 8780, uspořádaný podle specu `docs/superpowers/specs/2026-09-13-restrukturalizace-projektu-design.md`.

**Architecture:** Přesun probíhá ve třech fázích, každá vlastní commit: (1) smazání balastu, (2) backend přes absolutní importy + mapovací tabulku, (3) frontend přes alias `@/` + mapovací tabulku. Přesuny dělají skripty v `tools/restructure/` (git mv + přepis importů), aby byly opakovatelné a přezkoumatelné. Chování aplikace se nemění.

**Tech Stack:** Git worktree, Python 3.12 (uv), FastAPI, pytest, ruff, Vite 5 + React + TypeScript (`tsc --noEmit`), Node 20.

**Pravidla pro celý plán:**
- Pracuje se výhradně v `C:/Users/Admin/opora-clean`. Nikdy v `opora-v3`, nikdy na mainu, nikdy nesahat na porty 8740, 8768, 8780.
- Každý commit končí řádkem `Co-Authored-By: WOZCODE <contact@withwoz.com>`.
- Ověřovací příkazy: `npx tsc --noEmit`, `npx vite build`, `uv run pytest -q`, `uv run ruff check backend`.
- Shell je Git Bash. Cesty s mezerou v uvozovkách.

---

## Task 0: Worktree

**Files:** žádné změny v kódu.

- [ ] **Step 1: Vytvořit worktree z main**

```bash
cd "P:/0. OSVC/8. Code/07. Aplikace/02.Opora-control-center/Opora-control-center-canvas"
git worktree add -b restructure/clean-core C:/Users/Admin/opora-clean 372bb3d
cd /c/Users/Admin/opora-clean && git status --short | wc -l
```
Expected: `0`

- [ ] **Step 2: Nainstalovat závislosti a ověřit výchozí stav**

```bash
cd /c/Users/Admin/opora-clean
npm ci
uv sync
npx tsc --noEmit && npx vite build && uv run pytest -q 2>&1 | tail -3
```
Expected: tsc bez chyb, build vytvoří `dist/`, pytest končí řádkem `N passed` (poznamenej N do `docs/superpowers/plans/baseline.txt`, použije se v Task 7).

```bash
uv run pytest -q 2>&1 | tail -1 > docs/superpowers/plans/baseline.txt
```

---

## Task 1: Smazání balastu

**Files:**
- Delete: viz seznam níže.

- [ ] **Step 1: Smazat laneové a důkazní soubory**

```bash
cd /c/Users/Admin/opora-clean
git rm -rq e2e e2e-clean-editor e2e-context-boundary e2e-document-task e2e-source-creation e2e-v3-panels e2e-v3-shell
git rm -rq evidence test-results graphify-out .opora
git rm -q playwright.*.config.ts playwright.config.ts
git rm -q verify-document-task-live-ui.cjs vite.desktop-v3.config.ts vite.workflow-drafts.config.ts
git rm -q scripts/bind_node_session.py scripts/inspect_runtime.py scripts/prepare_e2e.py scripts/production_snapshot.py scripts/run_node_session_lane.py scripts/serve_clean_editor_fixture.py scripts/serve_v3_shell_fixture.py scripts/__init__.py
git rm -q src/MapTools.tsx src/ProjectMap.tsx src/project-map.ts
```

- [ ] **Step 2: Přesunout skill do claude/skills a smazat zbytek .claude**

```bash
mkdir -p claude/skills
git mv .claude/skills/opora-control-center claude/skills/opora-control-center
git rm -rq .claude 2>/dev/null; rm -rf .claude
```

- [ ] **Step 3: Smazat testy, jejichž předmět zmizel**

```bash
git rm -q tests/test_production_snapshot.py
grep -ln "e2e\|scripts/serve_\|playwright" tests/*.py
```
Expected: každý vypsaný test otevři a ověř, zda testuje smazaný skript nebo e2e. Pokud ano, `git rm` ho. `tests/test_drawing_assets_build.py` a `tests/test_working_source_tree.py` ponech (Task 8 je opraví po přesunu `copy-drawing-assets.mjs`).

- [ ] **Step 4: Odstranit `test:e2e` z package.json a Playwright z devDependencies**

Modify `package.json`: smaž řádek `"test:e2e": "playwright test"` a řádek `"@playwright/test": ...` v `devDependencies`. Pak:

```bash
npm install
```

- [ ] **Step 5: Ověřit a commitnout**

```bash
npx tsc --noEmit && npx vite build >/dev/null && uv run pytest -q 2>&1 | tail -1
git add -A
git commit -q -F - <<'EOF'
chore: remove lane configs, e2e suites, evidence and dead map code

Keeps only what the 8780 preview uses. Spec: docs/superpowers/specs/2026-09-13-restrukturalizace-projektu-design.md

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```
Expected: tsc OK, pytest `N-1 passed` (minus smazané testy).

---

## Task 2: Backend – jeden zdroj pravdy pro cesty

**Files:**
- Create: `backend/paths.py`
- Modify: `backend/app.py:299`, `backend/build_identity.py:8-16`, `backend/coding_worker.py:9`, `backend/task_handoff_worker.py:9`, `backend/graphify_runtime.py:56`, `backend/map_refresh_archify.py:143,423`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_paths.py
from pathlib import Path
from backend.paths import REPO_ROOT, DIST_DIR, VENDOR_DIR

def test_repo_root_points_at_checkout_root():
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert DIST_DIR == REPO_ROOT / "dist"
    assert VENDOR_DIR == REPO_ROOT / "vendor"
```

```bash
uv run pytest tests/test_paths.py -q
```
Expected: FAIL `ModuleNotFoundError: backend.paths`

- [ ] **Step 2: Implementace**

```python
# backend/paths.py
"""Jediné místo, kde backend odvozuje kořen repozitáře. Při přesunu modulů se mění jen zde."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
VENDOR_DIR = REPO_ROOT / "vendor"
GRAPHIFY_VENV = REPO_ROOT / ".venv-graphify"
```

- [ ] **Step 3: Nahradit výpočty kořene**

V každém souboru nahraď uvedený výraz:

| Soubor | Původně | Nově |
|---|---|---|
| `backend/app.py:299` | `Path(__file__).resolve().parent.parent / "dist"` | `DIST_DIR` (+ `from .paths import DIST_DIR`) |
| `backend/build_identity.py:8` | `root = Path(__file__).resolve().parent.parent` | `root = REPO_ROOT` (+ import) |
| `backend/coding_worker.py:9` | `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` | `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` **ponechat zatím**, změní se v Task 4 na `parents[3]` |
| `backend/task_handoff_worker.py:9` | stejné | stejné jako výše |
| `backend/graphify_runtime.py:56` | `Path(__file__).resolve().parents[1] / '.venv-graphify' / (...)` | `GRAPHIFY_VENV / (...)` (+ import) |
| `backend/map_refresh_archify.py:143` | `Path(__file__).resolve().parents[1] / "vendor" / "archify" / "archify" / name` | `VENDOR_DIR / "archify" / "archify" / name` |
| `backend/map_refresh_archify.py:423` | `Path(__file__).resolve().parents[1]` | `REPO_ROOT` |

Workery nemohou importovat `backend.paths` před úpravou `sys.path`, proto zůstávají na `parents[...]`.

- [ ] **Step 4: Testy a commit**

```bash
uv run pytest -q 2>&1 | tail -1 && uv run ruff check backend
git add -A && git commit -q -F - <<'EOF'
refactor(backend): derive repo root from backend/paths.py

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```

---

## Task 3: Backend – absolutní importy

**Files:**
- Create: `tools/restructure/absolutize_backend_imports.py`
- Modify: všechny `backend/*.py`

- [ ] **Step 1: Skript**

```python
# tools/restructure/absolutize_backend_imports.py
"""Přepíše `from .mod import X` na `from backend.mod import X` ve všech backend/*.py."""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(r"^(\s*)from \.(\w+) import", re.M)
changed = 0
for path in sorted((ROOT / "backend").rglob("*.py")):
    text = path.read_text(encoding="utf-8")
    new = PATTERN.sub(r"\1from backend.\2 import", text)
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed += 1
print(f"rewritten files: {changed}")
```

- [ ] **Step 2: Spustit, ověřit, commit**

```bash
python tools/restructure/absolutize_backend_imports.py
grep -rn "^from \." backend/ | wc -l
uv run pytest -q 2>&1 | tail -1 && uv run ruff check backend
git add -A && git commit -q -F - <<'EOF'
refactor(backend): absolute imports before package split

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```
Expected: grep `0`, pytest stejný počet jako Task 2.

---

## Task 4: Backend – rozdělení do balíčků

**Files:**
- Create: `tools/restructure/move_backend.py`, `backend/*/__init__.py`
- Move: všech 48 modulů podle tabulky

**Mapovací tabulka (modul → balíček):**

```
app                     -> app/factory.py   (a backend/app/__init__.py re-exportuje create_app)
agent_routes            -> api
archify_routes          -> api
graphify_routes         -> api
context_routes          -> api
desktop_v3_routes       -> api
task_handoff_routes     -> api
service                 -> domain
graph                   -> domain/graph
project_hub             -> domain/project
planning_context        -> domain/project
wireframe_context       -> domain/project
node_text               -> domain/node
node_specs              -> domain/node
node_links              -> domain/node
node_journal            -> domain/node
node_sessions           -> domain/node
node_session_sources    -> domain/node
removals                -> domain/node
drawings                -> domain/node
context_packets         -> agents/packets
desktop_v3_packets      -> agents/packets
desktop_v3_state        -> agents/packets
coding_runs             -> agents/runs
coding_tools            -> agents/runs
coding_worker           -> agents/runs
coding_oracle           -> agents/runs
llm_runs                -> agents/runs
task_handoffs           -> agents/runs
task_handoff_tools      -> agents/runs
task_handoff_worker     -> agents/runs
external_agent_tasks    -> agents/runs
agent_sources           -> agents/sources
agent_bindings          -> agents/sources
agent_activity          -> agents/sources
agent_telemetry         -> agents/sources
agent_catalog           -> agents/sources
graphify_runtime        -> maps
graphify_worker         -> maps
map_artifacts           -> maps
map_refresh             -> maps
map_refresh_archify     -> maps
map_refresh_pipeline    -> maps
map_refresh_snapshot    -> maps
gitio                   -> integrations
workspace_sources       -> integrations
workspace_documents     -> integrations
build_identity          -> integrations
paths                   -> (zůstává backend/paths.py)
```

- [ ] **Step 1: Skript přesunu**

```python
# tools/restructure/move_backend.py
"""git mv backend modulů do balíčků + přepis `backend.<mod>` → `backend.<pkg>.<mod>` všude (backend, tests, tools)."""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = {
    "app": "app/factory",
    "agent_routes": "api", "archify_routes": "api", "graphify_routes": "api",
    "context_routes": "api", "desktop_v3_routes": "api", "task_handoff_routes": "api",
    "service": "domain", "graph": "domain/graph",
    "project_hub": "domain/project", "planning_context": "domain/project", "wireframe_context": "domain/project",
    "node_text": "domain/node", "node_specs": "domain/node", "node_links": "domain/node",
    "node_journal": "domain/node", "node_sessions": "domain/node", "node_session_sources": "domain/node",
    "removals": "domain/node", "drawings": "domain/node",
    "context_packets": "agents/packets", "desktop_v3_packets": "agents/packets", "desktop_v3_state": "agents/packets",
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

def dotted(mod: str) -> str:
    target = MAP[mod]
    if target.endswith("/factory"):
        return "backend." + target.replace("/", ".")
    return "backend." + target.replace("/", ".") + "." + mod

def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)

# 1) přesuny
for mod, target in MAP.items():
    src = ROOT / "backend" / f"{mod}.py"
    if target.endswith("/factory"):
        dst = ROOT / "backend" / "app" / "factory.py"
    else:
        dst = ROOT / "backend" / target / f"{mod}.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    git("mv", str(src.relative_to(ROOT)), str(dst.relative_to(ROOT)))

# 2) __init__.py pro každý balíček
for pkg in {"app", "api", "domain", "domain/graph", "domain/project", "domain/node", "agents", "agents/packets",
            "agents/runs", "agents/sources", "maps", "integrations"}:
    init = ROOT / "backend" / pkg / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
(ROOT / "backend" / "app" / "__init__.py").write_text(
    'from backend.app.factory import create_app\n\n__all__ = ["create_app"]\n', encoding="utf-8")

# 3) přepis importů: `backend.<mod>` → nová cesta (delší jména první, aby `node_sessions` nepřepsal `node_session_sources`)
files = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "node_modules" not in p.parts]
files += [ROOT / "pyproject.toml"]
for mod in sorted(MAP, key=len, reverse=True):
    pat = re.compile(rf"\bbackend\.{mod}\b(?!\w)")
    for path in files:
        text = path.read_text(encoding="utf-8")
        new = pat.sub(dotted(mod), text)
        if new != text:
            path.write_text(new, encoding="utf-8")
print("done")
```

- [ ] **Step 2: Spustit**

```bash
python tools/restructure/move_backend.py && git status --short | head
```

- [ ] **Step 3: Ruční opravy, které skript nezvládne**

1. `backend/app/__init__.py` už re-exportuje `create_app`, takže `uvicorn backend.app:create_app --factory` funguje beze změny.
2. `backend/agents/runs/coding_worker.py:9` a `backend/agents/runs/task_handoff_worker.py:9`: `parents[1]` → `parents[3]` (soubor je nyní o dvě úrovně hlouběji).
3. `from backend import desktop_v3_packets` (v jednom testu) → `from backend.agents.packets import desktop_v3_packets`; stejně `from backend import agent_sources, agent_routes` → `from backend.agents.sources import agent_sources` a `from backend.api import agent_routes`. Ověř: `grep -rn "^from backend import" tests backend`.
4. `Path(__file__).with_name("coding_worker.py")` a spol. zůstávají správné, protože worker leží ve stejném balíčku jako volající.
5. `backend/integrations/gitio.py:24` `Path(__file__).resolve().parent / "disabled-hooks"`: pokud `backend/disabled-hooks/` existuje v gitu, přesuň ho: `git mv backend/disabled-hooks backend/integrations/disabled-hooks`.

- [ ] **Step 4: Ověřit**

```bash
uv run ruff check backend && uv run pytest -q 2>&1 | tail -1
uv run python -c "from backend.app import create_app; print(type(create_app('.data/_smoke')).__name__)"
```
Expected: ruff čistý, pytest stejný počet jako Task 3, výpis `FastAPI`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -q -F - <<'EOF'
refactor(backend): split flat modules into app/api/domain/agents/maps/integrations

Mapping and script: tools/restructure/move_backend.py

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```

---

## Task 5: Frontend – alias `@/` a absolutní importy

**Files:**
- Modify: `tsconfig.json`, `vite.config.ts`
- Create: `tools/restructure/aliasize_frontend_imports.py`

- [ ] **Step 1: Alias v tsconfig a vite**

`tsconfig.json` → do `compilerOptions` přidat:
```json
"baseUrl": ".",
"paths": { "@/*": ["src/*"] }
```
`vite.config.ts` → celý soubor:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { proxy: { "/api": "http://127.0.0.1:8740" } },
});
```
(Zachovej všechny ostatní volby, které v původním `vite.config.ts` byly, například `build.rollupOptions`.)

- [ ] **Step 2: Skript relativní → alias**

```python
# tools/restructure/aliasize_frontend_imports.py
"""Přepíše relativní importy v src/**/*.{ts,tsx} na alias @/<cesta od src>."""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
IMP = re.compile(r"""(from\s*|import\s*|import\(\s*)(['"])(\.{1,2}/[^'"]+)\2""")

def to_alias(file: Path, spec: str) -> str:
    target = (file.parent / spec).resolve()
    rel = target.relative_to(SRC).as_posix()
    return f"@/{rel}"

for path in list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")):
    text = path.read_text(encoding="utf-8")
    new = IMP.sub(lambda m: f"{m.group(1)}{m.group(2)}{to_alias(path, m.group(3))}{m.group(2)}", text)
    if new != text:
        path.write_text(new, encoding="utf-8")
print("done")
```
CSS `@import` zůstává relativní (řeší Vite), ale v `src/` žádný není (ověř `grep -rn "@import" src`).

- [ ] **Step 3: Spustit a ověřit**

```bash
python tools/restructure/aliasize_frontend_imports.py
grep -rn "from ['\"]\.\{1,2\}/" src | wc -l
npx tsc --noEmit && npx vite build >/dev/null && echo BUILD_OK
git add -A && git commit -q -F - <<'EOF'
refactor(frontend): @/ alias and absolute imports before folder split

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```
Expected: grep `0`, `BUILD_OK`.

---

## Task 6: Frontend – přesun do `frontend/`

**Files:**
- Create: `tools/restructure/move_frontend.py`
- Move: `src/**` → `frontend/**`
- Modify: `index.html:24`, `tsconfig.json`, `vite.config.ts`

**Mapovací tabulka (soubor v src/ → složka ve frontend/):**

```
main.tsx, App.tsx, style.css, DesktopThemeControls.tsx, vite-env.d.ts        -> app
TopBar.tsx                                                                    -> layout/top-bar
ModeRail.tsx, EnvironmentSwitch.tsx                                           -> layout/mode-rail
ProjectLayout.tsx, project-layout.css, EditorWorkbench.tsx, desktop-workspaces.css -> layout/shell
Board.tsx, natural-canvas.css, LayerContext.tsx                               -> canvas
DrawingWorkspace.tsx, DrawingTools.tsx, drawing-state.ts, drawing.css         -> canvas/drawing
NodePanel.tsx                                                                 -> node-detail
NodeTextEditor.tsx, TextWorkspace.tsx, text-workspace.css, BlockOutline.tsx, block-commands.ts -> node-detail/content
NodeSpecEditor.tsx                                                            -> node-detail/assignment
NodeLinksPanel.tsx                                                            -> node-detail/links
NodeJournal.tsx                                                               -> node-detail/journal
NodeActivity.tsx                                                              -> node-detail/work
ProjectHome.tsx, project-home.css, ProjectWorkspace.tsx                       -> project-detail
ArchifyMap.tsx, archify-map.css, GraphifyMap.tsx, MapUpdateMenu.tsx, map-update-menu.css -> project-detail/maps
AgentContextMap.tsx, agent-context-map.css, WireframeInspector.tsx, wireframe-model.ts, SourceExplorer.tsx -> project-detail/inspector
AgentsWorkspace.tsx, agents.css, agent-types.ts, LiveRunDetail.tsx            -> agents
CodingPanel.tsx, PlanPanel.tsx, TaskHandoffPanel.tsx, ContextShelf.tsx, context-actions.tsx -> agents/panels
desktop-v3/ (celá složka)                                                     -> agents/desktop-v3
RemovalDialog.tsx                                                             -> components/removal-dialog
ScopeContext.tsx                                                              -> shared/contexts
use-pending-edits.ts                                                          -> shared/hooks
types.ts                                                                      -> shared/types
desktop-v3.css                                                                -> design
```

- [ ] **Step 1: Skript**

```python
# tools/restructure/move_frontend.py
"""git mv src → frontend podle MAP a přepis aliasů @/<stará> → @/<nová> ve všech ts/tsx/css/html."""
import re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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
    "SourceExplorer.tsx": "project-detail/inspector",
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

renames = {}  # stará alias cesta bez přípony → nová
for name, folder in MAP.items():
    src = Path("src") / name
    dst = Path("frontend") / folder / name
    (ROOT / dst).parent.mkdir(parents=True, exist_ok=True)
    git("mv", str(src), str(dst))
    renames[name] = f"{folder}/{name}"
for name, folder in DIRS.items():
    (ROOT / "frontend" / folder).parent.mkdir(parents=True, exist_ok=True)
    git("mv", f"src/{name}", f"frontend/{folder}")
    renames[name] = folder

leftover = [p for p in (ROOT / "src").rglob("*") if p.is_file()]
assert not leftover, f"unmapped files in src: {leftover}"

files = [p for p in (ROOT / "frontend").rglob("*") if p.suffix in (".ts", ".tsx", ".css")] + [ROOT / "index.html"]
# import "@/Foo" (bez přípony) i "@/style.css" (s příponou) i "@/desktop-v3" (složka)
for old in sorted(renames, key=len, reverse=True):
    stem = old.rsplit(".", 1)[0] if "." in old and not old.endswith(".d.ts") else old
    new = renames[old]
    new_stem = new.rsplit(".", 1)[0] if "." in new.rsplit("/", 1)[-1] else new
    pat = re.compile(rf"""(['"])@/{re.escape(stem)}(?=['"/])""")
    for path in files:
        text = path.read_text(encoding="utf-8")
        out = pat.sub(lambda m: f"{m.group(1)}@/{new_stem}", text)
        if out != text:
            path.write_text(out, encoding="utf-8")
print("done")
```

- [ ] **Step 2: Spustit**

```bash
python tools/restructure/move_frontend.py && rmdir src 2>/dev/null; git status --short | wc -l
```

- [ ] **Step 3: Přepnout kořen aliasu a entry**

- `tsconfig.json`: `"paths": { "@/*": ["frontend/*"] }`, a v `include` nahraď `"src"` za `"frontend"`.
- `vite.config.ts`: `new URL("./frontend", import.meta.url)`.
- `index.html:24`: `<script type="module" src="/frontend/app/main.tsx"></script>`.
- Uvnitř `frontend/agents/desktop-v3/*` byly relativní importy mezi soubory ve stejné složce převedeny na `@/desktop-v3/...` v Task 5; skript je přepsal na `@/agents/desktop-v3/...`. Ověř: `grep -rn "@/desktop-v3" frontend | wc -l` → `0`.

- [ ] **Step 4: Ověřit a commit**

```bash
npx tsc --noEmit && npx vite build >/dev/null && echo BUILD_OK
ls dist/assets/*.js | head -2
git add -A && git commit -q -F - <<'EOF'
refactor(frontend): move src/ into frontend/ by screen and responsibility

Mapping and script: tools/restructure/move_frontend.py

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```
Expected: `BUILD_OK`; při chybě tsc oprav importy ručně podle hlášky (cesta v hlášce ukáže, který alias se nepřepsal).

---

## Task 7: Testy vedle kódu

**Files:**
- Move: `tests/test_*.py` → `backend/<pkg>/tests/`
- Modify: `pyproject.toml`

**Mapovací tabulka (test → balíček):**

```
test_api, test_canvas, test_agents_app_integration, test_context_app_v2, test_responsiveness, test_v3_acceptance,
test_backend_review_guards, test_model_validation_parity, test_paths                  -> backend/app/tests
test_agent_activity, test_agent_bindings, test_agent_boundary_regressions, test_agent_sources,
test_agent_token_redaction, test_agent_transport_isolation                            -> backend/agents/sources/tests
test_archify_routes, test_graphify_routes, test_context_routes, test_planning_api    -> backend/api/tests
test_block_links, test_map_links, test_node_journal, test_node_sessions, test_node_specs, test_node_text,
test_drawings, test_removal_history, test_removals, test_graph_source_ref              -> backend/domain/node/tests
test_project_hub, test_project_hub_concurrency, test_workspace_goal, test_wireframe_context,
test_empty_workspace_source, test_snapshot                                             -> backend/domain/project/tests
test_coding_lifecycle, test_coding_runs, test_coding_sandbox, test_llm_integration_contract, test_llm_runs,
test_task_handoff_context_contract, test_task_handoff_long_paths, test_task_handoff_verification_deadline,
test_task_handoff_windows_boundary, test_task_handoffs, test_oporacc_process_source   -> backend/agents/runs/tests
test_context_packets, test_desktop_v3_packets, test_desktop_v3_prepare, test_desktop_v3_state -> backend/agents/packets/tests
test_map_refresh, test_map_refresh_archify                                             -> backend/maps/tests
test_sync, test_working_source_tree, test_workspace_documents, test_workspace_source_safety,
test_workspace_sources, test_build_identity, test_source_creation_user_contract        -> backend/integrations/tests
test_drawing_assets_build                                                              -> tools/tests
```

- [ ] **Step 1: Přesun**

```bash
cd /c/Users/Admin/opora-clean
mv_t() { mkdir -p "$2"; for t in "${@:3}"; do git mv "tests/$t.py" "$2/$t.py"; done; }
mv_t x backend/app/tests test_api test_canvas test_agents_app_integration test_context_app_v2 test_responsiveness test_v3_acceptance test_backend_review_guards test_model_validation_parity test_paths
mv_t x backend/agents/sources/tests test_agent_activity test_agent_bindings test_agent_boundary_regressions test_agent_sources test_agent_token_redaction test_agent_transport_isolation
mv_t x backend/api/tests test_archify_routes test_graphify_routes test_context_routes test_planning_api
mv_t x backend/domain/node/tests test_block_links test_map_links test_node_journal test_node_sessions test_node_specs test_node_text test_drawings test_removal_history test_removals test_graph_source_ref
mv_t x backend/domain/project/tests test_project_hub test_project_hub_concurrency test_workspace_goal test_wireframe_context test_empty_workspace_source test_snapshot
mv_t x backend/agents/runs/tests test_coding_lifecycle test_coding_runs test_coding_sandbox test_llm_integration_contract test_llm_runs test_task_handoff_context_contract test_task_handoff_long_paths test_task_handoff_verification_deadline test_task_handoff_windows_boundary test_task_handoffs test_oporacc_process_source
mv_t x backend/agents/packets/tests test_context_packets test_desktop_v3_packets test_desktop_v3_prepare test_desktop_v3_state
mv_t x backend/maps/tests test_map_refresh test_map_refresh_archify
mv_t x backend/integrations/tests test_sync test_working_source_tree test_workspace_documents test_workspace_source_safety test_workspace_sources test_build_identity test_source_creation_user_contract
mv_t x tools/tests test_drawing_assets_build
ls tests
```
Expected: `tests/` obsahuje jen `conftest.py` (pokud existuje) a `__pycache__`. Pokud `conftest.py` existuje, přesuň ho do `backend/conftest.py`. Testy, které Task 1 smazal, ve výpisu chybějí, to je v pořádku.

- [ ] **Step 2: pyproject**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["backend", "tools"]
```

- [ ] **Step 3: Opravit testy s pevnými cestami**

`test_drawing_assets_build.py` a `test_working_source_tree.py` odkazují na `scripts/copy-drawing-assets.mjs` nebo `src/`. Task 8 přesune skript do `tools/copy-drawing-assets.mjs`; zde nahraď v testech `scripts/` → `tools/` a `src/` → `frontend/`. Testy, které počítají kořen jako `Path(__file__).parents[1]`, přepiš na `from backend.paths import REPO_ROOT`.

- [ ] **Step 4: Ověřit a commit**

```bash
git rm -rq tests 2>/dev/null; rm -rf tests
uv run pytest -q 2>&1 | tail -1; cat docs/superpowers/plans/baseline.txt
git add -A && git commit -q -F - <<'EOF'
refactor(tests): colocate pytest suites with the packages they cover

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```
Expected: počet passed = baseline minus testy smazané v Task 1.

---

## Task 8: Skelet nových složek, docs, tools

**Files:**
- Move: `scripts/copy-drawing-assets.mjs` → `tools/copy-drawing-assets.mjs`; `PRODUCT-CONTRACT.md`, `START-HERE.md` → `docs/`
- Create: README.md ve složkách, `docs/pravidla-struktury.md`, `tools/serve-preview.py`
- Modify: `package.json` (build skript)

- [ ] **Step 1: Přesuny**

```bash
git mv scripts/copy-drawing-assets.mjs tools/copy-drawing-assets.mjs && rmdir scripts
git mv PRODUCT-CONTRACT.md docs/PRODUCT-CONTRACT.md
git mv START-HERE.md docs/START-HERE.md
```
`package.json` → `"build": "tsc --noEmit && vite build && node tools/copy-drawing-assets.mjs"`.

- [ ] **Step 2: Skeletové složky s README**

Vytvoř soubory s uvedeným obsahem (jedna věta, česky):

| Soubor | Obsah |
|---|---|
| `frontend/layout/left-bar/README.md` | Paleta komponent, funkcí a metod k vložení do projektu, sektoru nebo uzlu. |
| `frontend/layout/right-bar/README.md` | Ovládání Claude Code a agentů: hooky, commands, běhy, stav. |
| `frontend/canvas/sector-card/README.md` | Karta sektoru na plátně. |
| `frontend/canvas/node-card/README.md` | Karta uzlu na plátně. |
| `frontend/node-detail/packet/README.md` | Náhled a export podkladů pro agenta (rozsah node / subtree / lineage). |
| `frontend/sector-detail/README.md` | Detail sektoru: stejná šablona jako node-detail. |
| `frontend/library/README.md` | UI knihovny předloh: procházení, vložení, checklist. |
| `frontend/components/README.md` | Znovupoužitelné komponenty bez domény; každá ve vlastní složce s kódem, testem a css. |
| `frontend/shared/api/README.md` | Jediný klient nad backend API a typy odpovědí. |
| `frontend/design/README.md` | Globální design tokens, témata, fonty, obrázky, ikony. |
| `backend/domain/sector/README.md` | Doména sektoru. |
| `backend/agents/control/README.md` | MCP server pro agenty: get_tree, get_node, claim_task, report_result, list_library, record_lesson. |
| `backend/library/README.md` | Načítání a verze předloh, checklisty, zpětná vazba. |
| `backend/claude_code/README.md` | Generování a řízení hooků, commands a skills z aplikace. |
| `database/schema/README.md` | SQL schéma a migrace po tabulkách. |
| `database/repositories/README.md` | Přístup k datům vyčleněný ze service.py. |
| `database/seeds/README.md` | Výchozí obsah knihovny předloh. |
| `library/components/README.md` | Předlohy komponent: blueprint.md + checklist.yaml + šablona kódu. |
| `library/functions/README.md` | Předlohy funkcí. |
| `library/methods/README.md` | Předlohy metod. |
| `library/lessons/README.md` | Zaznamenané chyby a poučení, ze kterých se aktualizují předlohy. |
| `claude/hooks/README.md` | Hooky Claude Code řízené aplikací. |
| `claude/commands/README.md` | Commands Claude Code řízené aplikací. |
| `shared/README.md` | JSON schémata kontraktů mezi frontendem, backendem a agenty. |

- [ ] **Step 3: docs/pravidla-struktury.md**

Zkopíruj §4 „Pravidla umístění nového souboru" a cílový strom ze specu do `docs/pravidla-struktury.md` a doplň úvodní větu: „Tento dokument je autorita pro umístění nového souboru. Při pochybnosti se řídí tímto pořadím otázek."

- [ ] **Step 4: tools/serve-preview.py**

```python
"""Spustí backend + statický build z tohoto worktree nad zadanou kopií dat. Nikdy nesahá na 8740/8768/8780."""
import argparse, os, socket, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--data", required=True, help="cesta ke kopii dat (adresář s canvas.sqlite)")
args = parser.parse_args()
assert args.port not in (8740, 8768, 8780), "chráněné porty"
with socket.socket() as s:
    assert s.connect_ex(("127.0.0.1", args.port)) != 0, "port je obsazený"
os.environ["OPORA_CANVAS_PORT"] = str(args.port)
os.environ["OPORA_CANVAS_DATA"] = args.data
from backend.app import create_app
import uvicorn
uvicorn.run(create_app(Path(args.data)), host="127.0.0.1", port=args.port)
```

- [ ] **Step 5: Ověřit a commit**

```bash
npm run build >/dev/null && uv run pytest -q 2>&1 | tail -1 && uv run ruff check backend tools
git add -A && git commit -q -F - <<'EOF'
chore: scaffold target folders with READMEs, structure rules and preview tool

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```

---

## Task 9: Ověření nad kopií dat

- [ ] **Step 1: Kopie dat 8780 a start na volném portu**

```bash
mkdir -p /c/Users/Admin/opora-clean/.data/verify
cp /c/Users/Admin/opora-v3/.data/v3-preview-copy/canvas.sqlite /c/Users/Admin/opora-clean/.data/verify/canvas.sqlite
cd /c/Users/Admin/opora-clean && uv run python tools/serve-preview.py --port 8790 --data .data/verify &
sleep 4; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8790/
```
Expected: `200`

- [ ] **Step 2: Kontrola API nad uzlem ze zadání**

```bash
P=4b38182c5b04482bb00e0f3d3ae55656; N=3aa5bd26-429a-444b-b9aa-b7606dbfb3ae
curl -s "http://127.0.0.1:8790/api/node-text?project=$P&workspace=draft&node=$N" | head -c 120; echo
curl -s "http://127.0.0.1:8790/api/view?project=$P&workspace=draft" | python -c "import sys,json; g=json.load(sys.stdin)['graph']; print(len(g['nodes']),'nodes')"
curl -s http://127.0.0.1:8790/api/health
```
Expected: text začíná `{"revision":39,"text":"- Správně rozdělit kód`, `7 nodes`, health `ok`.

- [ ] **Step 3: Kontrola v prohlížeči**

Otevřít `http://127.0.0.1:8790/?project=4b38182c5b04482bb00e0f3d3ae55656&workspace=draft&screen=canvas&environment=editor&node=3aa5bd26-429a-444b-b9aa-b7606dbfb3ae`. Musí být vidět: plátno s uzlem a sektorem, pravý panel UZEL · DETAIL s taby Obsah, Zadání, Práce, tlačítko Podklady pro agenta, přepnutí světlo/tma bez chyb v konzoli. Pořídit screenshot do `docs/superpowers/plans/2026-09-13-verify-8790.png`.

- [ ] **Step 4: Kořen worktree odpovídá specu §8**

```bash
ls -p /c/Users/Admin/opora-clean | grep -v "^node_modules/\|^dist/\|^\.data/\|^\.venv/"
```
Expected přesně: `backend/ claude/ database/ docs/ frontend/ index.html library/ package.json package-lock.json pyproject.toml shared/ tools/ tsconfig.json uv.lock vendor/ vite.config.ts README.md .gitignore`. Cokoli navíc smazat nebo zařadit; README.md v kořeni přepsat na 10 řádků: co to je, jak spustit (`npm run build`, `uv run python tools/serve-preview.py`), odkaz na `docs/pravidla-struktury.md`.

- [ ] **Step 5: Zastavit ověřovací server a commit**

```bash
kill %1
git add -A && git commit -q -F - <<'EOF'
docs: verification evidence for restructured worktree

Co-Authored-By: WOZCODE <contact@withwoz.com>
EOF
```

---

## Task 10: Přepnutí 8780 (jen po výslovném potvrzení uživatele)

- [ ] **Step 1: Zeptat se uživatele** – „Nový worktree prošel ověřením na 8790. Mám přepnout náhled 8780 na `C:/Users/Admin/opora-clean`? Proces 58808 se ukončí a nastartuje znovu z nového worktree nad stejnou kopií dat `.data/v3-preview-copy`."

- [ ] **Step 2: Po „ano"**: ukončit PID 58808, spustit `uv run python tools/serve-preview.py --port 8780 --data C:/Users/Admin/opora-v3/.data/v3-preview-copy` z `opora-clean` (assert na chráněné porty v tools/serve-preview.py pro tento účel povolí 8780 pouze s přepínačem `--allow-8780`; přidat ho do argparse: `parser.add_argument("--allow-8780", action="store_true")` a podmínku upravit na `assert args.port not in (8740, 8768) and (args.port != 8780 or args.allow_8780)`). Zaktualizovat paměť `opora-canvas-preview-port-8780.md`.

---

## Self-review

- Spec §3 mazání: Task 1. Spec §4 strom: Task 4, 6, 8. Spec §5 mapování: Task 4, 6. Spec §6 MCP: jen README v Task 8 (dle ne-cílů). Spec §7 postup: Task 0, 9, 10. Spec §8 podmínky dokončení: Task 9 Step 4 a Task 8 Step 3.
- Názvy: `backend/paths.py` (`REPO_ROOT`, `DIST_DIR`, `VENDOR_DIR`, `GRAPHIFY_VENV`) používané v Task 2, 7. `tools/serve-preview.py` v Task 8, 9, 10. Alias `@/` v Task 5, 6.
- Riziko: skript v Task 6 přepisuje aliasy podle názvu bez přípony; `types.ts` → `@/types` koliduje s `@/desktop-v3/types` jen kdyby cesta začínala `@/types`, což regex ošetřuje kotvou `@/`. `App` vs `AppShell` neexistuje. Pokud tsc po Task 6 hlásí chyby, jsou to zbylé aliasy; opravit ručně.
