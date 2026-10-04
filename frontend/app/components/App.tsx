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
import { insertBlockFromItem } from "@/editor/component-library/library-catalog/logic/catalog-insert";
import { catalogPlacement, catalogPlan, type CanvasPlanResult } from "@/editor/component-library/library-catalog/logic/catalog-plan";
import { agentItemById } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import { insertActionFromItem, insertRulesFromItem, sectorFromWorkflow } from "@/editor/component-library/agent-catalog/logic/agent-insert";
import EdgeReportPanel from "@/editor/canvas/edge-report/components/EdgeReportPanel";
import { edgeReportView, edgeRoute, reportOf, setEdgeReport } from "@/editor/canvas/edge-report/logic/edge-report-model";
import BlockEditorDrawer from "@/editor/block-editor/components/BlockEditorDrawer";
import LibraryNavbar from "@/layout/library-navbar/components/LibraryNavbar";
import { useLibraryNavbar } from "@/layout/library-navbar/logic/use-library-navbar";
import { useCanvasIndex } from "@/layout/library-navbar/logic/use-canvas-index";
import "@/layout/library-navbar/styles/library-navbar.css";
import AgentNavbar from "@/layout/agent-navbar/components/AgentNavbar";
import { useAgentNavbar } from "@/layout/agent-navbar/logic/use-agent-navbar";
import type { AgentSection } from "@/layout/agent-navbar/logic/agent-navbar";
import "@/layout/agent-navbar/styles/agent-navbar.css";
import MenuButton from "@/layout/panel-dock/components/MenuButton";
import PanelDock from "@/layout/panel-dock/components/PanelDock";
import DockSettings from "@/layout/panel-dock/components/DockSettings";
import { usePanelDock } from "@/layout/panel-dock/logic/use-panel-dock";
import { readLegacySkeletonPreference } from "@/layout/panel-dock/logic/panel-dock";
import { usePanelDrawer } from "@/layout/panel-dock/logic/use-panel-drawer";
import ProfileCard from "@/layout/project-profile/components/ProfileCard";
import { useProjectProfile } from "@/layout/project-profile/logic/use-project-profile";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import "@/editor/component-library/node-library/styles/node-library.css";
import TagFilter from "@/editor/canvas/tag-filter/components/TagFilter";
import ProjectHome from "@/project-setup/components/ProjectHome";
import TextWorkspace, { type TextSubtab } from "@/editor/node-detail/content/components/TextWorkspace";
import type { AgentTaskRequest } from "@/editor/llm-control/editor-context/components/context-actions";
import TaskHandoff from "@/editor/llm-control/editor-context/components/TaskHandoff";
import SkeletonActions from "@/editor/skeleton/components/SkeletonActions";
import { appendSkeleton } from "@/editor/skeleton/logic/skeleton";
import TopBar from "@/layout/top-bar/components/TopBar";
import AssistantButton from "@/layout/assistant-panel/components/AssistantButton";
import AssistantPanel from "@/layout/assistant-panel/components/AssistantPanel";
import "@/layout/assistant-panel/styles/assistant-panel.css";
import ModeRail from "@/layout/mode-rail/components/ModeRail";
import EnvironmentSwitch, { type Environment } from "@/layout/environment-switch/components/EnvironmentSwitch";
import ProjectWorkspace from "@/project/workspace/components/ProjectWorkspace";

