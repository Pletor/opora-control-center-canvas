import { useEffect, useRef, useState, lazy, Suspense, type ReactNode } from "react";
import Board from "@/Board";
import ProjectHome from "@/ProjectHome";
import TextWorkspace from "@/TextWorkspace";
import { AgentTaskNotice, emitAgentTask, type AgentTaskRequest } from "@/context-actions";
import PlanPanel from "@/PlanPanel";
import TopBar from "@/TopBar";
import ModeRail from "@/ModeRail";
import EnvironmentSwitch, { type Environment } from "@/EnvironmentSwitch";
import ProjectWorkspace from "@/ProjectWorkspace";
import {ProjectMapNavigation, type ProjectMapKind} from "@/ProjectLayout";
import WorkspaceDocumentEditor from "@/WorkspaceDocumentEditor";
import EditorWorkbench, { type WorkbenchPane } from "@/EditorWorkbench";
import ContextShelf from "@/ContextShelf";
import SourceExplorer from "@/SourceExplorer";
import { useWorkspaceSelection } from "@/workspace-selection";
import "@/desktop-workspaces.css";

import ScopeContext from "@/ScopeContext";
import LayerContext from "@/LayerContext";
import AgentsWorkspace from "@/AgentsWorkspace";
import "@/agents.css";
import CodingPanel from "@/CodingPanel";
import type { WireframeKind } from "@/wireframe-model";
import DrawingTools from "@/DrawingTools";
import { discardDrawingDrafts, type DrawingTool } from "@/drawing-state";
const DrawingWorkspace = lazy(() => import("@/DrawingWorkspace"));
import ArchifyMap from "@/ArchifyMap";
import WorkspaceSettings from "@/WorkspaceSettings";
import WorkspaceBoundary from "@/WorkspaceBoundary";
import {
  readMode,
  readSettings,
  SETTINGS_KEY,
  type WorkspaceMode,
  type SurfaceSettings,
} from "@/workspace-settings";
import "@/workspace-modes.css";
import DesktopThemeControls from "@/DesktopThemeControls";
import "@/desktop-v3.css";
import NodePanel, { type NodeTab } from "@/NodePanel";
import RemovalDialog from "@/RemovalDialog";
import { discardSpecDrafts } from "@/NodeSpecEditor";
import {
  api,
  type Graph,
  type View,
  type Project,
  type Job,
  type CanvasNode,
  type Workspace,
  type RemovalPreview,
} from "@/types";
const initial = new URLSearchParams(location.search);
/** Sjednotí URL parametry mode a environment do jednoho konzistentního páru. */
function resolveInitialModeEnvironment(
  params: URLSearchParams,
): { mode: WorkspaceMode; environment: Environment } {
  const modeParam = readMode(params.get("mode"));
  const envParam = params.get("environment");
  const hasEnv = envParam === "project" || envParam === "editor" || envParam === "live";
  if (!hasEnv) {
    return { mode: modeParam, environment: modeParam === "agents" ? "live" : "editor" };
  }
  const environment = envParam as Environment;
  if (environment === "live") return { mode: "agents", environment };
  return { mode: modeParam === "agents" ? "structure" : modeParam, environment };
}
const initialModeEnvironment = resolveInitialModeEnvironment(initial);
/**
 * Montážní místa v3 panelů (src/desktop-v3, Sonnet). Koordinátor je předá v main.tsx, např.
 * <App v3={{ agentPacket: (p) => <AgentPacketPanel {...p} /> }} />. Nenapojený slot nevykreslí nic.
 */
