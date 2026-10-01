import { useEffect, useMemo, useRef, useState, lazy, Suspense, type ReactNode } from "react";
import Board from "@/editor/canvas/board/components/Board";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import { addAction, buildBlockNodes, closeOpen, materialPreviewUrl, toggleOpen, type BlockApi, type BlockPort, type OpenBlocks } from "@/editor/workflow/blocks/logic/block-model";
import PipelinePicker from "@/editor/workflow/pipeline-picker/components/PipelinePicker";
import { addBlock, addBlockPort, moveBlock, removeBlock, removeBlockPort, renameBlockPort, setDone, updateBlock } from "@/editor/node-detail/tree/logic/tree-model";
import { edgeFromConnection, sameEdge, type BoardConnection } from "@/editor/canvas/board/logic/board-model";
import { emptyHistory, record, redo, sameGraph, undo, type GraphHistory } from "@/editor/canvas/history/logic/graph-history";
import { useUndoShortcut } from "@/editor/canvas/history/logic/undo-shortcut";
import { arrangeLayer as arrangeFootprints, layerFootprints } from "@/editor/canvas/board/logic/layout-model";
import { clampAreaResize, settleCard } from "@/editor/canvas/board/logic/solid-bodies";
import { itemById } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { cardFromItem, insertBlockFromItem, workflowFromItem } from "@/editor/component-library/library-catalog/logic/catalog-insert";
import { agentItemById } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import { insertActionFromItem, insertRulesFromItem, sectorFromWorkflow } from "@/editor/component-library/agent-catalog/logic/agent-insert";
import EdgeReportPanel from "@/editor/canvas/edge-report/components/EdgeReportPanel";
import { edgeReportView, reportOf, setEdgeReport } from "@/editor/canvas/edge-report/logic/edge-report-model";
import { addMaterial, captionMaterial, materialKindOf, moveMaterial, removeMaterial } from "@/editor/workflow/blocks/logic/block-model";
import NodeLibraryDrawer from "@/editor/component-library/node-library/components/NodeLibraryDrawer";
import { addBlockOfKind, closeLibrary, initialLibrary, openLibrary, showSection } from "@/editor/component-library/node-library/logic/library-model";
import LibraryNavbar from "@/layout/library-navbar/components/LibraryNavbar";
import { useLibraryNavbar } from "@/layout/library-navbar/logic/use-library-navbar";
import "@/layout/library-navbar/styles/library-navbar.css";
import AgentNavbar from "@/layout/agent-navbar/components/AgentNavbar";
import { useAgentNavbar } from "@/layout/agent-navbar/logic/use-agent-navbar";
import "@/layout/agent-navbar/styles/agent-navbar.css";
import PanelToggles from "@/layout/panel-dock/components/PanelToggles";
import PanelDropdown from "@/layout/panel-dock/components/PanelDropdown";
import { usePanelDock } from "@/layout/panel-dock/logic/use-panel-dock";
import { DOCK_PANELS } from "@/layout/panel-dock/logic/panel-dock";
import { cardBlocks } from "@/editor/canvas/node-card/logic/card-model";
import { nodeWorkflowOf, type PipelineLibrary } from "@/shared/desktop-state/logic/types";
import { fetchPipelines } from "@/shared/desktop-state/logic/api";
import "@/editor/component-library/node-library/styles/node-library.css";
import TagFilter from "@/editor/canvas/tag-filter/components/TagFilter";
import ProjectHome from "@/project-setup/components/ProjectHome";
import TextWorkspace, { type TextSubtab } from "@/editor/node-detail/content/components/TextWorkspace";
import { AgentTaskNotice, emitAgentTask, type AgentTaskRequest } from "@/editor/llm-control/editor-context/components/context-actions";
import TopBar from "@/layout/top-bar/components/TopBar";
import AssistantButton from "@/layout/assistant-panel/components/AssistantButton";
import AssistantPanel from "@/layout/assistant-panel/components/AssistantPanel";
import "@/layout/assistant-panel/styles/assistant-panel.css";
import ModeRail from "@/layout/mode-rail/components/ModeRail";
import EnvironmentSwitch, { type Environment } from "@/layout/environment-switch/components/EnvironmentSwitch";
import ProjectWorkspace from "@/project/workspace/components/ProjectWorkspace";
import {ProjectMapNavigation, type ProjectMapKind} from "@/project/shell/components/ProjectLayout";
import WorkspaceDocumentEditor from "@/project/workspace/components/WorkspaceDocumentEditor";
import SourceExplorer from "@/project/source-tree/components/SourceExplorer";
import { useWorkspaceSelection } from "@/shared/selection/logic/workspace-selection";
import { clearSelection, emptySelection, panelsFor, selectBlock, selectEdge, selectNode, type Panels, type Selection } from "@/app/logic/selection-model";
import "@/layout/shell/styles/desktop-workspaces.css";
import "@/editor/node-detail/sync-badge/styles/sync-badge.css";
import "@/project/sync-dashboard/styles/sync-dashboard.css";