import {ProjectMapNavigation, type ProjectMapKind} from "@/project/shell/components/ProjectLayout";
import { readProjectView } from "@/project/shell/logic/project-view";
import { architectureEditorId } from "@/project/architecture-editor/logic/editor-model";
import { domainForNode } from "@/project/architecture-editor/logic/domain-model";
import WorkspaceDocumentEditor from "@/project/workspace/components/WorkspaceDocumentEditor";
import CreateDialog from "@/editor/canvas/create-dialog/components/CreateDialog";
import type { CreateResult } from "@/editor/canvas/create-dialog/logic/create-form";
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
import { catalogProfile, isLocalKind, profileUnset, projectCapabilities } from "@/shared/project-capabilities/logic/project-capabilities";
import "@/layout/shell/styles/workspace-modes.css";
import AccountCorner from "@/layout/account-corner/components/AccountCorner";
import ProcessOverview from "@/live-run/processes/components/ProcessOverview";
import SettingsDialog from "@/settings/components/SettingsDialog";
import "@/design-tokens/styles/theme-tokens.css";
import NodePanel, { type NodeTab } from "@/editor/node-detail/components/NodePanel";
import { badgeView, pickVerdict } from "@/editor/node-detail/sync-badge/logic/sync-badge";
import { commitSpec, saveNodeSpec } from "@/shared/desktop-state/logic/api";
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
  type NodeSpec,
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
  const [projectMapKind,setProjectMapKind] = useState<ProjectMapKind>(() => readProjectView(initial.get("projectView")));
  const lastEditorMode = useRef<WorkspaceMode>(mode === "agents" ? "structure" : mode);
  function setMode(next: WorkspaceMode) {
    setEditorDocumentOpen(false);
    // Jiný mód = jiný pohled na vrstvu; šuplík z minulého pohledu by jen zakrýval plátno.
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
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [nodeTab, setNodeTab] = useState<NodeTab>("spec");
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
  // Knihovna (levý navbar): jedno rozhraní pro celou aplikaci — stav i preference drží hook,
  // ukládá se pod jediným klíčem `opora:library-navbar:v1`, nikdy s klíčem projektu.
  const [legacyStructure] = useState(readLegacySkeletonPreference);
  const libraryNavbar = useLibraryNavbar(legacyStructure ? "page" : undefined);
  const [catalogNotice, setCatalogNotice] = useState("");
  const catalogInsertLock = useRef(false);
  const [catalogReveal, setCatalogReveal] = useState<{ id: string; scope: string; nonce: number } | null>(null);
  const catalogRevealSequence = useRef(0);
  useEffect(() => {
    setCatalogReveal((current) => current?.scope === project + workspace + parent ? current : null);
  }, [project, workspace, parent]);
  // Menu Editoru (docs/menu-a-katalog.md, část A): ☰ vysune u levého okraje lištu ikon a vedle ní
  // panel sekce (Knihovna, Agenti, Postupy, Nastavení), jen v Editoru. Otevřenost je jen v paměti
  // sezení, poslední sekce se pamatuje jednou pro aplikaci; zkratky Ctrl+Shift+, / Ctrl+Shift+.
  // a Esc drží hook. Úvodní obrazovka menu nekreslí, proto tam zkratky nic nepřepínají.
  const dock = usePanelDock(environment === "editor" && screen === "canvas");
  // Filtr „Pro tento projekt / Vše“ je preference aplikace, „Mimo profil · zobrazit“ jen paměť
  // sezení. Profil patří projektu: načte se z /api/project-settings při otevření sekce a ukládá ho
  // jen App s očekávanou revizí.
  const drawer = usePanelDrawer();
  const projectProfile = useProjectProfile(project, dock.section);
  const profile = catalogProfile(projectProfile.snapshot?.settings ?? null);
  // Agenti a Postupy: dvě sekce menu nad jedním katalogem. Stav drží týž druh hooku pod jediným
  // klíčem `opora:agent-navbar:v1`. Samotné složení panelu čeká níž, až bude znát plátno a plochu
  // (`view`, `desktop`) — záložka Vybraná karta si podle nich načítá zadání vybrané karty.
  const agentNavbar = useAgentNavbar();
  // Přechod na jinou vrstvu (Zanořit, drobečková navigace) vrací stránku Text zpět na Uživatele.
  useEffect(() => { setTextSubtab("user"); }, [parent]);
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
  const [url, setUrl] = useState("");
  const [approved, setApproved] = useState(false);
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
  // Zápis asistenta (docs/asistent.md §6.2) jde přes backend z jiného procesu. Po ohlášení z panelu
  // se graf i stav Desktop v3 načtou znovu stejnými cestami jako při otevření projektu, jen bez
  // vyprázdnění plátna (Board přenese `measured`, fokus v kartách zůstane). Když právě běží uložení
  // grafu, reload počká na jeho konec; o souběh se pak postará digest (stávající hláška konfliktu).
  // Historie kroků zpět se vyprázdní jako při otevření: krok zpět by jinak zápis asistenta smazal.
  const savingGraph = useRef(0);
  const canvasReloadQueued = useRef(false);
  function reloadCanvas() {
    if (savingGraph.current > 0) { canvasReloadQueued.current = true; return; }
    canvasReloadQueued.current = false;
    desktop.reload();
    if (screen !== "canvas") return;
    const scope = { ...activeScope.current };
    const g = ++generation.current;
    api<View>(`/api/view?project=${encodeURIComponent(scope.project)}&workspace=${encodeURIComponent(scope.workspace)}`)
      .then((v) => {
        if (g !== generation.current || scope.project !== activeScope.current.project || scope.workspace !== activeScope.current.workspace) return;
        historyRef.current = emptyHistory();
        setView(v);
      })
      .catch((e) => { if (g === generation.current) setError(String(e)); });
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
      // Zavřený pop-up tvorby zahodí i svůj rozepsaný formulář (výběr ve stromu platí jen pro tento scope).
      setRemoval(null); lastLoadedScope.current = nextScope;
    }
    setError("");
    if (screen === "canvas") refresh(); else generation.current++;
  }, [project, workspace, screen]);
  useEffect(() => {
    const q = new URLSearchParams({ project, workspace, mode, screen, environment });
    if (parent) q.set("layer", parent);
    if (selected) q.set("node", selected);
    if (wireframeMode) q.set("wireframe", "1");
    q.set("projectView", projectMapKind);
    const currentRoute = new URLSearchParams(location.search);
    const switchedScope = (currentRoute.has("project") && currentRoute.get("project") !== project) || (currentRoute.has("workspace") && currentRoute.get("workspace") !== workspace);
    // The standalone editor owns these fields. Preserve invalid explicit IDs for its validation.
    if (!switchedScope || currentRoute.get("editorId") === architectureEditorId(project, workspace, currentRoute.get("domainId") || undefined)) {
      for (const name of ["editorId", "domainId", "pageId", "architectureNode"]) {
        if (currentRoute.has(name)) q.set(name, currentRoute.get(name)!);
      }
    }
    history.replaceState(null, "", "/?" + q);
  }, [project, workspace, parent, selected, mode, screen, wireframeMode, environment, projectMapKind]);
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
    savingGraph.current++;
    try {
      await saveGraph(graph, onApplied, stepped);
    } finally {
      savingGraph.current--;
      if (savingGraph.current === 0 && canvasReloadQueued.current) reloadCanvas();
    }
  }
  async function saveGraph(graph: Graph, onApplied?: () => void, stepped?: GraphHistory) {
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
  // Sekce Agenti a Postupy dostanou adresu karty a jeden otisk stavu: otisk plátna + revize plochy.
  // Když se karta pohne (jiný graf, jiná revize textů a bloků), otisk se změní a záložka Vybraná karta
  // si zadání načte znovu. Panel sám nic nedohledává — jen dostane props; kreslí se jen v menu.
  const agentNavbarPanel = (section: AgentSection) => (
    <AgentNavbar
      section={section}
      state={agentNavbar.state}
      project={project}
      workspace={workspace}
      selectedNodeId={selected}
      refreshKey={(view?.digest ?? "") + ":" + desktop.revision}
      readOnly={!!view?.readOnly || desktop.readOnly || !!(selected && nodeWorkflowOf(desktop.state, selected).done.confirmed)}
      profile={profile}
      scope={drawer.scope}
      showOutside={drawer.showOutside}
      onScope={drawer.setScope}
      onToggleOutside={drawer.toggleOutside}
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
  // Hledání ve STRÁNCE Knihovny jde přes jednotný index plátna (docs/kontext-karet-a-index.md §5):
  // jen s otevřenou záložkou a neprázdným dotazem; nová revize grafu nebo plochy dotaz zopakuje.
  // Bez odpovědi (načítá se, selhalo) panel filtruje lokálně podle názvu jako dřív.
  const pageMatches = useCanvasIndex(
    project,
    workspace,
    libraryNavbar.state.pageQuery,
    environment === "editor" && dock.rail && dock.section === "library" && libraryNavbar.state.tab === "page",
    `${view?.digest ?? ""}:${desktop.revision}`,
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
  const currentPage = [...ancestors].reverse().find((n) => n.site?.kind === "page") ?? null;
  const availableSectors = graph.nodes.filter((n) => n.kind === "sector");
  const activeProject = project === "draft" ? draftProject : projects.find((p) => p.id === project);
  // Volné uzly patří jen historickému vestavěnému draftu; připojený projekt
  // musí nejdřív dostat sektor, aby nevznikl zdroj bez vlastního kontextu.
  const capabilities = projectCapabilities(project, activeProject);
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
      {
        project,
        workspace,
        layer: parent,
        nodeId,
        nodeName: target?.name ?? nodeId,
        source,
        text,
        requestedAt: new Date().toISOString(),
      },
    );
  }
  function openDomainMap(id: string | null) {
    const route = new URLSearchParams(location.search);
    route.set("editorId", architectureEditorId(project, workspace, id ?? undefined));
    if (id) route.set("domainId", id); else route.delete("domainId");
    route.delete("pageId"); route.delete("architectureNode");
    history.replaceState(null, "", "/?" + route);
    setProjectMapKind("architecture");
    changeEnvironment("project");
  }
  function openArchitectureNode(id: string) {
    const scope = { project, workspace };
    void run(async () => {
      const fresh = await api<View>(`/api/view?${new URLSearchParams(scope)}`);
      if (activeScope.current.project !== scope.project || activeScope.current.workspace !== scope.workspace) return;
      const target = fresh.graph.nodes.find((candidate) => candidate.id === id);
      if (!target) throw new Error("Prvek již neexistuje. Obnovte mapu projektu.");
      generation.current++;
      historyRef.current = emptyHistory(); setView(fresh); desktop.reload();
      setMode("structure"); setParent(target.site?.kind === "page" ? target.id : target.parentId); setSelection(selectNode(id));
      setNodeTab("spec"); setTagFilter(""); dock.close();
    });
  }
  async function addSkeleton(parentId: string | null, names: string[], kind: "node" | "sector") {
    if (!editable || busy || savingGraph.current > 0) throw new Error("Úpravy nejsou právě dostupné. Otevřete pracovní prostor nebo počkejte na uložení.");
    const next = appendSkeleton(graph, parentId, names, kind, () => crypto.randomUUID());
    if (next === graph) return;
    const first = next.nodes[graph.nodes.length];
    let failure: unknown;
    await run(async () => {
      try {
        await save(next, () => { setParent(first.parentId); setSelection(selectNode(first.id)); });
      } catch (e) { failure = e; throw e; }
    });
    if (failure) throw failure;
  }
  // Pop-up tvorby si rozepsaný formulář drží sám; nové otevření ho vykreslí znovu a tím vyčistí.
  const [createSequence, setCreateSequence] = useState(0);
  function open(kind: typeof modal) {
    setModal(kind);
    setApproved(false);
    setCreateSequence((value) => value + 1);
  }
  /**
   * Hotový uzel z pop-upu tvorby: uloží se graf a teprve potom zadání sektoru přes existující spec API
   * (nová karta má revizi zadání 0). Ukládá jen App; dialog o API nic neví.
   */
  function createFromDialog(result: CreateResult) {
    const submitScope = { ...activeScope.current };
    run(async () => {
      await save({ ...graph, nodes: [...graph.nodes, result.node] }, () => {
        if (
          activeScope.current.project !== submitScope.project ||
          activeScope.current.workspace !== submitScope.workspace
        ) return;
        setParent(result.node.parentId);
        setSelection(selectNode(result.node.id));
        setModal(null);
      });
      if (result.spec) await saveNodeSpec(submitScope.project, submitScope.workspace, result.node.id, 0, result.spec);
    });
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
  /** Karta (uzel nebo sektor), na kterou se pustilo; komentář, oblast i prázdné plátno vrací `null`. */
  function dropCard(targetId: string | null): CanvasNode | null {
    const hit = targetId ? graph.nodes.find((n) => n.id === targetId) : undefined;
    return hit && (hit.kind === "node" || hit.kind === "sector") ? hit : null;
  }
  /** Do uzavřené karty se nic nevkládá (obsah je jen ke čtení); řekne to a vrátí `false`. */
  function openForDrop(card: CanvasNode): boolean {
    if (!nodeWorkflowOf(desktop.state, card.id).done.confirmed) return true;
    setError("Karta je uzavřená; vložit do ní nelze.");
    return false;
  }
  /** Nová karta nebo sektor dosedne mezi pevná tělesa vrstvy, aby nestála na nikom. */
  function settleDropped(dropped: CanvasNode): CanvasNode {
    // Otisk se počítá nad vrstvou, ve které už stojí; ostatní otisky jsou překážky.
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
    return { ...dropped, x: at.x, y: at.y };
  }
  /** Catalog instances save graph, canonical specification and context atomically. */
  async function insertCatalogComponent(itemId: string, targetId: string | null, point?: { x: number; y: number }) {
    if (!editable || !view || desktop.readOnly || desktop.loading || savingGraph.current || catalogInsertLock.current) return;
    const item = itemById(itemId);
    if (!item) { setError("Prvek již není v katalogu."); return; }
    const scope = { project, workspace };
    const isCurrent = () => activeScope.current.project === scope.project && activeScope.current.workspace === scope.workspace;
    catalogInsertLock.current = true;
    setCatalogNotice("");
    savingGraph.current++;
    let accepted = false;
    try {
      await run(async () => {
        try {
          const placement = catalogPlacement(graph.nodes, parent, targetId, point);
          const target = placement.parentId ? graph.nodes.find((candidate) => candidate.id === placement.parentId) : null;
          if (target && closedNodeIds.has(target.id)) throw new Error("Cílová karta je uzavřená; vložit do ní nelze.");
          const plan = catalogPlan(item, placement);
          const saved = await api<CanvasPlanResult>("/api/canvas-plan", { ...scope, digest: view.digest, plan });
          accepted = saved.ok && !saved.dryRun;
          const id = saved.refs?.component;
          if (!accepted || !id) throw new Error("Server nepotvrdil vytvoření komponenty.");
          const query = new URLSearchParams(scope);
          const [fresh, spec] = await Promise.all([
            api<View>(`/api/view?${query}`),
            api<NodeSpec>(`/api/node-spec?${query}&node=${encodeURIComponent(id)}`),
          ]);
          const created = fresh.graph.nodes.find((candidate) => candidate.id === id);
          if (!created || spec.fields.goal !== item.purpose || spec.fields.acceptance !== item.done.join("\n")) {
            throw new Error("Uloženou komponentu nebo její zadání se nepodařilo ověřit. Obnovte plátno před dalším vložením.");
          }
          if (!isCurrent()) return;
          generation.current++;
          historyRef.current = fresh.digest === saved.digest ? record(historyRef.current, view.graph) : emptyHistory();
          setView(fresh);
          desktop.reload();
          setEditorDocumentOpen(false);
          setEditorMode("structure");
          setTagFilter("");
          setParent(created.parentId);
          setSelection(selectNode(created.id));
          setCatalogReveal({ id: created.id, scope: project + workspace + created.parentId, nonce: ++catalogRevealSequence.current });
          setCatalogNotice(`Vloženo: ${created.name}. Zadání je uložené v kartě.`);
        } catch (e) {
          const message = (accepted ? "Zápis byl přijat, ale načtení výsledku selhalo. " : "") + (e instanceof Error ? e.message : String(e));
          if (isCurrent()) setCatalogNotice(message);
          throw new Error(message);
        }
      });
    } finally {
      catalogInsertLock.current = false;
      savingGraph.current--;
      if (savingGraph.current === 0 && canvasReloadQueued.current) reloadCanvas();
    }
  }
  function dropCatalogItem(itemId: string, x: number, y: number, targetId: string | null) {
    void insertCatalogComponent(itemId, targetId, { x, y });
  }
  /** Legacy content insertion is an explicit action, never the default drop behavior. */
  function insertCatalogBlock(itemId: string) {
    if (!editable || desktop.readOnly || desktop.loading || selectedClosed) return;
    const item = itemById(itemId);
    const target = dropCard(selected);
    if (!item || !target) return;
    void run(async () => {
      const ok = await desktop.mutate(insertBlockFromItem(target.id, item));
      if (!ok) throw new Error("Blok se nepodařilo uložit. Obnovte stav a zkuste to znovu.");
      setCatalogNotice(`Blok přidán do karty „${target.name}“.`);
    });
  }
  /**
   * Položka Agentů a Postupů puštěná na plátno. Hranice, role agenta, pipeline i hook míří do karty pod
   * ukazatelem, jinak do vybrané karty; bez obojího se jen řekne, co chybí. Totéž pravidlo ani tatáž
   * pipeline se nepřidají dvakrát. Workflow jako jediné sahá na graf: sektor dosedne mezi pevná tělesa
   * a uloží se přes `save` i s kartami fází a vazbami `next`; teprve pak doplní `desktop.mutate` stav karet.
   */
  function dropAgentItem(itemId: string, x: number, y: number, targetId: string | null) {
    if (!editable) return;
    const item = agentItemById(itemId);
    // Položka `info` (kdy sáhnout po skillu) se netáhne; panel ji ani nenechá zvednout.
    if (!item || item.kind === "info") return;
    if (item.kind === "workflow") {
      const insert = sectorFromWorkflow(item, parent, x, y);
      if (!insert) return;
      const sector = settleDropped(insert.sector);
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
    const target = dropCard(targetId) ?? dropCard(node?.id ?? null);
    if (!target) {
      setError("Pusťte položku na kartu.");
      return;
    }
    if (!openForDrop(target)) return;
    void desktop.mutate(
      item.kind === "action" ? insertActionFromItem(target.id, item) : insertRulesFromItem(target.id, item),
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
    if (kind === "node" && graph.nodes.find((candidate) => candidate.id === target)?.site) {
      openDomainMap(domainForNode(graph, target)?.id ?? null);
      return;
    }
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
  // Úvodní obrazovka má týž rám jako zbytek aplikace, ale bez šuplíku Knihovna/Agenti: nemá plátno, kam
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
  const productTreeProps = { nodes: graph.nodes, workspace, readOnly: !view || view.readOnly || desktop.readOnly, busy: busy || desktop.loading,
    onOpenDomain: openDomainMap, onChooseWorkspace: () => {
      if (localProject) { setWorkspace("draft"); enter(null); }
      else if (view?.workspaces.length) { setWorkspace(view.workspaces[0].id); enter(null); }
      else open("workspace");
    } };
  const catalogPanel = <LibraryNavbar
    state={libraryNavbar.state} nodes={graph.nodes} closed={closedNodeIds} pageMatches={pageMatches}
    profile={profile} scope={drawer.scope} showOutside={drawer.showOutside}
    onScope={drawer.setScope} onToggleOutside={drawer.toggleOutside}
    onTab={libraryNavbar.tab} onSearch={libraryNavbar.search} onItem={libraryNavbar.item}
    onPageFilter={libraryNavbar.pageFilter} onPageSearch={libraryNavbar.pageSearch} onToggleGroup={libraryNavbar.group}
    onOpenLayer={(id) => { setEditorDocumentOpen(false); setEditorMode("structure"); setTagFilter(""); openNode(id); }}
    structureActions={<SkeletonActions key={project + ":" + workspace} nodes={graph.nodes} selected={selected}
      readOnly={!editable || desktop.readOnly || selectedClosed} busy={busy} onAdd={addSkeleton}
      onEnter={(id) => { setEditorDocumentOpen(false); setEditorMode("structure"); setTagFilter(""); enter(id); }} />}
    insertion={{ disabled: !editable || desktop.readOnly || desktop.loading || ancestors.some((ancestor) => closedNodeIds.has(ancestor.id)),
      layerName: layer?.name ?? "kořen návrhu", blockTargetName: !selectedClosed ? dropCard(selected)?.name ?? null : null,
      notice: catalogNotice, onInsert: (id) => { void insertCatalogComponent(id, null); }, onInsertBlock: insertCatalogBlock }}
  />;
  return (
    <div className="app desktop-v2 desktop-v3">
      <TopBar
        onHome={() => setScreen("home")}
        trailing={<AssistantButton open={assistantOpen} busy={assistantBusy} onToggle={() => setAssistantOpen((v) => !v)} />}
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
      {/* Lišta Editoru se čte zleva jako věta: odkud beru (☰ menu), na co se dívám (záložky módů)
          a vpravo, co s tím dělám (skupiny nástrojů). */}
      {environment === "editor" && <div className="environment-toolbar v3-toolbar" role="toolbar" aria-label="Nástroje Editoru">
        <MenuButton open={dock.rail} onToggle={dock.toggleMenu} />
        <ModeRail mode={mode} onMode={setMode} editorOnly inactive={editorDocumentOpen} />
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
          z levého okraje rámu vyjíždí šuplík (Knihovna nebo Agenti a postupy) nad plátnem, ne vedle
          něj (kontrakt docs/suplik-a-profil.md). */}
      <div className="editor-frame">
      {environment === "project" ? <ProjectWorkspace project={project} workspace={workspace} selection={docSelection.value} onChange={docSelection.change} mapKind={projectMapKind} projectName={projects.find((p) => p.id === project)?.name ?? draftProject?.name} product={productTreeProps} onOpenEditor={openArchitectureNode} onGraphChanged={() => { reloadCanvas(); desktop.reload(); }}/> :
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
            {currentPage && <button type="button" data-testid="page-assignment" title={`Zadání stránky ${currentPage.name}`}
              onClick={() => { setSelection(selectNode(currentPage.id)); setNodeTab("spec"); }}>Zadání stránky: {currentPage.name}</button>}
            {mode === "structure" && outsideLinks > 0 && (
              <button type="button" className="quiet" onClick={() => setMode("map")}>
                Mapa architektury projektu
              </button>
            )}

          </div>}
          <div className="canvas-surface">
            {environment === "editor" && mode === "structure" && panels.drawer === "block" && !editorDocumentOpen && !artifactMapOpen && view && node && selectedWorkflow && selectedBlockData && (
                <BlockEditorDrawer title={`Blok ${selectedBlockData.number} · ${selectedBlockData.title}`}
                  onClose={() => setSelection(selectNode(node.id))}>
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
                </BlockEditorDrawer>
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
                  reveal={catalogReveal}
                  onRevealed={(nonce) => setCatalogReveal((current) => current?.nonce === nonce ? null : current)}
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
                onAgentTask={() => requestAgentTask(node.id, "", "canvas")}
                workflow={v3.nodeWorkflow?.({ project, workspace, nodeId: node.id })}
                resultRevision={desktop.revision}
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
                route={edgeRoute(edge, graph.nodes)}
                onChange={(field, value) => { void desktop.mutate(setEdgeReport(edge.id, { [field]: value })); }}
                onDue={(due) => { void desktop.mutate(setEdgeReport(edge.id, { due })); }}
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
      {environment === "editor" && dock.rail && (
        <PanelDock
          section={dock.section}
          onSelect={dock.select}
          onClose={dock.close}
        >
          {dock.section === "settings" ? (
            <DockSettings
              scope={drawer.scope}
              filtering={!profileUnset(profile)}
              onScope={drawer.setScope}
              profileCard={projectProfile.snapshot ? (
                <ProfileCard
                  name={projectProfile.snapshot.project.name || activeProject?.name || ""}
                  profile={profile}
                  saving={projectProfile.saving}
                  error={projectProfile.error}
                  onSave={(draft) => { void projectProfile.save(draft); }}
                  onReload={projectProfile.reload}
                />
              ) : (
                <p className="dock-settings__hint">{projectProfile.error || "Načítám profil projektu…"}</p>
              )}
            />
          ) : dock.section === "agents" || dock.section === "flows" ? (
            agentNavbarPanel(dock.section)
          ) : dock.section === "library" ? (
            catalogPanel
          ) : null}
        </PanelDock>
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
      {agentTask && <TaskHandoff key={JSON.stringify([agentTask.project, agentTask.workspace, agentTask.nodeId, agentTask.requestedAt])}
        request={agentTask} onClose={() => setAgentTask(null)} onSaved={() => { desktop.reload(); reloadCanvas(); }} />}
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
              <CreateDialog
                key={createSequence}
                kind={modal}
                project={project}
                workspace={workspace}
                parent={parent}
                nodes={graph.nodes}
                ancestorSector={ancestorSector}
                sectors={availableSectors}
                legacyFree={capabilities.legacyFree}
                busy={busy}
                onCreate={createFromDialog}
              />
            )}
          </section>
        </div>
      )}
      <AssistantPanel
        open={assistantOpen}
        context={{ projectId: project, workspace, layerId: parent ?? null, selectedNodeIds: selected ? [selected] : [], environment }}
        onClose={() => setAssistantOpen(false)}
        onBusyChange={setAssistantBusy}
        onCanvasWritten={reloadCanvas}
      />
    </div>
  );
}
