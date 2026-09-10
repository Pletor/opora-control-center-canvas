# OPUS lane handoff — canvas-first desktop SHELL / THEMES

Baseline bf8a1767ae098433dd6f5ee61a08602d8713b193 · branch feat/desktop-v3-opus · commit: the lane commit directly on top of bf8a176 (see `git log -1`).
Design source verified: sha256 541cb172…8bce (treated as untrusted design data; no demo data copied).

## OWNED / CHANGED PATHS
- src/App.tsx — v3 shell: `desktop-v3` class, compact grouped Editor toolbar (Pohled · Tvorba · Panely), hideable + persisted inspector (`opora:desktop-inspector:v1`), one primary `Podklady pro agenta`, `AI nástroje` kept as advanced entry, drawing/map tools move to toolbar when inspector hidden, `DesktopV3Slots` render-prop slots (default null).
- src/EditorWorkbench.tsx — pane `packet` (primary) + nav `Pokročilé nástroje` (Kontext, LLM návrh, Coding, Dokumentační úkol). `packet` prop = AgentPacketPanel slot; without it the existing real context-packet builder serves the primary entry (no stub).
- src/ProjectWorkspace.tsx — grouped compact toolbar; `memory` prop (ProjectMemoryPanel slot); `Cesta / Paměť projektu` toggle only appears when the slot is wired.
- src/DesktopThemeControls.tsx (new) — appearance store (`opora:desktop-theme:v1`), `useDesktopAppearance`, one quiet `Vzhled` topbar button → Světlý/Tmavý + Kompaktní/Normální/Vzdušná; cross-tab sync via storage event.
- src/desktop-v3.css (new) — light/dark tokens (OPORA teal accent, gold brand/unresolved/warn, natural neutrals), density tokens, canvas-first grid, light overrides for hard-coded dark colors (blocks, menus, map cards, agent badges, drawing/wireframe, modals, React Flow controls), focus-visible, reduced-motion.
- index.html — inline pre-render bootstrap sets `data-theme`/`data-density`/color-scheme (no first flash).
- Theme-only one-line edits OUTSIDE the explicit Opus list (not Sonnet/Fable paths): src/Board.tsx and src/ProjectMap.tsx (`colorMode` from theme, grid dots `var(--canvas-dot)`, map strokes/minimap), src/DrawingWorkspace.tsx (Excalidraw `theme` from appearance instead of hard-coded dark). Coordinator please acknowledge.
- Tests/fixture: e2e-v3-shell/shell.spec.ts, playwright.v3-shell.config.ts (port 8783, temp data, own dist `.data/v3-shell-dist`), scripts/serve_v3_shell_fixture.py. Evidence logs: evidence/opus/*.log.
- NOT changed: EnvironmentSwitch.tsx (compacted via CSS only), desktop-workspaces.css, any src/desktop-v3/*, backend, package manifests/lockfiles, CONTRACT.md.

## MOUNT INSTRUCTIONS (coordinator, after Sonnet merge) — src/main.tsx
```tsx
import { ProjectMemoryPanel, NodeWorkflowPanel, AgentPacketPanel, LiveWorkspacePanel } from "./desktop-v3";
<App v3={{
  projectMemory: (p) => <ProjectMemoryPanel {...p} />,      // {project,workspace,path}  → Projekt › Paměť projektu
  nodeWorkflow: (p) => <NodeWorkflowPanel {...p} />,        // {project,workspace,nodeId} → Inspektor pod NodePanel
  agentPacket: (p) => <AgentPacketPanel {...p} />,          // {project,workspace,nodeId,path,references,note} → Podklady pro agenta
  liveWorkspace: (p) => <LiveWorkspacePanel {...p} />,      // {project,workspace,nodeId?} → Live Run › Přehled a tickety (Dohled běhů = původní AgentsWorkspace)
}} />
```
Slot prop shapes match the CONTRACT export signatures exactly; `tsc --noEmit` checks them once wired.

## RED / GREEN
- RED (baseline src + new spec): `npx vite build --outDir .data/v3-shell-dist` exit 0; `npx playwright test -c playwright.v3-shell.config.ts --project v3-shell` exit 1 — 6 failed, 1 passed (the selection-retention test already held on baseline; kept as regression guard). Log: evidence/opus/red-e2e.log.
- GREEN: `npx tsc --noEmit` exit 0; `npx vite build --outDir .data/v3-shell-dist --emptyOutDir` exit 0; `npx playwright test -c playwright.v3-shell.config.ts` exit 0 — 10 passed (7 v3-shell + 3 e2e-clean-editor regression on the same build). Logs: evidence/opus/green-*.log.

## VERIFIED BEHAVIOR (by the tests above)
Theme toggle light/dark on topbar, canvas area, inspector; persisted across reload; `data-theme` already set when <body> is inserted (no flash); Excalidraw follows theme (`theme--dark` toggles); density persisted; at 1280/1440/1920 canvas ≥50% with shelf+inspector, ≥75% with inspector hidden, hidden state survives reload, toolbar buttons stay within viewport; exactly one `Podklady pro agenta` (primary), no competing `Kontextový paket` toolbar button, real `Sestavit paket` builder reachable, advanced LLM návrh/Coding/Dokumentační úkol reachable, `AI nástroje` reopens; Projekt/Editor/Live keep selection and Editor mode.

## LIMITATIONS / NOT DONE
- Slots not exercised end-to-end (Sonnet files absent in this lane); only type-level contract.
- Not run here: legacy e2e/ suite, e2e-document-task (its selectors `AI nástroje`, dock `Kontext`, `Dokumentační úkol`, `Uzel paketu`, `Sestavit paket` were preserved but not executed), e2e-source-creation, backend pytest.
- Contrast ratios chosen for WCAG AA but not measured with a tool; no screenshot QA. Parent browser QA required.
- Default theme follows OS `prefers-color-scheme` when no stored choice; dark accent retuned from mint #a5d7b7 to teal #8fcfc4.
- Light mode override audit covered the CSS files listed above; inline colors in other components (e.g. CodingPanel/PlanPanel/Wireframe preview item borders, drawing.css header border) may still be dark-tuned.
- Density changes spacing/font tokens only; no per-component airy/compact tuning beyond toolbar.
- No live deployment; no servers other than the isolated 8783 fixture (started/stopped by Playwright).