import ScopeContext from "@/shared/contexts/components/ScopeContext";
import LayerContext from "@/editor/node-detail/components/LayerContext";
import AgentsWorkspace from "@/live-run/run-monitor/components/AgentsWorkspace";
import "@/live-run/run-monitor/styles/agents.css";
import type { WireframeKind } from "@/editor/canvas/wireframes/logic/wireframe-model";
import DrawingTools from "@/editor/canvas/drawing/components/DrawingTools";
import { discardDrawingDrafts, type DrawingTool } from "@/editor/canvas/drawing/logic/drawing-state";
const DrawingWorkspace = lazy(() => import("@/editor/canvas/drawing/components/DrawingWorkspace"));
import ArchifyMap from "@/project/maps/components/ArchifyMap";
import WorkspaceBoundary from "@/ui-kit/workspace-boundary/components/WorkspaceBoundary";
import {
  readMode,
  readSettings,
  SETTINGS_KEY,
  type WorkspaceMode,
  type SurfaceSettings,
} from "@/shared/surface-settings/logic/workspace-settings";
import { isLocalKind, projectCapabilities } from "@/shared/project-capabilities/logic/project-capabilities";
import "@/layout/shell/styles/workspace-modes.css";
import AccountCorner from "@/layout/account-corner/components/AccountCorner";
import ProcessOverview from "@/live-run/processes/components/ProcessOverview";
import SettingsDialog from "@/settings/components/SettingsDialog";
import "@/design-tokens/styles/theme-tokens.css";
import NodePanel, { type NodeTab } from "@/editor/node-detail/components/NodePanel";
import { badgeView, pickVerdict } from "@/editor/node-detail/sync-badge/logic/sync-badge";
import { commitSpec } from "@/shared/desktop-state/logic/api";
import { useSyncReport } from "@/editor/node-detail/sync-badge/logic/use-sync-report";
import SyncDashboard from "@/project/sync-dashboard/components/SyncDashboard";
import { dashboardView } from "@/project/sync-dashboard/logic/sync-dashboard";
import CommentPanel from "@/editor/canvas/comment-card/components/CommentPanel";
import { newComment, nextCommentSpot } from "@/editor/canvas/comment-card/logic/comment-model";
import AreaPanel from "@/editor/canvas/area/components/AreaPanel";
import { areaLabel, membersOf, moveWithMembers, newArea, nextAreaSpot, resizeArea } from "@/editor/canvas/area/logic/area-model";
import BlockDrawerContent from "@/app/components/BlockDrawerContent";
import RemovalDialog from "@/ui-kit/removal-dialog/components/RemovalDialog";
import { discardSpecDrafts } from "@/editor/node-detail/assignment/components/NodeSpecEditor";
import {
  api,
  type Graph,
  type View,
  type Project,
  type Job,
  type Bootstrap,
  type CanvasNode,
  type Workspace,
  type RemovalPreview,
} from "@/shared/types/logic/types";
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
 * Montážní místa v3 panelů (frontend/agents/desktop-v3). Koordinátor je předá v main.tsx, např.
 * <App v3={{ agentPacket: (p) => <AgentPacketPanel {...p} /> }} />. Nenapojený slot nevykreslí nic.
 */