export type DesktopV3Slots = {
  projectMemory?: (scope: { project: string; workspace: string; path: string }) => ReactNode;
  nodeWorkflow?: (scope: { project: string; workspace: string; nodeId: string }) => ReactNode;
  agentPacket?: (scope: { project: string; workspace: string; nodeId: string; path: string; references: string[]; note: string }) => ReactNode;
  liveWorkspace?: (scope: { project: string; workspace: string; nodeId?: string }) => ReactNode;
};
const INSPECTOR_KEY = "opora:desktop-inspector:v1";
function readInspectorOpen() {
  try { return localStorage.getItem(INSPECTOR_KEY) !== "hidden"; } catch { return true; }
}
export default function App({ v3 = {} }: { v3?: DesktopV3Slots } = {}) {
  const [screen, setScreen] = useState<"home" | "canvas">(() => initial.get("screen") === "home" ? "home" : initial.get("screen") === "canvas" || initial.has("mode") || initial.has("layer") || initial.has("workspace") ? "canvas" : "home");
  const [draftProject, setDraftProject] = useState<Project | undefined>();
  const [wireframeMode, setWireframeMode] = useState(initial.get("wireframe") === "1");
  const [wireframeInsert, setWireframeInsert] = useState<{ kind: WireframeKind; sequence: number }>();
  const lastLoadedScope = useRef("");
  const [project, setProject] = useState(initial.get("project") ?? "draft");
  const [workspace, setWorkspace] = useState(
    initial.get("workspace") ?? "draft",
  );
  const [drawingTool, setDrawingTool] = useState<DrawingTool>("selection");
  const selection = useWorkspaceSelection(project, workspace);
  const [showContext, setShowContext] = useState(false);
  const [editorDocumentOpen, setEditorDocumentOpen] = useState(false);
  const [workbenchOpen, setWorkbenchOpen] = useState(false);
  const [workbenchPane, setWorkbenchPane] = useState<WorkbenchPane>("context");
  const [inspectorOpen, setInspectorOpen] = useState(readInspectorOpen);
  const [liveView, setLiveView] = useState<"overview" | "runs">("overview");
  function toggleInspector() {
    setInspectorOpen((shown) => {
      try { localStorage.setItem(INSPECTOR_KEY, shown ? "hidden" : "shown"); } catch { /* platí aspoň v této relaci */ }
      return !shown;
    });
  }
  useEffect(() => { setShowContext(selection.value.references.length > 0); }, [project, workspace, selection.value.references.length]);
  const [drawingCommand, setDrawingCommand] = useState<{
    type: DrawingTool;
    sequence: number;
  }>({ type: "selection", sequence: 0 });
  const [drawingReady, setDrawingReady] = useState(false);
  const [mode, setEditorMode] = useState<WorkspaceMode>(
    () => initialModeEnvironment.mode,
  );
  const [environment, setEnvironment] = useState<Environment>(
    () => initialModeEnvironment.environment,
  );
  const [projectMapKind,setProjectMapKind] = useState<ProjectMapKind>('archify');
  const lastEditorMode = useRef<WorkspaceMode>(mode === "agents" ? "structure" : mode);
  function setMode(next: WorkspaceMode) {
    setEditorDocumentOpen(false);
    setEditorMode(next);
    if (next !== "agents") lastEditorMode.current = next;
    setEnvironment(next === "agents" ? "live" : "editor");
  }
  function changeEnvironment(next: Environment) {
    setEnvironment(next);
    if (next === "live") setEditorMode("agents");
    else if (next === "editor") setEditorMode(lastEditorMode.current);
  }
  const [editingName, setEditingName] = useState<string | null>(null);
  const [agentTask, setAgentTask] = useState<AgentTaskRequest | null>(null);
  const [settings, setSettings] = useState(readSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [nodeTab, setNodeTab] = useState<NodeTab>("content");
  const [textRevision, setTextRevision] = useState(0);
  const [focusRun, setFocusRun] = useState<{ sourceId: string; runId: string } | null>(null);
  const [parent, setParent] = useState<string | null>(initial.get("layer"));
  const [selected, setSelected] = useState<string | null>(initial.get("node"));
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [removal, setRemoval] = useState<RemovalPreview | null>(null);
  const activeScope = useRef({ project, workspace });
  activeScope.current = { project, workspace };
  const activeContext = useRef("");
  activeContext.current = JSON.stringify([
    project,
    workspace,
    parent,
    selected,
    selectedEdge,
  ]);
  const bootstrapGeneration = useRef(0);
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [view, setView] = useState<View | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<
    "github" | "sector" | "node" | "workspace" | null
  >(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [approved, setApproved] = useState(false);
  const [createOrigin, setCreateOrigin] = useState<"existing" | "planned" | "concept" | null>(null);
  const [createPath, setCreatePath] = useState<string | null>(null);
  const [createKind, setCreateKind] = useState<"directory" | "file">("directory");
  const [createPlannedPath, setCreatePlannedPath] = useState("");
  const [createPurpose, setCreatePurpose] = useState("");
  const [createTargetSector, setCreateTargetSector] = useState("");
  const [actor, setActor] = useState("");
  const operationGeneration = useRef(0);
  const generation = useRef(0);
  async function bootstrap() {
    const ticket = ++bootstrapGeneration.current;
    const b = await api<{ projects: Project[]; jobs: Job[]; draft?: Project }>("/api/bootstrap");
    if (ticket !== bootstrapGeneration.current) return;
    setProjects(b.projects);
    setDraftProject(b.draft);
    setJobs(b.jobs);
  }
  async function refresh() {
    const g = ++generation.current;
    setView(null);
    try {
      const v = await api<View>(
        `/api/view?project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}`,
      );
      if (g === generation.current) setView(v);
    } catch (e) {
      if (g === generation.current) setError(String(e));
    }
  }
  useEffect(() => {
    bootstrap().catch((e) => setError(String(e)));
    const t = setInterval(() => bootstrap().catch(() => {}), 2500);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    const nextScope = JSON.stringify([project, workspace]);
    if (lastLoadedScope.current !== nextScope) {
      operationGeneration.current++;
      setBusy(false); setModal(null);
      // První načtení zachová uzel z odkazu; další změna scope jej zahodí.
      if (lastLoadedScope.current) setSelected(null);
      setSelectedEdge(null); setRemoval(null); lastLoadedScope.current = nextScope;
      // Výběr v asynchronním stromu platí jen pro původní projekt/workspace.
      setCreateOrigin(null); setCreatePath(null); setCreateKind("directory");
      setCreatePlannedPath(""); setCreatePurpose(""); setCreateTargetSector("");
    }
    setError("");
    if (screen === "canvas") refresh(); else generation.current++;
  }, [project, workspace, screen]);
  useEffect(() => {
    const q = new URLSearchParams({ project, workspace, mode, screen, environment });
    if (parent) q.set("layer", parent);
    if (selected) q.set("node", selected);
    if (wireframeMode) q.set("wireframe", "1");
    history.replaceState(null, "", "/?" + q);
  }, [project, workspace, parent, selected, mode, screen, wireframeMode, environment]);
  const completed = jobs
    .filter((j) => j.status === "complete" && j.project_id === project)
    .map((j) => j.id)
    .join(",");
  useEffect(() => {
    if (completed && screen === "canvas") refresh();
  }, [completed]);
  async function run(action: () => Promise<void>) {
    const ticket = ++operationGeneration.current;
    const scope = { ...activeScope.current };
    const isCurrent = () => ticket === operationGeneration.current &&
      scope.project === activeScope.current.project && scope.workspace === activeScope.current.workspace;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      if (isCurrent()) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (isCurrent()) setBusy(false);
    }
  }
  async function save(graph: Graph, onApplied?: () => void) {
    if (!view) return;
    const ticket = ++generation.current;
    const scope = { project, workspace };
    const saved = await api<View>("/api/graph", {
      project,
      workspace,
      graph,
      digest: view.digest,
    });
    if (
      ticket === generation.current &&
      activeScope.current.project === scope.project &&
      activeScope.current.workspace === scope.workspace
    ) {
      setView(saved);
      onApplied?.();
    }
  }
  const graph = view?.graph ?? { nodes: [], edges: [] };
  const node = graph.nodes.find((n) => n.id === selected);
  const edge = graph.edges.find((e) => e.id === selectedEdge);
  const layer = graph.nodes.find((n) => n.id === parent);
  const editable = !!view && !view.readOnly && !busy;
  const visible = graph.nodes.filter((n) => n.parentId === parent);
  const visibleIds = new Set(visible.map((n) => n.id));
  const outsideLinks = graph.edges.filter(
    (e) =>
      (visibleIds.has(e.source) || visibleIds.has(e.target)) &&
      !(visibleIds.has(e.source) && visibleIds.has(e.target)),
  ).length;
  const ancestors: CanvasNode[] = [];
  let cursor = layer;
  while (cursor) {
    ancestors.unshift(cursor);
    cursor = graph.nodes.find((n) => n.id === cursor!.parentId);
  }
  const ancestorSector = [...ancestors].reverse().find((n) => n.kind === "sector") ?? null;
  const availableSectors = graph.nodes.filter((n) => n.kind === "sector");
  const targetSector = graph.nodes.find((n) => n.id === createTargetSector) ?? null;
  const effectiveSector = modal === "node" ? (ancestorSector ?? targetSector) : null;
  const activeProject = project === "draft" ? draftProject : projects.find((p) => p.id === project);
  // Volné uzly patří jen historickému vestavěnému draftu; připojený projekt
  // musí nejdřív dostat sektor, aby nevznikl zdroj bez vlastního kontextu.
  const legacyFreeNode = project === "draft" && (activeProject?.sourceKind ?? "builtin") === "builtin";
  const legacyFreeSector = modal === "sector" && project === "draft" && (activeProject?.sourceKind ?? "builtin") === "builtin";
  const conceptCreate = createOrigin === "concept";
  const requiresTargetSector = modal === "node" && !effectiveSector && !legacyFreeNode && !conceptCreate;
  const requiresModeChoice = !legacyFreeSector && !(modal === "node" && legacyFreeNode && !effectiveSector?.sourceRef) && (modal === "sector" || modal === "node");
  const existingAllowedForNode = modal !== "node" || effectiveSector?.sourceRef?.origin === "existing";
  const purposeReady = conceptCreate ? createPurpose.trim().length > 0 : createOrigin !== "planned" || (modal === "sector" ? createPurpose.trim().length >= 12 : createPurpose.trim().length > 0);
  const pathReady = createOrigin !== "existing" || (existingAllowedForNode && createPath !== null);
  const plannedNodePathReady = createOrigin !== "planned" || modal !== "node" || !createPlannedPath.trim() || effectiveSector?.sourceRef?.origin === "existing" || !!effectiveSector?.sourceRef?.path;
  const createReady = !requiresTargetSector && plannedNodePathReady && (!requiresModeChoice || (createOrigin !== null && purposeReady && pathReady));
  const activeWorkspace = view?.workspaces.find((w) => w.id === workspace);
  const localProject = project === "draft" || ["local", "empty", "builtin"].includes(activeProject?.sourceKind ?? "");
  const linkTargets = graph.nodes.map((n) => ({ id: n.id, name: n.name, kind: n.kind }));
  /** Odkaz i souvislost vedou na tentýž uzel: otevře se jeho vrstva a označí se. */
  function openNode(id: string) {
    const target = graph.nodes.find((n) => n.id === id);
    if (!target) return;
    setParent(target.parentId);
    setSelected(target.id);
    setSelectedEdge(null);
  }
  /** Kontextová akce: rodičovská integrace dostane přesný scope, běh nevzniká zde. */
  function requestAgentTask(nodeId: string, text: string, source: AgentTaskRequest["source"]) {
    const target = graph.nodes.find((n) => n.id === nodeId);
    setAgentTask(
      emitAgentTask({
        project,
        workspace,
        layer: parent,
        nodeId,
        nodeName: target?.name ?? nodeId,
        source,
        text,
        requestedAt: new Date().toISOString(),
      }),
    );
  }
  function open(kind: typeof modal) {
    setModal(kind);
    setName("");
    setApproved(false);
    setCreateOrigin(null);
    setCreatePath(null);
    setCreateKind("directory");
    setCreatePlannedPath("");
    setCreatePurpose("");
    setCreateTargetSector("");
  }
  function enter(id: string | null) {
    setParent(id);
    setSelected(null);
    setSelectedEdge(null);
  }
  function selectProject(id: string, sourceKind?: string) {
    generation.current++;
    setView(null);
    setProject(id);
    const kind = sourceKind ?? projects.find((p) => p.id === id)?.sourceKind;
    setWorkspace(id === "draft" || ["local", "empty", "builtin"].includes(kind ?? "") ? "draft" : "main");
    enter(null);
  }
  function updateSettings(value: SurfaceSettings) {
    setSettings(value);
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(value));
    } catch {
      setError("Nastavení nyní platí, ale prohlížeč je nemohl uložit.");
    }
  }
  function connectGraph(source: string, target: string) {
    if (!editable || source === target) return;
    if (graph.edges.some((e) => e.source === source && e.target === target)) {
      setError("Toto propojení už existuje.");
      return;
    }
    run(() =>
      save({
        ...graph,
        edges: [...graph.edges, { id: crypto.randomUUID(), source, target }],
      }),
    );
  }
  async function requestRemoval(kind: RemovalPreview["kind"], target: string) {
    const context = activeContext.current;
    await run(async () => {
      const preview = await api<RemovalPreview>(
        "/api/removal-preview?" +
          new URLSearchParams({
            project,
            workspace: kind === "project" ? "main" : workspace,
            kind,
            target,
          }),
      );
      if (context === activeContext.current) setRemoval(preview);
    });
  }
  async function confirmRemoval(preview: RemovalPreview) {
    const result = await api<{
      view?: View;
      nodeIds?: string[];
      removedProject?: string;
    }>("/api/remove", {
      project: preview.project,
      workspace: preview.workspace,
      kind: preview.kind,
      target: preview.target,
      digest: preview.digest,
      confirmed: true,
    });
    generation.current++;
    if (preview.kind === "project") {
      bootstrapGeneration.current++;
      discardSpecDrafts(preview.project);
      discardDrawingDrafts(preview.project);
      setProjects((items) => items.filter((p) => p.id !== preview.project));
      setJobs((items) => items.filter((j) => j.project_id !== preview.project));
      if (activeScope.current.project === preview.project)
        selectProject("draft");
      bootstrap().catch((e) => setError(String(e)));
    } else {
      discardSpecDrafts(
        preview.project,
        preview.workspace,
        result.nodeIds ?? [],
      );
      discardDrawingDrafts(
        preview.project,
        preview.workspace,
        result.nodeIds ?? [],
      );
      if (
        activeScope.current.project === preview.project &&
        activeScope.current.workspace === preview.workspace &&
        result.view
      ) {
        setView(result.view);
        setSelected(null);
        setSelectedEdge(null);
        if (parent && result.nodeIds?.includes(parent)) setParent(null);
      }
    }
    setRemoval((current) =>
      current?.digest === preview.digest ? null : current,
    );
  }
  if (screen === "home") return <>
    <ProjectHome projects={projects} draftProject={draftProject} projectId={project} jobs={jobs} onChoose={selectProject} onRefresh={bootstrap} onOpen={() => { changeEnvironment("project"); setScreen("canvas"); }} onConnected={() => { changeEnvironment("project"); setScreen("canvas"); }} onRemove={() => requestRemoval("project", project)} renderLLM={(_snapshot, dirty) => <><PlanPanel key={project + ":plan"} project={project} dirty={dirty} /><CodingPanel key={project + ":coding"} project={project} dirty={dirty} /></>} />
    {removal && <RemovalDialog key={removal.digest} preview={removal} onClose={() => setRemoval(null)} onConfirm={confirmRemoval} />}
  </>;
  const artifactMapOpen = mode === "map" && !editorDocumentOpen;
  const inspectorTools =
    mode === "map" ? (
      null
    ) : mode === "drawing" ? (
      <DrawingTools
        wireframeMode={wireframeMode}
        onWireframeMode={setWireframeMode}
        onInsertWireframe={(kind) => setWireframeInsert((old) => ({ kind, sequence: (old?.sequence ?? 0) + 1 }))}
        tool={drawingTool}
        ready={drawingReady && editable}
        onTool={(type) => setDrawingCommand((old) => ({ type, sequence: old.sequence + 1 }))}
      />
    ) : undefined;
  const showNode = !!node && (mode === "structure" || mode === "map");
  const showEdge = !showNode && !!edge && (mode === "structure" || mode === "map");
  return (
    <div className="app desktop-v2 desktop-v3">
      <TopBar
        projectNavigation={environment === "project" ? <ProjectMapNavigation value={projectMapKind} onChange={setProjectMapKind}/> : null}
        trailing={<DesktopThemeControls/>}
        projects={projects}
        draftProject={draftProject}
        project={project}
        busy={busy}
        localProject={localProject}
        workspace={workspace}
        view={view}
        activeWorkspace={activeWorkspace}
        onSelectProject={(id) => selectProject(id)}
        onMain={() => {
          setWorkspace("main");
          enter(null);
        }}
        onWorkspace={() => {
          if (localProject) setWorkspace("draft");
          else if (view?.workspaces.length) {
            setWorkspace(view.workspaces[0].id);
            enter(null);
          } else open("workspace");
        }}
        onSelectWorkspace={(id) => {
          setWorkspace(id);
          enter(null);
        }}
        onSurfaceSettings={() => setSettingsOpen(true)}
        onProjectSettings={() => setScreen("home")}
        onRefresh={() => run(refresh)}
        onSync={() => {
          if (window.confirm("Aktualizovat pouze čistou spravovanou kopii ze schváleného upstreamu? Žádný push."))
            run(async () => {
              await api("/api/sync", { project, confirmed: true });
              await bootstrap();
            });
        }}
        onRemoveProject={() => requestRemoval("project", project)}
      >
        <EnvironmentSwitch value={environment} onChange={changeEnvironment} disabled={busy} />

      </TopBar>
      {error && (
        <div className="error" role="alert">
          {error}
          <button aria-label="Zavřít chybu" onClick={() => setError("")}>
            ×
          </button>
        </div>
      )}
      {environment === "project" ? <ProjectWorkspace project={project} workspace={workspace} selection={selection.value} onChange={selection.change} mapKind={projectMapKind}/> : <>
      {environment === "editor" && <div className="environment-toolbar v3-toolbar" role="toolbar" aria-label="Nástroje Editoru">
        <div className="v3-tool-group" role="group" aria-label="Pohled">
          <ModeRail mode={mode} onMode={setMode} editorOnly inactive={editorDocumentOpen} />
          <button aria-pressed={editorDocumentOpen} onClick={() => setEditorDocumentOpen((open) => !open)}>Dokumentace</button>
        </div>
        {(mode === "structure" || mode === "text") && <div className="v3-tool-group" role="group" aria-label="Tvorba">
          <button type="button" disabled={!editable} onClick={() => open("sector")}>+ Sektor</button>
          <button type="button" className="primary" disabled={!editable} onClick={() => open("node")}>+ Uzel</button>
        </div>}
        {/* Se skrytým inspektorem zůstávají nástroje kreslení a mapy dosažitelné v liště. */}
        {!inspectorOpen && !editorDocumentOpen && inspectorTools && <div className="v3-tool-group v3-mode-tools" role="group" aria-label="Nástroje pohledu">{inspectorTools}</div>}
        <span className="v3-grow" />
        {!artifactMapOpen && <><div className="v3-tool-group" role="group" aria-label="Panely">
          <button aria-pressed={showContext} onClick={() => setShowContext((shown) => !shown)}>Kontext</button>
          <button aria-pressed={inspectorOpen} title="Skrýt nebo zobrazit pravý inspektor" onClick={toggleInspector}>Inspektor</button>
        </div>
        <button className="primary v3-materials" onClick={() => { setWorkbenchPane("packet"); setWorkbenchOpen(true); }}>Podklady pro agenta</button>
        <button className="v3-quiet" title="Pokročilé: kontextový paket, LLM návrh, Coding, dokumentační úkol" onClick={() => setWorkbenchOpen(true)}>AI nástroje</button></>}
      </div>}
      <div className={"workspace-shell " + mode + "-mode" + ((mode === "agents" || mode === "map") ? " no-inspector" : "") + (!showContext ? " no-context" : "") + (!inspectorOpen ? " inspector-hidden" : "") + (environment === "editor" && editorDocumentOpen ? " document-open" : "")}>
        {environment === "editor" && showContext && !artifactMapOpen && <ContextShelf project={project} workspace={workspace} value={selection.value} onChange={selection.change} onAdd={selection.add}
          onOpen={(path) => { selection.change({ sourcePath: path }); setEditorDocumentOpen(true); }} />}
        <main className="canvas-area">
          {!artifactMapOpen && <div className="content-head">
            <nav aria-label="Cesta plátnem" className="crumbs">
              <button type="button" onClick={() => enter(null)}>Projekt</button>
              {ancestors.map((n) => (
                <span key={n.id}>
                  <i aria-hidden="true">/</i>
                  <button type="button" onClick={() => enter(n.id)}>{n.name}</button>
                </span>
              ))}
            </nav>
            {mode === "structure" && outsideLinks > 0 && (
              <button type="button" className="quiet" onClick={() => setMode("map")}>
                Mapa architektury projektu
              </button>
            )}

          </div>}
          <div className="canvas-surface">
            {environment === "editor" && editorDocumentOpen ? <WorkspaceDocumentEditor key={JSON.stringify([project, workspace, selection.value.sourcePath])} project={project} workspace={workspace} path={selection.value.sourcePath} /> : view ? (
              mode === "text" ? (
                <TextWorkspace project={project} workspace={workspace} layer={layer} children={visible} targets={linkTargets} onEnter={enter} onOpenNode={(id) => { openNode(id); setMode("structure"); }} onAgentTask={requestAgentTask} onTextSaved={() => setTextRevision((value) => value + 1)} />
              ) : mode === "agents" ? (
                v3.liveWorkspace ? <div className="v3-live">
                  <nav className="v3-live-tabs" aria-label="Pohled Live Run">
                    <button aria-pressed={liveView === "overview"} onClick={() => setLiveView("overview")}>Přehled a tickety</button>
                    <button aria-pressed={liveView === "runs"} onClick={() => setLiveView("runs")}>Dohled běhů</button>
                  </nav>
                  {liveView === "overview" ? <div className="v3-slot">{v3.liveWorkspace({ project, workspace, nodeId: selected ?? undefined })}</div>
                    : <AgentsWorkspace project={project} workspace={workspace} focusRun={focusRun} onOpenNode={(id) => { openNode(id); setMode("structure"); }} />}
                </div> : <AgentsWorkspace project={project} workspace={workspace} focusRun={focusRun} onOpenNode={(id) => { openNode(id); setMode("structure"); }} />
              ) : mode === "map" ? (
                <ArchifyMap key={project} project={project}/>
              ) : mode === "drawing" ? (
                <WorkspaceBoundary
                  key={JSON.stringify([project, workspace, parent, mode])}
                  onExit={() => setMode("structure")}
                >
                  <Suspense
                    fallback={
                      <div className="loading">Načítám kreslicí nástroje…</div>
                    }
                  >
                    <DrawingWorkspace
                      wireframeMode={wireframeMode}
                      wireframeInsert={wireframeInsert}
                      key={JSON.stringify([project, workspace, parent])}
                      project={project}
                      workspace={workspace}
                      layer={parent ?? ""}
                      tool={drawingCommand.type}
                      toolSequence={drawingCommand.sequence}
                      settings={settings}
                      onTool={setDrawingTool}
                      onReady={setDrawingReady}
                    />
                  </Suspense>
                </WorkspaceBoundary>
              ) : (
                <Board
                  key={project + workspace + parent}
                  scope={project + workspace + parent}
                  graph={graph}
                  settings={settings}
                  parent={parent}
                  selected={selected}
                  disabled={!editable}
                  selectedEdge={selectedEdge}
                  onSelect={(id) => {
                    setSelected(id);
                    setSelectedEdge(null);
                  }}
                  onSelectEdge={(id) => {
                    setSelectedEdge(id);
                    setSelected(null);
                  }}
                  onEnter={enter}
                  editing={editingName}
                  onEditing={setEditingName}
                  onRename={(id, name) =>
                    run(() =>
                      save({
                        ...graph,
                        nodes: graph.nodes.map((n) =>
                          n.id === id ? { ...n, name } : n,
                        ),
                      }),
                    )
                  }
                  onCreateAt={(x, y) => {
                    if (!editable) return;
                    const created: CanvasNode = {
                      id: crypto.randomUUID(),
                      parentId: parent,
                      kind: "node",
                      name: "Nový uzel",
                      purpose: "",
                      x,
                      y,
                    };
                    run(async () => {
                      await save({ ...graph, nodes: [...graph.nodes, created] });
                      setSelected(created.id);
                      setEditingName(created.id);
                    });
                  }}
                  onPosition={(id, x, y) =>
                    run(() =>
                      save({
                        ...graph,
                        nodes: graph.nodes.map((n) =>
                          n.id === id ? { ...n, x, y } : n,
                        ),
                      }),
                    )
                  }
                  onConnect={(c) => {
                    if (c.source && c.target)
                      run(() =>
                        save({
                          ...graph,
                          edges: [
                            ...graph.edges,
                            {
                              id: crypto.randomUUID(),
                              source: c.source!,
                              target: c.target!,
                            },
                          ],
                        }),
                      );
                  }}
                />
              )
            ) : (
              <div className="loading" role="status">
                Načítám plátno…
              </div>
            )}
            {mode === "structure" && view && !visible.length && (
              <div className="empty-canvas">
                <p className="empty-title">{view.readOnly ? "V mainu zatím není graf." : "Prázdná vrstva."}</p>
                <p className="muted">
                  {view.readOnly
                    ? "Repozitář nemá verzovaný opora-canvas.json. Vytvořte pracovní prostor a připravte graf tam."
                    : "Dvojklik na plátno vytvoří uzel na místě. Sektor přidáte tlačítkem + Sektor."}
                </p>
                {view.readOnly && (
                  <button type="button" onClick={() => open("workspace")}>
                    Vytvořit pracovní prostor
                  </button>
                )}
              </div>
            )}
            {busy && (
              <div className="saving" role="status">
                Ukládám / ověřuji operaci…
              </div>
            )}
          </div>
          {!artifactMapOpen && <footer className="statusline">
            <span>
              {visible.length} uzlů v této vrstvě · {graph.nodes.length} v grafu
            </span>
            <span>
              {view?.readOnly ? "SCHVÁLENÁ VĚTEV · POUZE ČTENÍ" : "NÁVRH / PRACOVNÍ ZMĚNY"} · Agent se automaticky nespouští
            </span>
          </footer>}
        </main>
        {mode !== "agents" && !artifactMapOpen && !editorDocumentOpen && inspectorOpen && (
          <aside className="inspector" aria-label="Inspektor">
            {showNode && node ? (<>
              <NodePanel
                key={project + ":" + workspace + ":" + node.id + ":" + view?.digest}
                node={node}
                project={project}
                workspace={workspace}
                readOnly={!!view?.readOnly}
                busy={busy}
                workspaces={view?.workspaces ?? []}
                tab={nodeTab}
                onTab={setNodeTab}
                onEnter={() => {
                  enter(node.id);
                  if (mode === "map") setMode("structure");
                }}
                onDelete={() => requestRemoval("node", node.id)}
                onSave={(n) =>
                  run(() =>
                    save({
                      ...graph,
                      nodes: graph.nodes.map((old) => (old.id === n.id ? n : old)),
                    }),
                  )
                }
                onWorkspace={() => open("workspace")}
                onOpenNode={openNode}
                onAgentTask={() => requestAgentTask(node.id, node.purpose || node.name, "canvas")}
                onLiveRun={v3.liveWorkspace ? () => {
                  setLiveView("overview");
                  setMode("agents");
                } : undefined}
                onOpenRun={(sourceId, runId) => {
                  setFocusRun({ sourceId, runId });
                  setLiveView("runs");
                  setMode("agents");
                }}
              />
              {v3.nodeWorkflow && <div className="v3-slot v3-node-workflow">{v3.nodeWorkflow({ project, workspace, nodeId: node.id })}</div>}
            </>) : showEdge && edge ? (
              <div className="edge-panel">
                <div className="eyebrow">VAZBA · DETAIL</div>
                <h2>
                  {graph.nodes.find((n) => n.id === edge.source)?.name} → {graph.nodes.find((n) => n.id === edge.target)?.name}
                </h2>
                <p className="muted">Explicitní propojení mezi uzly. Smazání odstraní jen vazbu, uzly zůstávají.</p>
                <button
                  type="button"
                  className="danger"
                  disabled={!editable}
                  title={view?.readOnly ? "Main je pouze pro čtení." : "Zobrazit dopad před smazáním"}
                  onClick={() => requestRemoval("edge", edge.id)}
                >
                  Smazat vazbu
                </button>
              </div>
            ) : mode === "text" && layer ? (
              <LayerContext
                key={project + ":" + workspace + ":" + layer.id}
                project={project}
                workspace={workspace}
                layer={layer}
                targets={linkTargets}
                readOnly={!!view?.readOnly}
                revision={textRevision}
                onOpenNode={(id) => {
                  openNode(id);
                  setMode("structure");
                }}
                onAgentTask={(text) => requestAgentTask(layer.id, text, "journal")}
              />
            ) : (
              <ScopeContext
                mode={mode}
                layer={layer}
                activeProject={activeProject}
                view={view}
                activeWorkspace={activeWorkspace}
                jobs={jobs}
                localProject={localProject}
                tools={inspectorTools}
                onWorkspace={() => open("workspace")}
              />
            )}
          </aside>
        )}
      </div>
      </>}
      <EditorWorkbench key={JSON.stringify([project, workspace])} project={project} workspace={workspace} nodeId={selected ?? ""}
        graph={graph} selection={selection.value} open={environment === "editor" && workbenchOpen} pane={workbenchPane}
        onPane={setWorkbenchPane} onClose={() => setWorkbenchOpen(false)}
        packet={v3.agentPacket?.({ project, workspace, nodeId: selected ?? "", path: selection.value.sourcePath, references: selection.value.references, note: selection.value.note }) ?? null} />
      {settingsOpen && (
        <WorkspaceSettings
          value={settings}
          onChange={updateSettings}
          onClose={() => setSettingsOpen(false)}
        />
      )}
      {removal && (
        <RemovalDialog
          key={removal.digest}
          preview={removal}
          onClose={() => setRemoval(null)}
          onConfirm={confirmRemoval}
        />
      )}
      {agentTask && <AgentTaskNotice request={agentTask} onDismiss={() => setAgentTask(null)} />}
      {modal && (
        <div className="modal-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Nastavení operace"
            className="modal"
          >
            <button
              className="close"
              aria-label="Zavřít dialog"
              onClick={() => setModal(null)}
              disabled={busy}
            >
              ×
            </button>
            {modal === "github" ? (
              <>
                <div className="eyebrow">SCHVÁLENÝ ZDROJ</div>
                <h2>Připojit GitHub repozitář</h2>
                <p>
                  Vznikne samostatná spravovaná kopie s Git historií. Vaše
                  existující adresáře se nemění.
                </p>
                <label className="field">
                  GitHub URL
                  <input
                    aria-label="GitHub URL"
                    value={url}
                    onChange={(e) => {
                      setUrl(e.target.value);
                      setApproved(false);
                    }}
                    placeholder="https://github.com/vlastnik/repozitar"
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={approved}
                    onChange={(e) => setApproved(e.target.checked)}
                  />
                  Schvaluji tento zdroj pro klonování. Nepovoluji push ani
                  merge.
                </label>
                <button
                  className="primary"
                  disabled={!approved || busy}
                  onClick={() =>
                    run(async () => {
                      await api("/api/connect", { url, approved });
                      setModal(null);
                      await bootstrap();
                    })
                  }
                >
                  Připojit na pozadí
                </button>
                <p className="muted">
                  Privátní repo vyžaduje předem nastavený Git přístup na
                  serveru. Tokeny sem nevkládejte.
                </p>
              </>
            ) : modal === "workspace" ? (
              <>
                <h2>Oddělený pracovní prostor</h2>
                {localProject ? (
                  <p>
                    Nejdřív připojte schválený GitHub repozitář. Lokální návrh
                    se tím nesmaže.
                  </p>
                ) : (
                  <>
                    <p>
                      Nová větev a worktree vzniknou ze současného spravovaného
                      mainu. Vybraný uzel:{" "}
                      {node?.name ?? layer?.name ?? "kořen projektu"}.
                    </p>
                    <label className="field">
                      Vlastník / označení agenta
                      <input
                        aria-label="Vlastník pracovního prostoru"
                        value={actor}
                        onChange={(e) => setActor(e.target.value)}
                        maxLength={120}
                      />
                    </label>
                    <button
                      className="primary"
                      disabled={busy || !actor.trim()}
                      onClick={() =>
                        run(async () => {
                          const w = await api<Workspace>("/api/workspaces", {
                            project,
                            nodeId: node?.id ?? layer?.id ?? "project",
                            actor,
                          });
                          setWorkspace(w.id);
                          setModal(null);
                          enter(null);
                        })
                      }
                    >
                      Vytvořit worktree
                    </button>
                  </>
                )}
              </>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (busy || !name.trim() || !createReady) return;
                  const submitScope = { ...activeScope.current };
                  run(async () => {
                    const parentId = modal === "node" && !ancestorSector && targetSector ? targetSector.id : parent;
                    const siblings = graph.nodes.filter((n) => n.parentId === parentId).length;
                    const plannedNodePath = modal === "node" && effectiveSector?.sourceRef?.path && createPlannedPath.trim()
                      ? `${effectiveSector.sourceRef.path}/${createPlannedPath.trim()}`
                      : createPlannedPath.trim();
                    let sourceRef: CanvasNode["sourceRef"] = null;
                    if (modal === "sector" && createOrigin === "existing") {
                      sourceRef = { origin: "existing", path: createPath ?? "", kind: "directory" };
                    } else if (modal === "sector" && createOrigin === "planned") {
                      sourceRef = { origin: "planned", path: createPlannedPath.trim(), kind: "directory" };
                    } else if (modal === "node" && effectiveSector && createOrigin === "existing") {
                      sourceRef = { origin: "existing", path: createPath ?? "", kind: createKind };
                    } else if (modal === "node" && effectiveSector && createOrigin === "planned") {
                      sourceRef = { origin: "planned", path: plannedNodePath, kind: createKind };
                    }
                    const n: CanvasNode = {
                      id: crypto.randomUUID(),
                      parentId,
                      kind: modal as "sector" | "node",
                      name,
                      purpose: createOrigin === "planned" || conceptCreate ? createPurpose.trim() : "",
                      x: (siblings % 3) * 310,
                      y: Math.floor(siblings / 3) * 210,
                      ...(sourceRef ? { sourceRef } : {}),
                    };
                    await save({ ...graph, nodes: [...graph.nodes, n] }, () => {
                      if (
                        activeScope.current.project !== submitScope.project ||
                        activeScope.current.workspace !== submitScope.workspace
                      ) return;
                      setParent(parentId);
                      setSelected(n.id);
                      setSelectedEdge(null);
                      setModal(null);
                    });
                  });
                }}
              >
                <div className="eyebrow">{modal === "sector" ? "SEKTOR V TÉTO VRSTVĚ" : "UZEL V TÉTO VRSTVĚ"}</div>
                <h2>{modal === "sector" ? "Nový sektor" : "Nový uzel"}</h2>
                <label className="field">
                  Název uzlu
                  <input
                    aria-label="Název uzlu"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    maxLength={160}
                    autoFocus
                  />
                </label>
                {modal === "node" && !ancestorSector && (!conceptCreate || availableSectors.length > 0) && (
                  <label className="field">
                    Cílový sektor
                    <select
                      aria-label="Cílový sektor"
                      value={createTargetSector}
                      onChange={(e) => {
                        const nextTargetSector = graph.nodes.find((n) => n.id === e.target.value && n.kind === "sector") ?? null;
                        setCreateTargetSector(e.target.value);
                        // Legacy volný uzel nemá volbu zdroje: nenechávej skrytý návrh
                        // blokovat vytvoření ani prosakovat do uzlu bez zdroje.
                        if (legacyFreeNode && !nextTargetSector?.sourceRef) {
                          setCreateOrigin(null);
                          setCreatePath(null);
                          setCreateKind("directory");
                          setCreatePlannedPath("");
                          setCreatePurpose("");
                          return;
                        }
                        // Změna rodiče nemaže rozepsaný návrh. Jen existující cestu
                        // je nutné znovu vybrat v rozsahu nového sektoru.
                        if (createOrigin === "existing") {
                          setCreateOrigin(null);
                          setCreatePath(null);
                        } else if (createOrigin === "planned" && createPlannedPath.trim() &&
                          nextTargetSector?.sourceRef?.origin !== "existing" && !nextTargetSector?.sourceRef?.path) {
                          // Neurčený sektor nemůže relativní cestu bezpečně ukotvit.
                          setCreatePlannedPath("");
                        }
                      }}
                    >
                      <option value="">{legacyFreeNode ? "Bez zdroje (volný uzel jako dosud)" : "Vyberte sektor"}</option>
                      {availableSectors.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                    {requiresTargetSector && !targetSector && <p className="create-source-note">Tento projekt vyžaduje sektor. Vyberte cílový sektor, aby se uzel vytvořil v jeho vrstvě se zdrojovým kontextem.</p>}
                  </label>
                )}
                {requiresModeChoice && (
                  <>
                    <div className="create-mode-toggle" role="group" aria-label="Původ zdroje">
                      <button type="button" aria-pressed={conceptCreate}
                        onClick={() => { setCreateOrigin("concept"); setCreatePath(null); }}>
                        Jen funkce / myšlenka, bez souboru
                      </button>
                      <button
                        type="button"
                        aria-pressed={createOrigin === "existing"}
                        disabled={!existingAllowedForNode}
                        title={!existingAllowedForNode ? "Sektor zatím nemá napojený existující zdroj." : undefined}
                        onClick={() => { setCreateOrigin("existing"); setCreatePath(null); }}
                      >
                        Navázat na existující zdroj
                      </button>
                      <button
                        type="button"
                        aria-pressed={createOrigin === "planned"}
                        onClick={() => { setCreateOrigin("planned"); setCreatePath(null); }}
                      >
                        Navrhnout nové
                      </button>
                    </div>
                    {conceptCreate && <label className="field">
                      Co má tato část umět?
                      <textarea aria-label="Co má tato část umět?" rows={3} required maxLength={2000}
                        value={createPurpose} onChange={(e) => setCreatePurpose(e.target.value)} />
                      <span className="create-source-note">Popište chování vlastními slovy. Nevybíráte soubor ani cestu; vznikne pouze návrh v Editoru.</span>
                    </label>}
                    {createOrigin === "existing" && (
                      existingAllowedForNode ? (
                        <>
                          <div className="create-source-picker">
                            <SourceExplorer
                              project={project}
                              workspace={workspace}
                              selected={createPath ?? ""}
                              onSelect={(path, kind) => { setCreatePath(path); if (modal === "node") setCreateKind(kind === "root" ? "directory" : kind); }}
                              search=""
                              refresh={0}
                              basePath={modal === "node" ? (effectiveSector?.sourceRef?.path ?? "") : ""}
                              rootLabel=""
                              directoriesOnly={modal === "sector"}
                              rootOnly={modal === "sector"}
                            />
                          </div>
                          {createPath !== null ? (
                            <p className="create-source-picked">Vybráno: <code>{createPath || "/"}</code></p>
                          ) : (
                            <p className="create-source-note">Vyberte {modal === "sector" ? "složku" : "složku nebo soubor"} ve stromu, nebo zrušte dialog.</p>
                          )}
                        </>
                      ) : (
                        <p className="create-source-note">Tento sektor nemá napojený existující zdroj; nejdřív mu jej přiřaďte, nebo uzel jen navrhněte.</p>
                      )
                    )}
                    {createOrigin === "planned" && (
                      <>
                        <label className="field">
                          {modal === "node" ? "Zamýšlená cesta v sektoru (nepovinné, nic se nevytváří na disku)" : "Zamýšlená cesta (nepovinné, nic se nevytváří na disku)"}
                          <input
                            aria-label="Zamýšlená cesta"
                            value={createPlannedPath}
                            onChange={(e) => setCreatePlannedPath(e.target.value)}
                            maxLength={400}
                          />
                        </label>
                        {modal === "node" && (
                          <label className="field">
                            Druh navrhovaného zdroje
                            <select aria-label="Druh navrhovaného zdroje" value={createKind} onChange={(e) => setCreateKind(e.target.value as "directory" | "file")}>
                              <option value="directory">Složka</option>
                              <option value="file">Soubor</option>
                            </select>
                          </label>
                        )}
                        <label className="field">
                          {modal === "sector" ? "Podstata návrhu sektoru (nejméně 12 znaků)" : "Podstata návrhu uzlu"}
                          <textarea
                            aria-label={modal === "sector" ? "Podstata návrhu sektoru" : "Podstata návrhu uzlu"}
                            rows={3}
                            required
                            value={createPurpose}
                            onChange={(e) => setCreatePurpose(e.target.value)}
                            maxLength={2000}
                          />
                        </label>
                      </>
                    )}
                  </>
                )}
                <button className="primary" disabled={busy || !name.trim() || !createReady}>
                  Vytvořit
                </button>
              </form>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