export type DesktopV3Slots = {
  projectMemory?: (scope: { project: string; workspace: string; path: string }) => ReactNode;
  nodeWorkflow?: (scope: { project: string; workspace: string; nodeId: string }) => ReactNode;
  agentPacket?: (scope: { project: string; workspace: string; nodeId: string; path: string; references: string[]; note: string }) => ReactNode;
  liveWorkspace?: (scope: { project: string; workspace: string; nodeId?: string }) => ReactNode;
};
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
  const docSelection = useWorkspaceSelection(project, workspace);
  const [editorDocumentOpen, setEditorDocumentOpen] = useState(false);
  const [liveView, setLiveView] = useState<"overview" | "runs" | "processes">("overview");
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
    // Jiný mód = jiný pohled na vrstvu; zavěšený panel z minulého pohledu by jen zakrýval plátno.
    dock.close();
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
  const [appSettingsOpen, setAppSettingsOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [nodeTab, setNodeTab] = useState<NodeTab>("content");
  // Podzáložka stránky Text (Uživatel/Agenti); resetuje se na Uživatel při přechodu na jinou vrstvu.
  const [textSubtab, setTextSubtab] = useState<TextSubtab>("user");
  const [textRevision, setTextRevision] = useState(0);
  const [focusRun, setFocusRun] = useState<{ sourceId: string; runId: string } | null>(null);
  const [parent, setParent] = useState<string | null>(initial.get("layer"));
  const initialNode = initial.get("node");
  const [selection, setSelection] = useState<Selection>(() => (initialNode ? selectNode(initialNode) : emptySelection()));
  // Odvozené zkratky: zbytek souboru je psaný proti trojici "vybraný uzel / blok / vazba".
  const selected = selection.node;
  const selectedBlock = selection.block;
  const selectedEdge = selection.edge;
  const [removal, setRemoval] = useState<RemovalPreview | null>(null);
  // Bloky z portů karty: otevřené v této relaci (blok s uloženými položkami je vidět vždy).
  const [openBlocks, setOpenBlocks] = useState<OpenBlocks>({});
  const [pipelinePickerFor, setPipelinePickerFor] = useState<string | null>(null);
  // Knihovna uzlu vlevo: panel vyjede, když uživatel klikne na kartu, a zajede, když výběr zmizí.
  const [library, setLibrary] = useState(initialLibrary);
  useEffect(() => { setLibrary((l) => (selected ? openLibrary(l) : closeLibrary(l))); }, [selected]);
  // Knihovna (levý navbar): jedno rozhraní pro celou aplikaci — stav i preference drží hook,
  // ukládá se pod jediným klíčem `opora:library-navbar:v1`, nikdy s klíčem projektu.
  const libraryNavbar = useLibraryNavbar();
  // Zavěšené panely Editoru (docs/rozvrzeni-editoru.md): Knihovna nebo Agenti a postupy visí pod
  // svým tlačítkem v liště nástrojů, otevřený je nejvýš jeden a jen v Editoru. Stav je jen v paměti
  // sezení; zkratky Ctrl+Shift+, / Ctrl+Shift+. a Esc drží hook. Úvodní obrazovka panely nekreslí,
  // proto tam zkratky nic nepřepínají a odchod na ni panel zavře.
  const dock = usePanelDock(environment === "editor" && screen === "canvas");
  // Agenti a postupy: obsah zavěšeného panelu. Stav drží týž druh hooku pod jediným klíčem
  // `opora:agent-navbar:v1`. Samotné složení panelu čeká níž, až bude znát plátno a plochu
  // (`view`, `desktop`) — záložka Agenti si podle nich načítá zadání vybrané karty.
  const agentNavbar = useAgentNavbar();
  // Přechod na jinou vrstvu (Zanořit, drobečková navigace) vrací stránku Text zpět na Uživatele.
  useEffect(() => { setTextSubtab("user"); }, [parent]);
  const [pipelineLibrary, setPipelineLibrary] = useState<PipelineLibrary | null>(null);
  useEffect(() => {
    if (!library.open || library.section !== "actions" || pipelineLibrary) return;
    fetchPipelines().then(setPipelineLibrary).catch(() => setPipelineLibrary({ categories: [] }));
  }, [library.open, library.section, pipelineLibrary]);
  // Filtr štítků: karty bez vybraného štítku jsou na plátně ztlumené; prázdný = bez filtru.
  const [tagFilter, setTagFilter] = useState("");
  const desktop = useDesktopState(project, workspace);
  // Echo Oracle nad projektem: jeden dotaz na otevřený projekt, přepočet jen na vyžádání.
  const sync = useSyncReport(project, workspace);
  // Vybraný blok zmizel ze stavu (smazán jinde): výběr spadne zpět na uzel, aby zásuvka i inspektor zůstaly platné.
  useEffect(() => {
    if (!selected || !selectedBlock) return;
    if (!nodeWorkflowOf(desktop.state, selected).blocks.some((b) => b.id === selectedBlock)) setSelection(selectNode(selected));
  }, [selected, selectedBlock, desktop.state]);
  const blockApi = useRef<BlockApi>({
    mutate: async () => false, close: () => {}, pickPipeline: () => {}, uploadMaterial: async () => null, discardUpload: () => {}, previewUrl: () => null,
  });
  function togglePort(nodeId: string, port: BlockPort) {
    setOpenBlocks((current) => toggleOpen(current, nodeId, port));
  }
  blockApi.current = {
    mutate: desktop.mutate,
    close: (nodeId, port) => setOpenBlocks((current) => closeOpen(current, nodeId, port)),
    pickPipeline: (nodeId) => setPipelinePickerFor(nodeId),
    uploadMaterial: async (nodeId, dataUrl) => {
      try {
        const saved = await api<{ file: string }>("/api/node-materials/upload", { project, workspace, nodeId, dataUrl });
        return saved.file;
      } catch (error) {
        setError(error instanceof Error ? error.message : "Podklad se nepodařilo nahrát.");
        return null;
      }
    },
    discardUpload: (nodeId, file) => { void api("/api/node-materials/remove", { project, nodeId, file }).catch(() => {}); },
    previewUrl: (nodeId, material) => materialPreviewUrl(project, workspace, nodeId, material),
  };
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
  // Kroky zpět na plátně: snímky grafu patří k jednomu projektu a prostoru, proto žijí v ref vedle
  // pohledu a s každým novým načtením se vyprazdňují.
  const historyRef = useRef<GraphHistory>(emptyHistory());
  async function bootstrap() {
    const ticket = ++bootstrapGeneration.current;
    const b = await api<Bootstrap>("/api/bootstrap");
    if (ticket !== bootstrapGeneration.current) return;
    setProjects(b.projects);
    setDraftProject(b.draft);
    setJobs(b.jobs);
  }
  async function refresh() {
    const g = ++generation.current;
    setView(null);
    historyRef.current = emptyHistory();
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
      // První načtení zachová uzel z odkazu; další změna scope zahodí výběr celý (uzel, blok i vazbu).
      const hadScope = !!lastLoadedScope.current;
      setSelection((current) => (hadScope ? emptySelection() : { ...current, block: null, edge: null }));
      setRemoval(null); lastLoadedScope.current = nextScope;
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
  /**
   * Jediná cesta, kterou se graf ukládá — proto tady vzniká i krok zpět: graf platný před změnou se
   * odloží do historie. `stepped` posílá jen krok zpět/vpřed: nese hotovou historii, takže se sám
   * jako nový krok nezapisuje, a jde na server s `undo: true` — jen tehdy smí snímek uzel nebo
   * vazbu vypustit (vznik uzlu se tak dá vzít zpět), aniž by se cokoli mazalo. Odmítnuté uložení
   * (kolize digestu) historii vrátí, jak byla.
   */
  async function save(graph: Graph, onApplied?: () => void, stepped?: GraphHistory) {
    if (!view) return;
    const historyBefore = historyRef.current;
    historyRef.current = stepped ?? (sameGraph(view.graph, graph) ? historyBefore : record(historyBefore, view.graph));
    const ticket = ++generation.current;
    const scope = { project, workspace };
    let saved: View;
    try {
      saved = await api<View>("/api/graph", {
        project,
        workspace,
        graph,
        digest: view.digest,
        undo: stepped !== undefined,
      });
    } catch (e) {
      historyRef.current = historyBefore;
      throw e;
    }
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
  const syncView = badgeView(pickVerdict(sync.report, node?.id ?? null));
  // Dashboard procesu na úvodní obrazovce: jména rozsahů bere z grafu, zbytek z echa.
  const syncBoard = dashboardView(sync.report, Object.fromEntries(graph.nodes.map((n) => [n.id, n.name])));
  const edge = graph.edges.find((e) => e.id === selectedEdge);
  const layer = graph.nodes.find((n) => n.id === parent);
  const editable = !!view && !view.readOnly && !busy;
  // Agenti a postupy dostanou adresu karty a jeden otisk stavu: otisk plátna + revize plochy. Když se
  // karta pohne (jiný graf, jiná revize textů a bloků), otisk se změní a záložka Agenti si zadání
  // načte znovu. Panel sám nic nedohledává — jen dostane props; kreslí se jen v zavěšeném panelu.
  const agentNavbarPanel = (
    <AgentNavbar
      state={agentNavbar.state}
      project={project}
      workspace={workspace}
      selectedNodeId={selected}
      refreshKey={(view?.digest ?? "") + ":" + desktop.revision}
      readOnly={!!view?.readOnly || desktop.readOnly || !!(selected && nodeWorkflowOf(desktop.state, selected).done.confirmed)}
      onClose={dock.close}
      onCategory={agentNavbar.category}
      onSearch={agentNavbar.search}
      onTab={agentNavbar.tab}
    />
  );
  /** Krok zpět i vpřed je jen uložení staršího snímku grafu; historii nese `save` v `stepped`. */
  function stepHistory(direction: "undo" | "redo") {
    if (!editable) return;
    const step = direction === "undo" ? undo(historyRef.current, graph) : redo(historyRef.current, graph);
    if (!step) return;
    run(() => save(step.graph, undefined, step.history));
  }
  // Ctrl+Z patří plátnu Editoru: ne v Projektu ani Live Runu, ne nad dokumentací a ne v kreslení,
  // kde má krok zpět Excalidraw. Psaní do polí a textů si zkratku hlídá samo (isTypingTarget).
  useUndoShortcut({
    enabled: editable && environment === "editor" && mode !== "drawing" && !editorDocumentOpen,
    onUndo: () => stepHistory("undo"),
    onRedo: () => stepHistory("redo"),
  });
  const blocks = useMemo(
    () => buildBlockNodes(graph, parent, desktop.state, openBlocks, desktop.readOnly || !!view?.readOnly, blockApi),
    [graph, parent, desktop.state, openBlocks, desktop.readOnly, view?.readOnly],
  );
  // Uzavřená karta: bloky, porty, akce, pravidla i podklady jsou jen ke čtení, dokud ji člověk neotevře.
  const selectedWorkflow = node ? nodeWorkflowOf(desktop.state, node.id) : null;
  const selectedClosed = !!selectedWorkflow?.done.confirmed;
  const libraryReadOnly = !editable || desktop.readOnly || selectedClosed;
  // Uzavřené karty pro seznam vrstev v knihovně (záložka STRÁNKA): panel je jen označí jako skryté.
  const closedNodeIds = useMemo(
    () => new Set(Object.entries(desktop.state.nodes).filter(([, workflow]) => workflow.done?.confirmed).map(([id]) => id)),
    [desktop.state],
  );
  // Vybraný blok pro Editor v zásuvce (panels.drawer === "block"); undefined, dokud stav nedorazí.
  const selectedBlockData = selectedWorkflow?.blocks.find((b) => b.id === selectedBlock);
  const pickerNode = graph.nodes.find((n) => n.id === pipelinePickerFor);
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
  const capabilities = projectCapabilities(project, activeProject);
  const legacyFreeNode = capabilities.legacyFree;
  const legacyFreeSector = modal === "sector" && capabilities.legacyFree;
  const conceptCreate = createOrigin === "concept";
  const requiresTargetSector = modal === "node" && !effectiveSector && !legacyFreeNode && !conceptCreate;
  const requiresModeChoice = !legacyFreeSector && !(modal === "node" && legacyFreeNode && !effectiveSector?.sourceRef) && (modal === "sector" || modal === "node");
  const existingAllowedForNode = modal !== "node" || effectiveSector?.sourceRef?.origin === "existing";
  const purposeReady = conceptCreate ? createPurpose.trim().length > 0 : createOrigin !== "planned" || (modal === "sector" ? createPurpose.trim().length >= 12 : createPurpose.trim().length > 0);
  const pathReady = createOrigin !== "existing" || (existingAllowedForNode && createPath !== null);
  const plannedNodePathReady = createOrigin !== "planned" || modal !== "node" || !createPlannedPath.trim() || effectiveSector?.sourceRef?.origin === "existing" || !!effectiveSector?.sourceRef?.path;
  const createReady = !requiresTargetSector && plannedNodePathReady && (!requiresModeChoice || (createOrigin !== null && purposeReady && pathReady));
  const activeWorkspace = view?.workspaces.find((w) => w.id === workspace);
  const localProject = capabilities.localProject;
  // Komentář ani oblast nemají zdroj ani vazby next/action/rule a nesmí být cílem odkazu: ven z grafu
  // nabízených cílů se proto vylučují.
  const linkTargets = graph.nodes.filter((n) => n.kind !== "comment" && n.kind !== "area").map((n) => ({ id: n.id, name: n.name, kind: n.kind }));
  /** Odkaz i souvislost vedou na tentýž uzel: otevře se jeho vrstva a označí se. */
  function openNode(id: string) {
    const target = graph.nodes.find((n) => n.id === id);
    if (!target) return;
    setParent(target.parentId);
    setSelection(selectNode(target.id));
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
    setSelection(emptySelection());
  }
  function selectProject(id: string, sourceKind?: string) {
    generation.current++;
    setView(null);
    historyRef.current = emptyHistory();
    setProject(id);
    const kind = sourceKind ?? projects.find((p) => p.id === id)?.sourceKind;
    setWorkspace(id === "draft" || isLocalKind(kind) ? "draft" : "main");
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
  /**
   * Dokončený tah na plátně. Z tlačítka bloku (úchyt `block:<blockId>:<portId>`) vznikne vazba
   * `port: "block"` s identitou bloku i portu, z hrany karty klasický `next / action / rule`.
   */
  function connectEdge(connection: BoardConnection) {
    if (!editable) return;
    const created = edgeFromConnection(connection);
    if (!created) return;
    if (graph.edges.some((e) => sameEdge(e, created))) {
      setError("Toto propojení už existuje.");
      return;
    }
    run(() => save({ ...graph, edges: [...graph.edges, created] }));
  }
  /** Nový komentář na aktuální vrstvě, umístěný úhlopříčně za ty už existující. */
  function createComment() {
    if (!editable) return;
    const spot = nextCommentSpot(graph.nodes, parent);
    const created = newComment(parent, spot.x, spot.y);
    run(async () => {
      await save({ ...graph, nodes: [...graph.nodes, created] });
      setSelection(selectNode(created.id));
    });
  }
  /** Nová oblast na aktuální vrstvě, umístěná úhlopříčně za ty už existující. */
  function createArea() {
    if (!editable) return;
    const spot = nextAreaSpot(graph.nodes, parent);
    const created = newArea(parent, spot.x, spot.y);
    run(async () => {
      await save({ ...graph, nodes: [...graph.nodes, created] });
      setSelection(selectNode(created.id));
    });
  }
  /**
   * Položka knihovny puštěná na plátno. Karta (`kind: "card"`) vzniká jedinou cestou, kterou se graf ukládá —
   * přes `save` — takže se rovnou zapíše do historie (Ctrl+Z ji vezme zpátky) a ještě před uložením dosedne
   * mezi pevná tělesa, aby nestála na nikom. Teprve nad hotovou kartou se jedním `desktop.mutate` doplní
   * rozpad položky jako bloky a její musí/nesmí jako pravidla uzlu. Položka `kind: "block"` graf nemění:
   * přidá jeden blok do vybrané karty, a bez výběru se jen řekne, co chybí.
   */
  function dropCatalogItem(itemId: string, x: number, y: number) {
    if (!editable) return;
    const item = itemById(itemId);
    if (!item) return;
    if (item.kind === "block") {
      if (!node || (node.kind !== "node" && node.kind !== "sector")) {
        setError("Nejdřív vyberte kartu.");
        return;
      }
      // Uzavřená karta má obsah jen ke čtení; stejná pojistka jako u bloků kreslených na kartě.
      if (nodeWorkflowOf(desktop.state, node.id).done.confirmed) {
        setError("Karta je uzavřená; blok do ní přidat nelze.");
        return;
      }
      void desktop.mutate(insertBlockFromItem(node.id, item));
      return;
    }
    const dropped = cardFromItem(item, parent, x, y);
    // Otisk nové karty se počítá nad vrstvou, ve které už stojí; ostatní otisky jsou překážky.
    const footprints = layerFootprints({ ...graph, nodes: [...graph.nodes, dropped] }, parent, desktop.state, openBlocks, {});
    const print = footprints.find((f) => f.id === dropped.id);
    const at = print
      ? settleCard(
          dropped,
          print,
          footprints.filter((f) => f.id !== dropped.id),
          graph.nodes.filter((n) => n.parentId === parent && n.kind === "area" && !!n.size),
        )
      : { x: dropped.x, y: dropped.y };
    const created: CanvasNode = { ...dropped, x: at.x, y: at.y };
    run(async () => {
      await save({ ...graph, nodes: [...graph.nodes, created] });
      await desktop.mutate((current) => ({ ...current, nodes: { ...current.nodes, [created.id]: workflowFromItem(item) } }));
      setSelection(selectNode(created.id));
    });
  }
  /**
   * Položka pravého katalogu (postup) puštěná na plátno. Pravidlo, role agenta i pipeline míří do
   * vybrané karty — bez výběru se jen řekne, co chybí, uzavřená karta zůstává jen ke čtení a totéž
   * pravidlo ani tatáž pipeline se nepřidají dvakrát. Workflow jako jediné sahá na graf: sektor
   * dosedne mezi pevná tělesa a uloží se přes `save` i s kartami fází a vazbami `next`, takže ho
   * Ctrl+Z vezme zpátky celý; teprve nad hotovým sektorem doplní jeden `desktop.mutate` stav karet.
   */
  function dropAgentItem(itemId: string, x: number, y: number) {
    if (!editable) return;
    const item = agentItemById(itemId);
    // Položka `info` (kdy sáhnout po hooku či skillu) se netáhne; panel ji ani nenechá zvednout.
    if (!item || item.kind === "info") return;
    if (item.kind === "workflow") {
      const insert = sectorFromWorkflow(item, parent, x, y);
      if (!insert) return;
      // Otisk nového sektoru se počítá nad vrstvou, ve které už stojí; ostatní otisky jsou překážky.
      const footprints = layerFootprints({ ...graph, nodes: [...graph.nodes, insert.sector] }, parent, desktop.state, openBlocks, {});
      const print = footprints.find((f) => f.id === insert.sector.id);
      const at = print
        ? settleCard(
            insert.sector,
            print,
            footprints.filter((f) => f.id !== insert.sector.id),
            graph.nodes.filter((n) => n.parentId === parent && n.kind === "area" && !!n.size),
          )
        : { x: insert.sector.x, y: insert.sector.y };
      const sector: CanvasNode = { ...insert.sector, x: at.x, y: at.y };
      run(async () => {
        await save({
          ...graph,
          nodes: [...graph.nodes, sector, ...insert.children],
          edges: [...graph.edges, ...insert.edges],
        });
        await desktop.mutate((current) => ({ ...current, nodes: { ...current.nodes, ...insert.nodes } }));
        setSelection(selectNode(sector.id));
      });
      return;
    }
    if (!node || (node.kind !== "node" && node.kind !== "sector")) {
      setError("Nejdřív vyberte kartu.");
      return;
    }
    // Uzavřená karta má obsah jen ke čtení; stejná pojistka jako u levé knihovny.
    if (nodeWorkflowOf(desktop.state, node.id).done.confirmed) {
      setError("Karta je uzavřená; postup do ní přidat nelze.");
      return;
    }
    void desktop.mutate(
      item.kind === "action" ? insertActionFromItem(node.id, item) : insertRulesFromItem(node.id, item),
    );
  }
  /** Tažení rámečku oblasti: posune ji i všechny její aktuální členy o stejný vektor. */
  function moveArea(id: string, dx: number, dy: number) {
    if (!editable) return;
    run(() => save({ ...graph, nodes: moveWithMembers(graph.nodes, id, dx, dy) }));
  }
  /**
   * Tahadlo NodeResizer: rámeček je pevné těleso, takže vyžádaný rozměr ještě projde přes `clampAreaResize` —
   * zmenšit se smí jen do chvíle, než by z oblasti vypadl její obsah, a vyrůst jen k první překážce (jiná
   * oblast nebo cizí karta). Teprve ustálený rozměr se uloží.
   */
  function resizeAreaNode(id: string, w: number, h: number) {
    if (!editable) return;
    const area = graph.nodes.find((n) => n.id === id);
    if (!area?.size) return;
    const memberIds = new Set(membersOf(area, graph.nodes).map((n) => n.id));
    const footprints = layerFootprints(graph, area.parentId, desktop.state, openBlocks, {});
    const fitted = clampAreaResize(
      { id, x: area.x, y: area.y, w: area.size.w, h: area.size.h },
      footprints.filter((f) => memberIds.has(f.id)),
      graph.nodes
        .filter((n) => n.parentId === area.parentId && n.kind === "area" && n.id !== id && !!n.size)
        .map((n) => ({ id: n.id, x: n.x, y: n.y, w: n.size!.w, h: n.size!.h })),
      footprints.filter((f) => !memberIds.has(f.id)),
      w,
      h,
    );
    run(() => save({ ...graph, nodes: graph.nodes.map((n) => (n.id === id ? resizeArea(n, fitted.w, fitted.h) : n)) }));
  }
  /**
   * Tlačítko „Srovnat“: srovná celou viditelnou vrstvu podle toku — co spojuje vazba, stojí vedle sebe
   * zleva doprava, co spolu nesouvisí, leží zvlášť, karty v oblasti zůstanou v ní (a rámeček se pod nimi
   * v případě potřeby zvětší) a volné karty se odstěhují pod oblasti. Nové polohy i rozměry uloží naráz.
   */
  function arrangeLayer() {
    if (!editable) return;
    const layerAreas = graph.nodes.filter((n) => n.parentId === parent && n.kind === "area");
    const arranged = arrangeFootprints(
      layerFootprints(graph, parent, desktop.state, openBlocks, {}),
      graph.edges,
      layerAreas,
    );
    const moved = new Map(arranged.nodes.map((p) => [p.id, p]));
    const framed = new Map(arranged.areas.map((a) => [a.id, a]));
    const nodes = graph.nodes.map((n) => {
      const frame = framed.get(n.id);
      if (frame) {
        const sized = frame.w !== n.size?.w || frame.h !== n.size?.h ? resizeArea(n, frame.w, frame.h) : n;
        return frame.x !== sized.x || frame.y !== sized.y ? { ...sized, x: frame.x, y: frame.y } : sized;
      }
      const to = moved.get(n.id);
      return to && (to.x !== n.x || to.y !== n.y) ? { ...n, x: to.x, y: to.y } : n;
    });
    if (nodes.some((n, i) => n !== graph.nodes[i])) run(() => save({ ...graph, nodes }));
  }
  /** Text komentáře opuštěný na plátně nebo v inspektoru. */
  function commentText(nodeId: string, text: string) {
    run(() => save({ ...graph, nodes: graph.nodes.map((n) => (n.id === nodeId ? { ...n, purpose: text } : n)) }));
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
    // Smazání jde mimo `save` a bere s sebou i obsah uzlu: starší snímky grafu by ho jen vzkřísily prázdný.
    historyRef.current = emptyHistory();
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
        setSelection(emptySelection());
        if (parent && result.nodeIds?.includes(parent)) setParent(null);
      }
    }
    setRemoval((current) =>
      current?.digest === preview.digest ? null : current,
    );
  }
  // Úvodní obrazovka má týž rám jako zbytek aplikace, ale bez zavěšených panelů: nemá plátno, kam
  // by se dalo táhnout, ani vybranou kartu, pro kterou by Agenti a postupy něco ukázali.
  if (screen === "home") return <>
    <div className="editor-frame">
      <ProjectHome projects={projects} draftProject={draftProject} projectId={project} jobs={jobs} onChoose={selectProject} onRefresh={bootstrap} onOpen={() => { changeEnvironment("project"); setScreen("canvas"); }} onConnected={() => { changeEnvironment("project"); setScreen("canvas"); }} onRemove={() => requestRemoval("project", project)} />
      <SyncDashboard view={syncBoard} onRefresh={sync.refresh} />
    </div>
    {removal && <RemovalDialog key={removal.digest} preview={removal} onClose={() => setRemoval(null)} onConfirm={confirmRemoval} />}
    <AccountCorner onSettings={() => setAppSettingsOpen(true)} />
    {appSettingsOpen && <SettingsDialog onClose={() => setAppSettingsOpen(false)} surface={{ value: settings, onChange: updateSettings }} />}
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
  // Kreslení má vlastní inspektor (nástroje plátna) mimo model výběru; ostatní režimy jdou přes panelsFor.
  const panels: Panels = mode === "drawing" ? { drawer: null, inspector: "scope" } : panelsFor(selection, mode, !!layer, node?.kind);
  const inspectorShown = panels.inspector !== null;
  return (
    <div className="app desktop-v2 desktop-v3">
      <TopBar
        trailing={<AssistantButton open={assistantOpen} onToggle={() => setAssistantOpen((v) => !v)} />}
        projectNavigation={environment === "project" ? <ProjectMapNavigation value={projectMapKind} onChange={setProjectMapKind}/> : null}
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
      {/* Lišta Editoru se čte zleva jako věta: na co se dívám (záložky módů), z čeho beru (tlačítka
          zavěšených panelů) a vpravo, co s tím dělám (skupiny nástrojů). */}
      {environment === "editor" && <div className="environment-toolbar v3-toolbar" role="toolbar" aria-label="Nástroje Editoru">
        <ModeRail mode={mode} onMode={setMode} editorOnly inactive={editorDocumentOpen} />
        <PanelToggles open={dock.open} onToggle={dock.toggle} />
        <span className="v3-grow" />
        <div className="v3-tool-group" role="group" aria-label="Pohled">
          <button aria-pressed={editorDocumentOpen} onClick={() => setEditorDocumentOpen((open) => !open)}>Dokumentace</button>
        </div>
        {(mode === "structure" || mode === "text") && <div className="v3-tool-group" role="group" aria-label="Tvorba">
          <button type="button" disabled={!editable} onClick={() => open("sector")}>+ Sektor</button>
          <button type="button" className="primary" disabled={!editable} onClick={() => open("node")}>+ Uzel</button>
          <button type="button" disabled={!editable} onClick={createComment}>+ Komentář</button>
          <button type="button" disabled={!editable} onClick={createArea}>+ Oblast</button>
        </div>}
        {mode === "structure" && <div className="v3-tool-group v3-tool-group--shrink" role="group" aria-label="Filtr štítků">
          <TagFilter graph={graph} parent={parent} state={desktop.state} value={tagFilter} onChange={setTagFilter} />
        </div>}
        {mode === "structure" && <div className="v3-tool-group" role="group" aria-label="Rozložení">
          <button type="button" disabled={!editable} onClick={arrangeLayer}>Srovnat</button>
        </div>}
        {/* Se skrytým inspektorem zůstávají nástroje kreslení a mapy dosažitelné v liště. */}
        {!inspectorShown && !editorDocumentOpen && inspectorTools && <div className="v3-tool-group v3-mode-tools" role="group" aria-label="Nástroje pohledu">{inspectorTools}</div>}
      </div>}
      {/* Rám prostředí pod horní lištou a lištou nástrojů: obsah prostředí zabírá celou šířku. V Editoru
          do rámu visí zavěšený panel (Knihovna nebo Agenti a postupy) nad plátnem, ne vedle něj
          (kontrakt docs/rozvrzeni-editoru.md). */}
      <div className="editor-frame">
      {environment === "project" ? <ProjectWorkspace project={project} workspace={workspace} selection={docSelection.value} onChange={docSelection.change} mapKind={projectMapKind}/> :
      <div className={"workspace-shell " + mode + "-mode" + ((mode === "agents" || mode === "map") ? " no-inspector" : "") + " no-context" + (!inspectorShown ? " inspector-hidden" : "") + (environment === "editor" && editorDocumentOpen ? " document-open" : "")}>
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
            {environment === "editor" && mode === "structure" && !editorDocumentOpen && !artifactMapOpen && view && (
                <NodeLibraryDrawer
                  open={panels.drawer !== null}
                  section={library.section}
                  onSection={(section) => setLibrary((l) => showSection(l, section))}
                  // Komentář ani oblast nemají bloky, akce ani podklady: knihovna je nikdy nesmí dostat jako svůj uzel.
                  node={node && node.kind !== "comment" && node.kind !== "area" ? node : null}
                  workflow={selectedWorkflow}
                  rows={selectedWorkflow ? cardBlocks(selectedWorkflow) : []}
                  readOnly={libraryReadOnly}
                  pipelines={pipelineLibrary}
                  edges={graph.edges}
                  project={project}
                  workspace={workspace}
                  onClose={() => setLibrary(closeLibrary)}
                  onAddBlock={(kind) => { if (node && !libraryReadOnly) void desktop.mutate(addBlockOfKind(node.id, kind)); }}
                  onRemoveBlock={(blockId) => { if (node && !libraryReadOnly) void desktop.mutate(removeBlock(node.id, blockId)); }}
                  onAddAction={(pipeline) => { if (node && !libraryReadOnly) void desktop.mutate(addAction(node.id, pipeline)); }}
                  materials={{
                    previewUrl: (material) => (node ? blockApi.current.previewUrl(node.id, material) : null),
                    onMove: (index, delta) => { if (node && !libraryReadOnly) void desktop.mutate(moveMaterial(node.id, index, delta)); },
                    onRemove: (material) => {
                      if (!node || libraryReadOnly) return;
                      const id = node.id;
                      void desktop.mutate(removeMaterial(id, material.id)).then((ok) => { if (ok && material.kind === "upload") blockApi.current.discardUpload(id, material.path); });
                    },
                    onCaption: (id, caption) => { if (node && !libraryReadOnly) void desktop.mutate(captionMaterial(node.id, id, caption)); },
                    onAddRef: (path, caption) => (node && !libraryReadOnly ? desktop.mutate(addMaterial(node.id, materialKindOf(path), path.trim(), caption)) : Promise.resolve(false)),
                    onUpload: async (dataUrl, caption) => {
                      if (!node || libraryReadOnly) return false;
                      const file = await blockApi.current.uploadMaterial(node.id, dataUrl);
                      return file ? desktop.mutate(addMaterial(node.id, "upload", file, caption)) : false;
                    },
                  }}
                  content={panels.drawer === "block" && node && selectedWorkflow && selectedBlockData ? {
                    title: `Blok ${selectedBlockData.number} · ${selectedBlockData.title}`,
                    body: (
                      <BlockDrawerContent
                        desktop={desktop}
                        project={project}
                        workspace={workspace}
                        node={node}
                        workflow={selectedWorkflow}
                        blockId={selectedBlockData.id}
                        linkTargets={linkTargets}
                        disabled={libraryReadOnly}
                        onSelectBlock={(id) => setSelection(selectBlock(node.id, id))}
                        onSelectNode={() => setSelection(selectNode(node.id))}
                        onPickTag={(tag) => setTagFilter((current) => (current === tag ? "" : tag))}
                      />
                    ),
                  } : undefined}
                />
            )}
            {environment === "editor" && editorDocumentOpen ? <WorkspaceDocumentEditor key={JSON.stringify([project, workspace, docSelection.value.sourcePath])} project={project} workspace={workspace} path={docSelection.value.sourcePath} /> : view ? (
              mode === "text" ? (
                <TextWorkspace project={project} workspace={workspace} layer={layer} children={visible} targets={linkTargets} subtab={textSubtab} onSubtab={setTextSubtab} isClosed={(id) => !!nodeWorkflowOf(desktop.state, id).done.confirmed} onEnter={enter} onOpenNode={(id) => { openNode(id); setMode("structure"); }} onAgentTask={requestAgentTask} onTextSaved={() => setTextRevision((value) => value + 1)} refreshKey={(view?.digest ?? "") + ":" + desktop.revision} />
              ) : mode === "agents" ? (
                v3.liveWorkspace ? <div className="v3-live">
                  <nav className="v3-live-tabs" aria-label="Pohled Live Run">
                    <button aria-pressed={liveView === "overview"} onClick={() => setLiveView("overview")}>Přehled a tickety</button>
                    <button aria-pressed={liveView === "runs"} onClick={() => setLiveView("runs")}>Dohled běhů</button>
                    <button aria-pressed={liveView === "processes"} onClick={() => setLiveView("processes")}>Procesy</button>
                  </nav>
                  {liveView === "overview" ? <div className="v3-slot">{v3.liveWorkspace({ project, workspace, nodeId: selected ?? undefined })}</div>
                    : liveView === "processes" ? <ProcessOverview project={project} projectName={projects.find((p) => p.id === project)?.name ?? draftProject?.name ?? project} nodeNames={Object.fromEntries(graph.nodes.map((n) => [n.id, n.name]))} onOpenNode={(id) => { openNode(id); setMode("structure"); }} />
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
                  selectedBlock={selectedBlock}
                  disabled={!editable}
                  selectedEdge={selectedEdge}
                  onSelect={(id) => setSelection(selectNode(id))}
                  onSelectBlock={(nodeId, blockId) => setSelection(selectBlock(nodeId, blockId))}
                  onClear={() => setSelection(clearSelection())}
                  onSelectEdge={(id) => setSelection(selectEdge(id))}
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
                      setSelection(selectNode(created.id));
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
                  onCommentText={commentText}
                  onAreaMove={moveArea}
                  onAreaResize={resizeAreaNode}
                  onConnect={connectEdge}
                  state={desktop.state}
                  blocks={blocks}
                  openBlocks={openBlocks}
                  onTogglePort={togglePort}
                  onBlockMove={(nodeId, port, dx, dy) =>
                    run(() =>
                      save({
                        ...graph,
                        nodes: graph.nodes.map((n) =>
                          n.id === nodeId
                            ? { ...n, blockOffsets: { ...n.blockOffsets, [port]: { dx: Math.round(dx), dy: Math.round(dy) } } }
                            : n,
                        ),
                      }),
                    )
                  }
                  tagFilter={tagFilter}
                  onCatalogDrop={dropCatalogItem}
                  onAgentDrop={dropAgentItem}
                  onTagFilter={(tag) => setTagFilter((current) => (current === tag ? "" : tag))}
                  onCardBlock={(nodeId, event) => {
                    // Uzavřená karta má bloky i porty jen ke čtení; dílek je zamčený, tady je pojistka.
                    if (nodeWorkflowOf(desktop.state, nodeId).done.confirmed) return;
                    if (event.type === "add") void desktop.mutate(addBlock(nodeId));
                    else if (event.type === "move") void desktop.mutate(moveBlock(nodeId, event.blockId, event.delta));
                    else if (event.type === "remove") void desktop.mutate(removeBlock(nodeId, event.blockId));
                    else if (event.type === "text") void desktop.mutate(updateBlock(nodeId, event.blockId, { text: event.text }));
                    else if (event.type === "add-port") void desktop.mutate(addBlockPort(nodeId, event.blockId));
                    else if (event.type === "rename-port") void desktop.mutate(renameBlockPort(nodeId, event.blockId, event.portId, event.label));
                    else if (event.type === "remove-port") void desktop.mutate(removeBlockPort(nodeId, event.blockId, event.portId));
                    else void desktop.mutate(updateBlock(nodeId, event.blockId, { title: event.title }));
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
        {!editorDocumentOpen && panels.inspector !== null && (
          <aside className="inspector" aria-label="Inspektor">
            {panels.inspector === "node" && node ? (<>
              <NodePanel
                key={project + ":" + workspace + ":" + node.id + ":" + view?.digest}
                node={node}
                project={project}
                workspace={workspace}
                readOnly={!!view?.readOnly}
                busy={busy}
                syncView={syncView}
                onCommitSpec={() => run(async () => {
                  await commitSpec(project, workspace, node.id, "zadání " + node.name);
                  sync.refresh();
                })}
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
                graphNodes={linkTargets}
                done={(selectedWorkflow ?? nodeWorkflowOf(desktop.state, node.id)).done}
                onDone={(patch) => { void desktop.mutate(setDone(node.id, patch)); }}
                onPickTag={(tag) => setTagFilter((current) => (current === tag ? "" : tag))}
                onSelectBlock={(id) => setSelection(selectBlock(node.id, id))}
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
            </>) : panels.inspector === "comment" && node ? (
              <CommentPanel
                key={project + ":" + workspace + ":" + node.id + ":" + view?.digest}
                node={node}
                readOnly={!!view?.readOnly}
                busy={busy}
                onSave={(n) =>
                  run(() =>
                    save({
                      ...graph,
                      nodes: graph.nodes.map((old) => (old.id === n.id ? n : old)),
                    }),
                  )
                }
                onDelete={() => requestRemoval("node", node.id)}
              />
            ) : panels.inspector === "area" && node ? (
              <AreaPanel
                key={project + ":" + workspace + ":" + node.id + ":" + view?.digest}
                project={project}
                workspace={workspace}
                node={node}
                readOnly={!!view?.readOnly}
                closed={selectedClosed}
                busy={busy}
                members={membersOf(node, graph.nodes).map((m) => ({ id: m.id, name: m.name, kind: m.kind }))}
                flows={graph.edges
                  .filter((e) => e.port === "flow" && (e.source === node.id || e.target === node.id))
                  .map((e) => {
                    const otherId = e.source === node.id ? e.target : e.source;
                    const other = graph.nodes.find((n) => n.id === otherId);
                    const direction: "in" | "out" = e.target === node.id ? "in" : "out";
                    return { id: e.id, name: other ? areaLabel(other) : otherId, direction };
                  })}
                onSave={(n) =>
                  run(() =>
                    save({
                      ...graph,
                      nodes: graph.nodes.map((old) => (old.id === n.id ? n : old)),
                    }),
                  )
                }
                onOpenNode={openNode}
                onDelete={() => requestRemoval("node", node.id)}
              />
            ) : panels.inspector === "edge" && edge ? (
              <EdgeReportPanel
                key={project + ":" + workspace + ":" + edge.id}
                view={edgeReportView(edge, graph.nodes, nodeWorkflowOf(desktop.state, edge.source))}
                report={reportOf(desktop.state, edge.id)}
                readOnly={!!view?.readOnly || desktop.readOnly}
                busy={busy}
                onChange={(field, value) => { void desktop.mutate(setEdgeReport(edge.id, { [field]: value })); }}
                onDelete={() => requestRemoval("edge", edge.id)}
              />
            ) : panels.inspector === "layer" && layer ? (
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
      </div>}
      {environment === "editor" && dock.open && (
        <PanelDropdown panel={dock.open} label={DOCK_PANELS.find((item) => item.key === dock.open)?.label ?? ""} onClose={dock.close}>
          {dock.open === "library" ? (
            <LibraryNavbar
              state={libraryNavbar.state}
              layerName={layer ? layer.name : "Projekt"}
              nodes={graph.nodes}
              closed={closedNodeIds}
              onTab={libraryNavbar.tab}
              onMode={libraryNavbar.mode}
              onSearch={libraryNavbar.search}
              onCategory={libraryNavbar.category}
              onPageFilter={libraryNavbar.pageFilter}
              onPageSearch={libraryNavbar.pageSearch}
              onToggleGroup={libraryNavbar.group}
              onOpenLayer={openNode}
              onBack={layer ? () => enter(layer.parentId) : undefined}
              onClose={dock.close}
            />
          ) : (
            agentNavbarPanel
          )}
        </PanelDropdown>
      )}
      </div>
      {pickerNode && (
        <PipelinePicker
          nodeName={pickerNode.name}
          onClose={() => setPipelinePickerFor(null)}
          onSelect={(pipeline) => {
            const nodeId = pickerNode.id;
            setPipelinePickerFor(null);
            desktop.mutate(addAction(nodeId, pipeline)).then((ok) => {
              if (!ok) setError(desktop.error || "Akci se nepodařilo uložit.");
            });
          }}
        />
      )}
      <AccountCorner onSettings={() => setAppSettingsOpen(true)} />
      {appSettingsOpen && <SettingsDialog
        onClose={() => setAppSettingsOpen(false)}
        surface={{ value: settings, onChange: updateSettings }}
        project={{
          name: activeProject?.name ?? draftProject?.name ?? "Lokální návrh",
          localProject,
          busy,
          onProjectSettings: () => setScreen("home"),
          onRefresh: () => run(refresh),
          onSync: () => {
            if (window.confirm("Aktualizovat pouze čistou spravovanou kopii ze schváleného upstreamu? Žádný push."))
              run(async () => {
                await api("/api/sync", { project, confirmed: true });
                await bootstrap();
              });
          },
          onRemoveProject: () => requestRemoval("project", project),
        }}
      />}
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
                      setSelection(selectNode(n.id));
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
      {assistantOpen && (
        <AssistantPanel
          context={{ projectId: project, workspace, layerId: parent ?? null, selectedNodeIds: selected ? [selected] : [], environment }}
          onClose={() => setAssistantOpen(false)}
        />
      )}
    </div>
  );
}
