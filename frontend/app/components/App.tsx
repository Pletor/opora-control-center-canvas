import { saveCanvasGraph } from "@/editor/canvas/board/logic/graph-positions";
import { fetchState } from "@/shared/desktop-state/logic/api";
import { confirmSector } from "@/editor/canvas/sector-proposals/logic/sector-proposals";
import type { StateResponse } from "@/shared/desktop-state/logic/types";
import { useEffect, useMemo, useRef, useState, lazy, Suspense } from "react";
import "@/ui-kit/panel-frame/styles/panels.css";
import Board from "@/editor/canvas/board/components/Board";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import { useLeases } from "@/editor/canvas/node-card/logic/use-leases";
import { useSourceStatus } from "@/editor/canvas/node-card/logic/use-source-status";
import { closeCardAfterMerge, confirmProposal } from "@/editor/canvas/node-card/logic/completion-proposals";
import { addAction, buildBlockNodes, closeOpen, materialPreviewUrl, toggleOpen, type BlockApi, type BlockPort, type OpenBlocks } from "@/editor/workflow/blocks/logic/block-model";
import PipelinePicker from "@/editor/workflow/pipeline-picker/components/PipelinePicker";
import { openIdeas } from "@/editor/node-detail/ideas/logic/ideas-model";
import { addBlock, addBlockPort, moveBlock, removeBlock, removeBlockPort, renameBlockPort, decideBlockPort, updateBlock } from "@/editor/node-detail/tree/logic/tree-model";
import { edgeFromConnection, sameEdge, type BoardConnection } from "@/editor/canvas/board/logic/board-model";
import { emptyHistory, record, recordRemoval, redo, sameGraph, undo, type GraphHistory } from "@/editor/canvas/history/logic/graph-history";
import HistoryButtons from "@/editor/canvas/history/components/HistoryButtons";
import { SaveScopeProvider } from "@/shared/hooks/components/save-scope-context";
import { useSaveScope, useSaveParticipant, flushSaveScope, invalidateSavedScope, trackSaveWrite, waitForSaveWrites, saveScopeEntries } from "@/shared/hooks/logic/save-coordinator";
import { orphanedPendingEdits, flushOrphanedPendingEdits } from "@/shared/hooks/logic/use-pending-edits";
import { usePolling } from "@/shared/hooks/logic/use-polling";
import { keepSame } from "@/shared/hooks/logic/same-response";
import SaveVersionsTools from "@/editor/canvas/save-versions/components/SaveVersionsTools";
import ActivityLogTools from "@/editor/canvas/activity-log/components/ActivityLogTools";
import { useCanvasVersions } from "@/editor/canvas/save-versions/logic/use-canvas-versions";
import { useSaveShortcut } from "@/editor/canvas/save-versions/logic/use-save-shortcut";
import { versionAuthor } from "@/editor/canvas/save-versions/logic/save-versions";
import { deletableSelection, selectionPlan } from "@/editor/canvas/board/logic/box-selection";
import { useUndoShortcut } from "@/editor/canvas/history/logic/undo-shortcut";
import { arrangeLayer as arrangeFootprints, layerFootprints, type ArrangeOptions } from "@/editor/canvas/board/logic/layout-model";
/** Rozestupy „Srovnat“: dost místa na obálky předávek na vazbách a oblasti se odpuzují jako magnety. */
const ARRANGE_SPACING: ArrangeOptions = { gapX: 160, gapY: 72, areaGap: 160 };
import { clampAreaResize } from "@/editor/canvas/board/logic/solid-bodies";
import EdgeReportPanel from "@/editor/canvas/edge-report/components/EdgeReportPanel";
import { edgeReportView, edgeRoute, reportOf, setEdgeReport } from "@/editor/canvas/edge-report/logic/edge-report-model";
import BlockPanelDrawer from "@/editor/block-panel/components/BlockPanelDrawer";
import StructurePanel from "@/layout/structure-panel/components/StructurePanel";
import { useStructurePanel } from "@/layout/structure-panel/logic/use-structure-panel";
import { useCanvasIndex } from "@/layout/structure-panel/logic/use-canvas-index";
import CardBrief from "@/layout/card-brief/components/CardBrief";
import MenuButton from "@/layout/panel-dock/components/MenuButton";
import PanelDock from "@/layout/panel-dock/components/PanelDock";
import DockSettings from "@/layout/panel-dock/components/DockSettings";
import { usePanelDock } from "@/layout/panel-dock/logic/use-panel-dock";
import ProfileCard from "@/layout/project-profile/components/ProfileCard";
import { useProjectProfile } from "@/layout/project-profile/logic/use-project-profile";
import { useAgentAutonomy } from "@/shared/agent-autonomy/logic/use-agent-autonomy";
import AgentAutonomyBadge from "@/shared/agent-autonomy/components/AgentAutonomyBadge";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import { withStages, type PipelineWriteResponse } from "@/shared/desktop-state/logic/slim-writes";
import "@/editor/component-library/node-library/styles/node-library.css";
import TagFilter from "@/editor/canvas/tag-filter/components/TagFilter";
import ProjectHome from "@/project-setup/components/ProjectHome";
import StoryboardWorkspace from "@/editor/storyboard/components/StoryboardWorkspace";
import TextWorkspace, { type TextSubtab } from "@/editor/node-detail/content/components/TextWorkspace";
import type { AgentTaskRequest } from "@/editor/llm-control/editor-context/components/context-actions";
import TaskHandoff from "@/editor/llm-control/editor-context/components/TaskHandoff";
import SkeletonActions from "@/editor/skeleton/components/SkeletonActions";
import { appendSkeleton } from "@/editor/skeleton/logic/skeleton";
import TopBar from "@/layout/top-bar/components/TopBar";
import AssistantButton from "@/layout/assistant-panel/components/AssistantButton";
import AssistantPanel from "@/layout/assistant-panel/components/AssistantPanel";
import { sendHeartMessage, type HeartRequest } from "@/layout/heart-channel/logic/heart-api";
import type { CardRequest } from "@/project/architecture-editor/live-status/logic/session-state";
import type { ArchitectureLiveProps } from "@/project/architecture-editor/components/ArchitectureEditor";
import "@/layout/assistant-panel/styles/assistant-panel.css";
import ModeRail from "@/layout/mode-rail/components/ModeRail";
import EnvironmentSwitch from "@/layout/environment-switch/components/EnvironmentSwitch";
import { resolveInitialModeEnvironment, type Environment } from "@/layout/environment-switch/logic/environment";
import ProjectWorkspace from "@/project/workspace/components/ProjectWorkspace";

import {ProjectMapNavigation, type ProjectMapKind} from "@/project/shell/components/ProjectLayout";
import { readProjectView } from "@/project/shell/logic/project-view";
import { architectureEditorId } from "@/project/architecture-editor/logic/editor-model";
import { domainForNode, worktreeDomainChoice } from "@/project/architecture-editor/logic/domain-model";
import CreateDialog from "@/editor/canvas/create-dialog/components/CreateDialog";
import type { CreateResult } from "@/editor/canvas/create-dialog/logic/create-form";
import { useWorkspaceSelection } from "@/shared/selection/logic/workspace-selection";
import { clearSelection, emptySelection, panelsFor, selectBlock, selectCardTrail, selectEdge, selectNode, type Panels, type Selection } from "@/app/logic/selection-model";
import "@/layout/shell/styles/desktop-workspaces.css";

import ScopeContext from "@/shared/contexts/components/ScopeContext";
import LayerContext from "@/editor/node-detail/components/LayerContext";
import type { WireframeKind } from "@/editor/canvas/wireframes/logic/wireframe-model";
import DrawingTools from "@/editor/canvas/drawing/components/DrawingTools";
import { discardDrawingDrafts, type DrawingTool } from "@/editor/canvas/drawing/logic/drawing-state";
const DrawingWorkspace = lazy(() => import("@/editor/canvas/drawing/components/DrawingWorkspace"));
import ControlTower from "@/editor/control-tower/components/ControlTower";
import AddMenu from "@/editor/canvas/add-menu/components/AddMenu";
import LiveStrip from "@/editor/live-strip/components/LiveStrip";
import { cardCycleError } from "@/editor/canvas/board/logic/card-cycle";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import OfficeWorkspace from "@/editor/office/components/OfficeWorkspace";
import WorkspaceBoundary from "@/ui-kit/workspace-boundary/components/WorkspaceBoundary";
import {
  readMode,
  readSettings,
  SETTINGS_KEY,
  type WorkspaceMode,
  type SurfaceSettings,
} from "@/shared/surface-settings/logic/workspace-settings";
import { catalogProfile, isLocalKind, projectCapabilities } from "@/shared/project-capabilities/logic/project-capabilities";
import "@/layout/shell/styles/workspace-modes.css";
import AccountCorner from "@/layout/account-corner/components/AccountCorner";
import SettingsDialog from "@/settings/components/SettingsDialog";
import "@/design-tokens/styles/theme-tokens.css";
import NodePanel from "@/editor/node-detail/components/NodePanel";
import CardDrawerHost from "@/hub/oporahub-card-drawer/components/CardDrawerHost";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/open";
import BriefVaultDock, { type VaultFocus } from "@/editor/brief-vault-dock/components/BriefVaultDock";
import { ownerLabel } from "@/editor/brief-vault-dock/logic/vault-dock-model";
import { keepVaultMounted } from "@/editor/brief-vault-dock/logic/vault-drafts";
import { saveNodeSpec } from "@/shared/desktop-state/logic/api";
import { useSyncReport } from "@/editor/node-detail/sync-badge/logic/use-sync-report";
import { notifyCurrentPlanScope } from "@/hub/plan-changes/logic/plan-changes";
import { useGraphProposals } from "@/hub/graph-proposals/logic/use-graph-proposals";
import { usePlanChanges } from "@/hub/plan-changes/logic/use-plan-changes";
import { useGitEvidence } from "@/hub/git-evidence/logic/use-git-evidence";
import { useReviewPolicy } from "@/hub/review-policy/logic/use-review-policy";
import { useGithubReconciliation } from "@/hub/github-reconciliation/logic/use-github-reconciliation";
import { useExecutionReceipts } from "@/hub/execution-receipts/logic/use-execution-receipts";
import { useExecutionObservations } from "@/hub/execution-observations/logic/use-execution-observations";
import { useFormalVerification } from "@/hub/formal-verification/logic/use-formal-verification";
import { useContentChanges } from "@/hub/content-changes/logic/use-content-changes";
import { useProposalReviewModels } from "@/hub/proposal-review/logic/use-proposal-review-models";
import { useExecutionBudgets } from "@/hub/execution-budgets/logic/use-execution-budgets";
import { useOporaProposals } from "@/hub/proposal-history/logic/use-opora-proposals";
import OporaHubWorkspace from "@/hub/oporahub-workspace/components/OporaHubWorkspace";
import { dashboardView } from "@/project/sync-dashboard/logic/sync-dashboard";
import CommentPanel from "@/editor/canvas/comment-card/components/CommentPanel";
import { newComment, nextCommentSpot } from "@/editor/canvas/comment-card/logic/comment-model";
import AreaPanel from "@/editor/canvas/area/components/AreaPanel";
import { areaHost } from "@/editor/canvas/area/logic/area-model";
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
const initialModeEnvironment = resolveInitialModeEnvironment(initial);
export default function App() {
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
  function setMode(next: WorkspaceMode) {
    // Jiný mód = jiný pohled na vrstvu; šuplík z minulého pohledu by jen zakrýval plátno.
    dock.close();
    setEditorMode(next);
    setEnvironment("editor");
  }
  function changeEnvironment(next: Environment) {
    setEnvironment(next);
  }
  // Pořadí karet v grafu závislostí pro „Srovnat“ (sdílené čtení agent-state, žádný další poller).
  const agentCards = useAgentState(project, workspace).state?.cards;
  const topoOrder = useMemo(() => new Map((agentCards ?? []).flatMap((card) => card.topoIndex == null ? [] : [[card.nodeId, card.topoIndex] as const])), [agentCards]);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [agentTask, setAgentTask] = useState<AgentTaskRequest | null>(null);
  // Schránka v levém menu: bez požadavku ukazuje schránku otevřené vrstvy (nebo plátna); openVault z detailu
  // karty ji přepne na rozsah vlastníka fragmentu a fokus. Požadavek platí do změny vrstvy či prostoru.
  const [vaultRequest, setVaultRequest] = useState<{ project: string; workspace: string; scope: string; focus: VaultFocus | null } | null>(null);
  const vaultNonce = useRef(0);
  const [settings, setSettings] = useState(readSettings);
  const [appSettingsOpen, setAppSettingsOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  // Doména předvyplněná v modalu „Nový worktree“ z živého panelu; jinak se bere vybraný uzel.
  const [worktreeDomain, setWorktreeDomain] = useState<string | null>(null);
  // Podzáložka stránky Text (Uživatel/Agenti); resetuje se na Uživatel při přechodu na jinou vrstvu.
  const [textSubtab, setTextSubtab] = useState<TextSubtab>("user");
  const [textRevision, setTextRevision] = useState(0);
  const [planAppliedRevision, setPlanAppliedRevision] = useState(0);
  const [parent, setParent] = useState<string | null>(initial.get("layer"));
  const initialNode = initial.get("node");
  // Klik na poslední změnu na tváři karty: záznam činnosti se otevře s filtrem této karty.
  const [activityRequest, setActivityRequest] = useState<{ nodeId: string; seq: number } | null>(null);
  const [selection, setSelection] = useState<Selection>(() => (initialNode ? selectNode(initialNode) : emptySelection()));
  // Odvozené zkratky: zbytek souboru je psaný proti trojici "vybraný uzel / blok / vazba".
  const selected = selection.node;
  const selectedBlock = selection.block;
  const selectedEdge = selection.edge;
  const [removal, setRemoval] = useState<RemovalPreview | null>(null);
  // Hromadný výběr na plátně (tah obdélníkem, Ctrl+klik): patří jedné vrstvě jednoho prostoru.
  const [multiSelected, setMultiSelected] = useState<string[]>([]);
  useEffect(() => setMultiSelected([]), [project, workspace, parent]);
  useEffect(() => setVaultRequest(null), [project, workspace, parent]);
  // Bloky z portů karty: otevřené v této relaci (blok s uloženými položkami je vidět vždy).
  const [openBlocks, setOpenBlocks] = useState<OpenBlocks>({});
  const [pipelinePickerFor, setPipelinePickerFor] = useState<string | null>(null);
  // Struktura (sekce menu): jedno rozhraní pro celou aplikaci — filtr, hledání a sbalené skupiny drží
  // hook pod jediným klíčem `opora:structure-panel:v1`, nikdy s klíčem projektu.
  const structurePanel = useStructurePanel();
  // Schránka v menu s rozepsaným textem zůstává namountovaná (jen skrytá), aby se text neztratil.
  const [vaultDirty, setVaultDirty] = useState(false);
  // Menu Editoru (docs/menu-a-katalog.md, část A): ☰ vysune u levého okraje lištu ikon a vedle ní
  // panel sekce (Struktura, Schránka, Nastavení), jen v Editoru. Otevřenost je jen v paměti
  // sezení, poslední sekce se pamatuje jednou pro aplikaci; zkratky Ctrl+Shift+, / Ctrl+Shift+.
  // a Esc drží hook. Úvodní obrazovka menu nekreslí, proto tam zkratky nic nepřepínají.
  const loadsCanvas = screen === "canvas";
  const dock = usePanelDock(environment === "editor" && screen === "canvas");
  // Profil patří projektu: načte se z /api/project-settings při otevření sekce a ukládá ho jen App
  // s očekávanou revizí.
  const projectProfile = useProjectProfile(project, dock.section);
  // Plná autonomie agentů: jediný zdroj pro přepínač (úvodní obrazovka) a štítky v liště a ve velínu.
  const agentAutonomy = useAgentAutonomy(project);
  const profile = catalogProfile(projectProfile.snapshot?.settings ?? null);
  // Přechod na jinou vrstvu (Zanořit, drobečková navigace) vrací stránku Text zpět na Uživatele.
  useEffect(() => { setTextSubtab("user"); }, [parent]);
  // Filtr štítků: karty bez vybraného štítku jsou na plátně ztlumené; prázdný = bez filtru.
  const [tagFilter, setTagFilter] = useState("");
  const desktop = useDesktopState(project, workspace);
  const leases = useLeases(project, workspace);
  // Vybraný blok zmizel ze stavu (smazán jinde): výběr spadne zpět na uzel, aby zásuvka i inspektor zůstaly platné.
  useEffect(() => {
    if (!selected || !selectedBlock) return;
    if (!nodeWorkflowOf(desktop.state, selected).blocks.some((b) => b.id === selectedBlock)) setSelection(selectNode(selected));
  }, [selected, selectedBlock, desktop.state]);
  // Naměřené výšky karet (plní Board): „Srovnat“ s nimi nepřekryje vyšší karty s bloky.
  const cardHeights = useRef<Record<string, number>>({});
  const blockApi = useRef<BlockApi>({
    mutate: async () => false, close: () => {}, pickPipeline: () => {}, routePipeline: async () => false, uploadMaterial: async () => null, discardUpload: () => {}, previewUrl: () => null,
  });
  function togglePort(nodeId: string, port: BlockPort) {
    setOpenBlocks((current) => toggleOpen(current, nodeId, port));
  }
  blockApi.current = {
    mutate: desktop.mutate,
    close: (nodeId, port) => setOpenBlocks((current) => closeOpen(current, nodeId, port)),
    pickPipeline: (nodeId) => setPipelinePickerFor(nodeId),
    routePipeline: async (nodeId, profile) => {
      try {
        const base = desktop.revision;
        // Odpověď nese jen revizi a nové etapy karty (karta P3); stav se doplní lokálně.
        const value = await api<PipelineWriteResponse>("/api/desktop-v3/pipeline", { project, workspace, nodeId, expectedRevision: base, op: "route", profile, reason: "Přepnuto člověkem v UI." });
        desktop.applySlim(base, value, (current) => withStages(current, value.nodeId, value.stages));
        return true;
      } catch (error) {
        setError(error instanceof Error ? error.message : "Pipeline se nepodařilo přestavět.");
        return false;
      }
    },
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
  // OporaHub přehled čte jen agent-state; periodická čtení starších dílků běží, jen když je otevřený detail.
  const [hubDetailOpen, setHubDetailOpen] = useState(false);
  const hubDetail = environment === "hub" && hubDetailOpen;
  // Echo Oracle (3–6 s na serveru) čte jen dashboard procesu v detailu OporaHubu: načte se při jeho otevření,
  // přepočet jen na vyžádání. Editor ani přehled na něj nečekají.
  const sync = useSyncReport(project, workspace, hubDetail);
  const proposals = useOporaProposals(project, workspace, view?.graph.nodes ?? [], environment === "hub", !!view?.readOnly);
  const gitEvidence = useGitEvidence(project, workspace, environment === "hub", planAppliedRevision);
  const reviewPolicy = useReviewPolicy(project, workspace, environment === "hub", planAppliedRevision, gitEvidence);
  const reconciliation = useGithubReconciliation(project, workspace, hubDetail, planAppliedRevision, gitEvidence);
  const executionReceipts = useExecutionReceipts(project, workspace, view?.graph.nodes ?? [], environment === "hub", planAppliedRevision);
  const executionObservations = useExecutionObservations(project, workspace, planAppliedRevision, environment === "hub");
  const executionBudgets = useExecutionBudgets(project, workspace, view?.graph.nodes ?? [], environment === "hub", planAppliedRevision);
  const formalVerification = useFormalVerification(project, workspace, hubDetail, planAppliedRevision);
  const contentChanges = useContentChanges(project, workspace, hubDetail, !!view?.readOnly, planAppliedRevision,
    () => notifyCurrentPlanScope({ project, workspace }, activeScope.current, () => {
      setPlanAppliedRevision(value => value + 1); setTextRevision(value => value + 1); sync.refresh(); planChanges.refresh(); reloadCanvas();
    }));
  const planChanges = usePlanChanges(project, workspace, view?.graph.nodes ?? [], environment === "hub", !!view?.readOnly,
    () => notifyCurrentPlanScope({ project, workspace }, activeScope.current, () => {
      setPlanAppliedRevision(value => value + 1); setTextRevision(value => value + 1); sync.refresh(); proposals.refresh();
    }));
  const graphProposals = useGraphProposals(project, workspace, view?.graph.nodes ?? [], environment === "hub", !!view?.readOnly, planAppliedRevision,
    () => notifyCurrentPlanScope({ project, workspace }, activeScope.current, () => {
      setPlanAppliedRevision(value => value + 1); setTextRevision(value => value + 1); sync.refresh(); proposals.refresh(); planChanges.refresh(); reloadCanvas();
    }));
  const sourceStatuses = useSourceStatus(project, workspace, view?.digest ?? "");
  const proposalReview = useProposalReviewModels({ project, workspace }, hubDetail, planAppliedRevision,
    { spec: planChanges.inspected, graph: graphProposals.inspected, content: contentChanges.detail?.proposal });
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
    // Idle polling každých 2,5 s: stejný obsah nechá starou referenci, jinak se App i Board překreslují zbytečně.
    setProjects((current) => keepSame(current, b.projects));
    setDraftProject((current) => keepSame(current, b.draft));
    setJobs((current) => keepSame(current, b.jobs));
  }
  // Zápis jiného procesu (srdce, agent) jde přes backend. Po ohlášení (`opora:spawned`)
  // se graf i stav Desktop v3 načtou znovu stejnými cestami jako při otevření projektu, jen bez
  // vyprázdnění plátna (Board přenese `measured`, fokus v kartách zůstane). Když právě běží uložení
  // grafu, reload počká na jeho konec; o souběh se pak postará digest (stávající hláška konfliktu).
  // Historie kroků zpět se vyprázdní jako při otevření: krok zpět by jinak cizí zápis smazal.
  const savingGraph = useRef(0);
  const canvasReloadQueued = useRef(false);
  function reloadCanvas() {
    if (savingGraph.current > 0) { canvasReloadQueued.current = true; return; }
    canvasReloadQueued.current = false;
    desktop.reload();
    if (!loadsCanvas) return;
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
  useEffect(() => {
    const changed = (event: Event) => {
      const scope = (event as CustomEvent<{ project: string; workspace: string }>).detail;
      if (scope.project === project && scope.workspace === workspace) reloadCanvas();
    };
    window.addEventListener("opora:spawned", changed);
    return () => window.removeEventListener("opora:spawned", changed);
  });
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
  // Projekty a úlohy přes sdílený poller: nikdy dva dotazy najednou, ve skryté záložce stojí.
  // Chybu ukáže jen první načtení; další kola zkoušejí potichu znovu.
  const firstBootstrap = useRef(true);
  usePolling(() => {
    const first = firstBootstrap.current;
    firstBootstrap.current = false;
    return bootstrap().catch((e) => { if (first) setError(String(e)); });
  }, { intervalMs: 2500 });
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
    if (loadsCanvas) refresh(); else generation.current++;
  }, [project, workspace, screen]);
  // Karta z živého panelu v jiném worktree: otevře se až po přepnutí prostoru, tedy po úklidu výběru výše.
  const [pendingCard, setPendingCard] = useState<CardRequest | null>(null);
  useEffect(() => {
    if (!pendingCard || pendingCard.workspace !== workspace) return;
    setPendingCard(null);
    openArchitectureNode(pendingCard.nodeId);
  }, [pendingCard, workspace]);
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
      for (const name of ["editorId", "domainId", "pageId", "architectureNode", "structureNode"]) {
        if (currentRoute.has(name)) q.set(name, currentRoute.get(name)!);
      }
    }
    // Otevřený detail karty (`openCardDrawer`) si drží vlastní parametry; v tomtéž prostoru je nepřepisujeme.
    if (!switchedScope) for (const name of ["ohCard", "ohTab"]) if (currentRoute.has(name)) q.set(name, currentRoute.get(name)!);
    // Zanoření Studia (`studioFocus`, docs/studio.md §2) drží Studio samo; platí jen v jeho záložce a v tomtéž prostoru.
    if (!switchedScope && projectMapKind === "studio" && currentRoute.has("studioFocus")) q.set("studioFocus", currentRoute.get("studioFocus")!);
    history.replaceState(null, "", "/?" + q);
  }, [project, workspace, parent, selected, mode, screen, wireframeMode, environment, projectMapKind]);
  const completed = jobs
    .filter((j) => j.status === "complete" && j.project_id === project)
    .map((j) => j.id)
    .join(",");
  useEffect(() => {
    if (completed && loadsCanvas) refresh();
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
      await trackSaveWrite(project, workspace, saveGraph(graph, onApplied, stepped));
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
      saved = await saveCanvasGraph(view, {
        project,
        workspace,
        graph,
        digest: view.digest,
        undo: stepped !== undefined,
      });
    } catch (e) {
      historyRef.current = historyBefore;
      throw cardCycleError(e, (id) => view.graph.nodes.find((n) => n.id === id)?.name) ?? e;
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
  // Dashboard procesu na úvodní obrazovce: jména rozsahů bere z grafu, zbytek z echa.
  const syncBoard = dashboardView(sync.report, Object.fromEntries(graph.nodes.map((n) => [n.id, n.name])));
  const edge = graph.edges.find((e) => e.id === selectedEdge);
  const layer = graph.nodes.find((n) => n.id === parent);
  const activeVaultRequest = vaultRequest && vaultRequest.project === project && vaultRequest.workspace === workspace ? vaultRequest : null;
  const vaultScope = activeVaultRequest?.scope ?? layer?.id ?? "";
  // Rozsah Schránky se během psaní nemění, aby se rozepsaný formulář nepřemountoval.
  const vaultShown = useRef(vaultScope);
  if (!vaultDirty) vaultShown.current = vaultScope;
  const editable = !!view && !view.readOnly && !busy;
  /**
   * Krok zpět i vpřed je jen uložení staršího snímku grafu; historii nese `save` v `stepped`. Krok
   * zpět na smazání (`restore`) místo toho obnoví zálohu na serveru — vrátí karty i s obsahem.
   */
  function stepHistory(direction: "undo" | "redo") {
    if (!editable) return;
    const step = direction === "undo" ? undo(historyRef.current, graph) : redo(historyRef.current, graph);
    if (!step) return;
    const restore = (step as { restore?: string }).restore;
    run(() => (restore ? restoreRemoval(restore, step.history) : save(step.graph, undefined, step.history)));
  }
  /** Obnova smazaného (`/api/remove/restore`); odmítnutí (digest, už použito) historii nemění. */
  async function restoreRemoval(recoveryId: string, stepped: GraphHistory) {
    if (!view) return;
    const ticket = ++generation.current;
    const scope = { project, workspace };
    const result = await api<{ view: View }>("/api/remove/restore", { project, workspace, recoveryId, digest: view.digest });
    if (ticket !== generation.current || activeScope.current.project !== scope.project || activeScope.current.workspace !== scope.workspace) return;
    historyRef.current = stepped;
    setView(result.view);
    desktop.reload();
  }
  // Ctrl+Z patří plátnu Editoru: ne v Projektu ani OporaHubu, ne nad dokumentací a ne v kreslení,
  // kde má krok zpět Excalidraw. Psaní do polí a textů si zkratku hlídá samo (isTypingTarget).
  const historyEnabled = editable && environment === "editor" && mode !== "drawing";
  useUndoShortcut({
    enabled: historyEnabled,
    onUndo: () => stepHistory("undo"),
    onRedo: () => stepHistory("redo"),
  });
  // Central save flushes the existing content owners before creating a workspace checkpoint.
  const [saveAllBusy, setSaveAllBusy] = useState(false);
  const [restorationEpoch, setRestorationEpoch] = useState(0);
  const saveAllLock = useRef(false);
  const restoreTicket = useRef<{ versionId: string; token: string; digest: string; project: string; workspace: string } | null>(null);
  const saveScope = useSaveScope(project, workspace);
  useSaveParticipant({ id: JSON.stringify(["persisted-content", project, workspace]), project, workspace, label: "Rozepsané texty a dokumentace",
    dirty: orphanedPendingEdits(project, workspace).length > 0, isDirty: () => orphanedPendingEdits(project, workspace).length > 0,
    flush: () => flushOrphanedPendingEdits(project, workspace) });
  const versionsEnabled = screen === "canvas" && !!view;
  const canvasVersions = useCanvasVersions({ project, workspace, enabled: versionsEnabled, refreshKey: `${view?.digest ?? ""}:${desktop.revision}:${saveScope.writeRevision}`, paused: saveAllBusy || saveScope.pending });
  const versionAuthorName = versionAuthor(view?.workspaces, workspace);
  async function prepareCheckpoint() {
    if (!view || view.readOnly || desktop.readOnly) throw new Error("Tento pracovní prostor je pouze ke čtení.");
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    await waitForSaveWrites(project, workspace);
    await canvasVersions.preflight();
    await flushSaveScope(project, workspace);
    const fresh = await api<View>("/api/view?" + new URLSearchParams({ project, workspace }));
    const versions = await canvasVersions.refresh(true);
    if (!versions.currentToken) throw new Error("Chybí potvrzený otisk pracovního prostoru.");
    if (activeScope.current.project !== project || activeScope.current.workspace !== workspace) throw new Error("Pracovní prostor se během ukládání změnil.");
    return { digest: fresh.digest, token: versions.currentToken, fresh };
  }
  function saveVersion() {
    if (!versionsEnabled || saveAllLock.current) return;
    saveAllLock.current = true; setSaveAllBusy(true); setError("");
    void (async () => {
      try { const checkpoint = await prepareCheckpoint(); await canvasVersions.save(checkpoint.digest, versionAuthorName, checkpoint.token); if (activeScope.current.project === project && activeScope.current.workspace === workspace) setView(checkpoint.fresh); }
      catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
      finally { saveAllLock.current = false; setSaveAllBusy(false); }
    })();
  }
  async function prepareRestore(versionId: string) {
    if (saveAllLock.current) throw new Error("Počkejte na dokončení ukládání.");
    saveAllLock.current = true; setSaveAllBusy(true); restoreTicket.current = null;
    try { const checkpoint = await prepareCheckpoint(); restoreTicket.current = { versionId, token: checkpoint.token, digest: checkpoint.digest, project, workspace }; }
    finally { saveAllLock.current = false; setSaveAllBusy(false); }
  }
  async function restoreVersion(versionId: string) {
    const confirmed = restoreTicket.current;
    if (!confirmed || confirmed.versionId !== versionId || confirmed.project !== project || confirmed.workspace !== workspace) throw new Error("Znovu vyberte verzi a potvrďte její obnovení.");
    if (saveAllLock.current || saveScopeEntries(project, workspace).length) throw new Error("Od přípravy obnovy vznikly další změny. Znovu připravte obnovení.");
    saveAllLock.current = true; setSaveAllBusy(true);
    try {
      const restored = await canvasVersions.restore(versionId, confirmed.digest, versionAuthorName, confirmed.token);
      if (activeScope.current.project !== project || activeScope.current.workspace !== workspace) return;
      invalidateSavedScope(project, workspace); discardSpecDrafts(project, workspace); discardDrawingDrafts(project, workspace);
      const restoredIds = new Set(restored.graph.nodes.map((node) => node.id));
      if (parent && !restoredIds.has(parent)) setParent(null);
      if (selected && !restoredIds.has(selected)) setSelection(emptySelection());
      const route = new URLSearchParams(location.search);
      const routeDomain = route.get("domainId");
      const survivingDomain = routeDomain && restored.graph.nodes.some((node) => node.id === routeDomain && node.site?.kind === "application") ? routeDomain : null;
      if (survivingDomain) route.set("domainId", survivingDomain); else route.delete("domainId");
      for (const key of ["pageId", "architectureNode"]) {
        const id = route.get(key);
        if (id && (!restoredIds.has(id) || !survivingDomain || domainForNode(restored.graph, id)?.id !== survivingDomain)) route.delete(key);
      }
      if (route.has("editorId")) route.set("editorId", architectureEditorId(project, workspace, survivingDomain ?? undefined));
      history.replaceState(null, "", "/?" + route);
      generation.current++; historyRef.current = emptyHistory(); setView(restored); desktop.reload();
      setRestorationEpoch((value) => value + 1); restoreTicket.current = null;
    } finally { saveAllLock.current = false; setSaveAllBusy(false); }
  }
  function reloadExternalSaveState() {
    const pending = saveScopeEntries(project, workspace);
    if (pending.length) { setError("Nejprve dokončete nebo zahoďte rozepsané změny v původním panelu: " + pending.map((entry) => entry.label).join(", ")); return; }
    if (saveAllLock.current) return;
    saveAllLock.current = true; setSaveAllBusy(true);
    void (async () => {
      try {
        const fresh = await api<View>("/api/view?" + new URLSearchParams({ project, workspace }));
        await canvasVersions.refresh(true);
        if (activeScope.current.project !== project || activeScope.current.workspace !== workspace) return;
        const changed = saveScopeEntries(project, workspace);
        if (changed.length) throw new Error("Během načítání vznikly rozepsané změny. Zůstávají zachované: " + changed.map((entry) => entry.label).join(", "));
        generation.current++; historyRef.current = emptyHistory(); setView(fresh); desktop.reload();
        setRestorationEpoch((value) => value + 1); setError("");
      } catch (cause) { setError(String(cause)); }
      finally { saveAllLock.current = false; setSaveAllBusy(false); }
    })();
  }
  useSaveShortcut({ enabled: versionsEnabled, onSave: saveVersion });
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
  // Hledání ve Struktuře jde přes jednotný index plátna (docs/kontext-karet-a-index.md §5):
  // jen s otevřenou sekcí a neprázdným dotazem; nová revize grafu nebo plochy dotaz zopakuje.
  // Bez odpovědi (načítá se, selhalo) panel filtruje lokálně podle názvu jako dřív.
  const pageMatches = useCanvasIndex(
    project,
    workspace,
    structurePanel.state.query,
    environment === "editor" && dock.rail && dock.section === "structure",
    `${view?.digest ?? ""}:${desktop.revision}`,
  );
  // Vybraný blok pro Editor v zásuvce (panels.drawer === "block"); undefined, dokud stav nedorazí.
  const selectedBlockData = selectedWorkflow?.blocks.find((b) => b.id === selectedBlock);
  const pickerNode = graph.nodes.find((n) => n.id === pipelinePickerFor);
  const visible = graph.nodes.filter((n) => n.parentId === parent);
  const ancestors: CanvasNode[] = [];
  let cursor = layer;
  while (cursor) {
    ancestors.unshift(cursor);
    cursor = graph.nodes.find((n) => n.id === cursor!.parentId);
  }
  const ancestorSector = [...ancestors].reverse().find((n) => n.kind === "sector") ?? null;
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
  /** Schránka v levém menu: rozsah = plátno (""), sektor nebo karta s vlastní schránkou; volitelně rovnou na fragmentu (a v jeho disciplíně). */
  function openVault(scope: string, focus?: string) {
    setVaultRequest({ project, workspace, scope, focus: focus ? { id: focus, nonce: ++vaultNonce.current } : null });
    dock.open("vault");
  }
  /** Po vložení karet ze schránky: načíst plátno i stav, jako po každé dávce plánu. */
  function reloadAfterVaultPlan() {
    const scope = { project, workspace };
    void run(async () => {
      const fresh = await api<View>(`/api/view?${new URLSearchParams(scope)}`);
      if (activeScope.current.project !== scope.project || activeScope.current.workspace !== scope.workspace) return;
      generation.current++; historyRef.current = emptyHistory(); setView(fresh); desktop.reload();
    });
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
      setTagFilter(""); dock.close();
    });
  }
  /** Studio → Architektura projektu: parametry editoru jdou do adresy dřív, než se editor připojí, protože je čte při startu. */
  function openStudioInArchitecture(params: Record<string, string>) {
    const route = new URLSearchParams(location.search);
    for (const name of ["editorId", "domainId", "pageId", "architectureNode", "structureNode", "studioFocus"]) route.delete(name);
    for (const [name, value] of Object.entries(params)) route.set(name, value);
    route.set("projectView", "architecture");
    history.replaceState(null, "", "/?" + route);
    setProjectMapKind("architecture");
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
    setWorktreeDomain(null);
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
  /**
   * Akce, které dřív zakládaly relaci asistenta (Kancelář „Posadit agenta“, živý panel domény), posílají
   * připravený text srdci a otevřou panel, kde je odpověď srdce vidět (docs/brain-heart-channel.md §5).
   */
  function askHeart(request: HeartRequest) {
    setAssistantOpen(true);
    if (!project) return;
    sendHeartMessage(project, request.workspace, request.text).catch((e) => setError("Zprávu srdci se nepodařilo poslat: " + (e instanceof Error ? e.message : String(e))));
  }
  /** Odpověď člověka srdci z bočního menu bloku (úsudek karty); otevře panel, kde je odpověď srdce vidět. */
  function answerHeart(text: string): Promise<boolean> {
    if (!project) return Promise.resolve(false);
    return sendHeartMessage(project, workspace, text)
      .then(() => { setAssistantOpen(true); return true; })
      .catch((e) => { setError("Zprávu srdci se nepodařilo poslat: " + (e instanceof Error ? e.message : String(e))); return false; });
  }
  /** Přepnutí pracovního prostoru: TopBar i „Pracovat v tomto worktree“ v živém panelu domény. */
  function selectWorkspace(id: string) {
    setWorkspace(id);
    enter(null);
  }
  const architectureLive: ArchitectureLiveProps = {
    worktreeLive: capabilities.worktreeLive,
    onSwitchWorkspace: selectWorkspace,
    onAskHeart: askHeart,
    onCreateWorktree: (domainId) => { open("workspace"); setWorktreeDomain(domainId); },
    onOpenCard: (request) => {
      if (request.workspace === workspace) { openArchitectureNode(request.nodeId); return; }
      setPendingCard(request);
      selectWorkspace(request.workspace);
    },
  };
  // Modal „Nový worktree“: worktree vždy patří doméně (uzlu `site.kind = "application"`). Předvolí se
  // doména z živého panelu, jinak doména vybraného uzlu nebo vrstvy; bez domény nejde worktree založit.
  const worktreeDomains = graph.nodes.filter((n) => n.site?.kind === "application");
  const chosenDomain = worktreeDomainChoice(graph, worktreeDomain, selected ?? parent);
  function enter(id: string | null) {
    setParent(id);
    setSelection(emptySelection());
  }
  /** Dvojklik na kartu otevře jednotný detail; sektor a stránka dál vedou do vnitřního plátna. */
  function enterOrDetail(id: string) {
    const target = graph.nodes.find((n) => n.id === id);
    if (target?.kind === "node" && !target.site) { openNode(id); openCardDrawer(id); return; }
    enter(id);
  }
  // Potvrzení navrženého uzavření karty (starší desktop-v3 tok, akce karty `confirm`).
  const confirmProposalNow = (id: string) => desktop.mutate(confirmProposal(id));
  // Uzavření karty po sloučení PR z detailu karty (akce `close_card` z agent-state); vrací chybu, nebo "".
  async function closeCardNow(id: string, note: string): Promise<string> {
    try {
      return (await desktop.mutate(closeCardAfterMerge(id, note))) ? "" : desktop.error || "Uzavření karty se nepodařilo uložit.";
    } catch (e) {
      return e instanceof Error ? e.message : String(e);
    }
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
    // Uvnitř sloupce toku rozhoduje pořadí v grafu závislostí (`topoIndex` z agent-state), pak původní místo.
    const arranged = arrangeFootprints(
      layerFootprints(graph, parent, desktop.state, openBlocks, cardHeights.current, true)
        .map((f) => ({ ...f, order: topoOrder.get(f.id) })),
      graph.edges,
      layerAreas,
      ARRANGE_SPACING,
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
    // Graf před smazáním: krok zpět na něj vrátí smazané přes zálohu `recoveryId` (jen týž scope).
    const sameScope = () => activeScope.current.project === preview.project && activeScope.current.workspace === preview.workspace;
    const before = sameScope() ? view?.graph : undefined;
    const result = await api<{
      view?: View;
      nodeIds?: string[];
      removedProject?: string;
      recoveryId?: string;
    }>("/api/remove", {
      project: preview.project,
      workspace: preview.workspace,
      kind: preview.kind,
      target: preview.target,
      digest: preview.digest,
      confirmed: true,
    });
    generation.current++;
    // Smazání jde mimo `save` a bere s sebou i obsah uzlu: bez zálohy (`recoveryId`) by ho starší
    // snímky grafu jen vzkřísily prázdné, proto se historie bez ní (a vždy u projektu) vyprázdní.
    historyRef.current = preview.kind !== "project" && before && result.recoveryId && sameScope()
      ? recordRemoval(historyRef.current, before, result.recoveryId)
      : emptyHistory();
    setMultiSelected([]);
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
  // Úvodní obrazovka má týž rám jako zbytek aplikace, ale bez menu Editoru: nemá plátno ani vybranou kartu.
  if (screen === "home") return <>
    <div className="editor-frame" key={restorationEpoch} inert={saveAllBusy}>
      <ProjectHome projects={projects} draftProject={draftProject} projectId={project} jobs={jobs} autonomy={agentAutonomy} onChoose={selectProject} onRefresh={bootstrap} onOpen={() => { changeEnvironment("project"); setScreen("canvas"); }} onConnected={() => { changeEnvironment("project"); setScreen("canvas"); }} onRemove={() => requestRemoval("project", project)} />
    </div>
    {removal && <RemovalDialog key={removal.digest} preview={removal} onClose={() => setRemoval(null)} onConfirm={confirmRemoval} />}
    <AccountCorner onSettings={() => setAppSettingsOpen(true)} />
    {appSettingsOpen && <SettingsDialog onClose={() => setAppSettingsOpen(false)} surface={{ value: settings, onChange: updateSettings }} />}
  </>;
  const artifactMapOpen = mode === "map" || mode === "office" || mode === "storyboard";
  const inspectorTools =
    mode === "map" || mode === "office" || mode === "storyboard" ? (
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
  const structureSection = <StructurePanel
    state={structurePanel.state} nodes={graph.nodes} closed={closedNodeIds} matches={pageMatches}
    onTab={structurePanel.tab} onFilter={structurePanel.filter} onSearch={structurePanel.search} onToggleGroup={structurePanel.group}
    onOpenLayer={(id) => { setEditorMode("structure"); setTagFilter(""); openNode(id); }}
    actions={<SkeletonActions key={project + ":" + workspace} nodes={graph.nodes} selected={selected}
      readOnly={!editable || desktop.readOnly || selectedClosed} busy={busy} onAdd={addSkeleton}
      onEnter={(id) => { setEditorMode("structure"); setTagFilter(""); enter(id); }} />}
    selectedCard={<CardBrief project={project} workspace={workspace} selectedNodeId={selected}
      refreshKey={(view?.digest ?? "") + ":" + desktop.revision} />}
  />;
  // Schránka v menu: viditelná v sekci `vault`; s rozepsaným textem zůstává namountovaná i při jiné
  // sekci či zavřeném menu. Rozsah se během psaní nemění, aby se formulář nepřemountoval.
  const keptVault = view && keepVaultMounted(dock.rail && dock.section === "vault", vaultDirty) ? {
    section: "vault" as const,
    content: (
      <BriefVaultDock key={JSON.stringify([project, workspace, vaultShown.current])} project={project} workspace={workspace}
        scope={vaultShown.current} owner={ownerLabel(vaultShown.current, graph.nodes)} focus={activeVaultRequest?.focus ?? null}
        state={desktop.state} digest={view.digest} readOnly={!!view.readOnly}
        nodes={graph.nodes.map((n) => ({ id: n.id, name: n.name, kind: n.kind, parentId: n.parentId }))}
        onOpenNode={(id) => { openNode(id); setMode("structure"); }}
        onPlanApplied={reloadAfterVaultPlan} onStateChanged={() => desktop.reload()} onDirty={setVaultDirty} />
    ),
  } : undefined;
  return (
    <SaveScopeProvider project={project} workspace={workspace}><div className="app desktop-v2 desktop-v3">
      <TopBar
        onHome={() => setScreen("home")}
        trailing={<><AssistantButton open={assistantOpen} onToggle={() => setAssistantOpen((v) => !v)} />{versionsEnabled && <ActivityLogTools key={"activity:" + project + ":" + workspace} project={project} workspace={workspace} nodes={graph.nodes} selectedNodeId={selected} refreshKey={(view?.digest ?? "") + ":" + desktop.revision} onOpenNode={(id) => { openNode(id); setMode("structure"); }} request={activityRequest} />}{versionsEnabled && <SaveVersionsTools key={project + ":" + workspace} versions={{ ...canvasVersions, dirty: canvasVersions.dirty || saveScope.dirty, saving: canvasVersions.saving || saveAllBusy }} disabled={!view || view.readOnly || desktop.readOnly} onSave={saveVersion} onRestore={restoreVersion} onPrepareRestore={prepareRestore} onReloadExternal={reloadExternalSaveState}/>}</>}
        projectNavigation={environment === "project" ? <ProjectMapNavigation value={projectMapKind} onChange={(kind) => { if (!saveAllBusy) setProjectMapKind(kind); }}/> : null}
        projects={projects}
        draftProject={draftProject}
        project={project}
        busy={busy || saveAllBusy}
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
        onSelectWorkspace={selectWorkspace}
      >
        <EnvironmentSwitch value={environment} onChange={changeEnvironment} disabled={busy || saveAllBusy} />
        <AgentAutonomyBadge autonomy={agentAutonomy.autonomy} />

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
      {environment === "editor" && <div className="environment-toolbar v3-toolbar" role="toolbar" aria-label="Nástroje Editoru" inert={saveAllBusy}>
        <MenuButton open={dock.rail} onToggle={dock.toggleMenu} />
        <ModeRail mode={mode} onMode={setMode} />
        <span className="v3-grow" />
        <div className="v3-tool-group" role="group" aria-label="Pohled">
          {/* Lišta stojí i během ukládání (jen zešedne), aby při každém kroku neproblikla. */}
          {view && !view.readOnly && <HistoryButtons canUndo={historyEnabled && historyRef.current.past.length > 0} canRedo={historyEnabled && historyRef.current.future.length > 0}
            onUndo={() => stepHistory("undo")} onRedo={() => stepHistory("redo")} />}
        </div>
        {(mode === "structure" || mode === "text") && <div className="v3-tool-group" role="group" aria-label="Tvorba">
          <AddMenu disabled={!editable} onAdd={(kind) => kind === "sector" || kind === "node" ? open(kind) : kind === "comment" ? createComment() : createArea()} />
        </div>}
        {mode === "structure" && <div className="v3-tool-group v3-tool-group--shrink" role="group" aria-label="Filtr štítků">
          <TagFilter graph={graph} parent={parent} state={desktop.state} value={tagFilter} onChange={setTagFilter} />
        </div>}
        {mode === "structure" && <div className="v3-tool-group" role="group" aria-label="Rozložení">
          <button type="button" disabled={!editable} onClick={arrangeLayer} title="Srovná vrstvu do sloupců podle vazeb; ve sloupci podle pořadí v grafu závislostí">Srovnat</button>
        </div>}
        {/* Se skrytým inspektorem zůstávají nástroje kreslení a mapy dosažitelné v liště. */}
        {!inspectorShown && inspectorTools && <div className="v3-tool-group v3-mode-tools" role="group" aria-label="Nástroje pohledu">{inspectorTools}</div>}

      </div>}
      {/* Rám prostředí pod horní lištou a lištou nástrojů: obsah prostředí zabírá celou šířku. V Editoru
          z levého okraje rámu vyjíždí menu (Struktura, Schránka, Nastavení) nad plátnem, ne vedle
          něj (kontrakt docs/suplik-a-profil.md). */}
      <div className="editor-frame" key={restorationEpoch} inert={saveAllBusy}>
      {environment === "project" ? <ProjectWorkspace project={project} workspace={workspace} selection={docSelection.value} onChange={docSelection.change} mapKind={projectMapKind} projectName={projects.find((p) => p.id === project)?.name ?? draftProject?.name} onOpenEditor={openArchitectureNode} onOpenArchitecture={openStudioInArchitecture} architectureLive={architectureLive} onGraphChanged={() => { reloadCanvas(); desktop.reload(); }}/> :
      environment === "hub" ? <OporaHubWorkspace onDetailOpenChange={setHubDetailOpen} view={syncBoard} onRefresh={sync.refresh} proposals={proposals} changes={planChanges} contentChanges={contentChanges} proposalReview={proposalReview} evidence={gitEvidence} executions={executionReceipts} executionObservations={executionObservations} budgets={executionBudgets} formalVerification={formalVerification} graphProposals={graphProposals} reviewPolicy={reviewPolicy} reconciliation={reconciliation} /> :
      <div className={"workspace-shell " + mode + "-mode" + (mode === "map" || mode === "office" || mode === "storyboard" ? " no-inspector" : "") + " no-context" + (!inspectorShown ? " inspector-hidden" : "")}>
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

          </div>}
          <div className="canvas-surface">
            {/* Boční menu = stopa práce karty: z vybraného bloku, nebo výslovně z karty (karty srdce bloky nemají). */}
            {environment === "editor" && mode === "structure" && (panels.drawer === "card" || (panels.drawer === "block" && selectedBlockData)) && !artifactMapOpen && view && node && selectedWorkflow && (
                <BlockPanelDrawer>
                      <BlockDrawerContent
                        project={project}
                        workspace={workspace}
                        node={node}
                        workflow={selectedWorkflow}
                        blockId={selectedBlockData?.id ?? null}
                        edges={graph.edges}
                        nodes={graph.nodes}
                        onSelectNode={() => setSelection(selectNode(node.id))}
                        onAskHeart={answerHeart}
                      />
                </BlockPanelDrawer>
            )}
            {view ? (
              mode === "text" ? (
                <TextWorkspace project={project} workspace={workspace} layer={layer} children={visible} targets={linkTargets} subtab={textSubtab} onSubtab={setTextSubtab} isClosed={(id) => !!nodeWorkflowOf(desktop.state, id).done.confirmed} onEnter={enter} onOpenNode={(id) => { openNode(id); setMode("structure"); }} onAgentTask={requestAgentTask} onTextSaved={() => setTextRevision((value) => value + 1)} refreshKey={(view?.digest ?? "") + ":" + desktop.revision} />
              ) : mode === "map" ? (
                <ControlTower key={project} project={project} workspace={workspace} graph={graph} projectName={projects.find((p) => p.id === project)?.name ?? draftProject?.name} onOpen={(id) => { openCardDrawer(id); }} onOpenMap={() => openDomainMap(null)} onOpenVault={openVault} worktreeLive={capabilities.worktreeLive} autonomy={agentAutonomy.autonomy} />
              ) : mode === "office" ? (
                <OfficeWorkspace key={`${project}:${workspace}`} project={project} workspace={workspace} graph={graph} state={desktop.state} onOpenNode={(id) => { openNode(id); setMode("structure"); }} onEnterLayer={(id) => { enter(id); setMode("structure"); }}
                  onAskHeart={askHeart} />
              ) : mode === "storyboard" ? (
                <StoryboardWorkspace key={JSON.stringify([project, workspace])} project={project} workspace={workspace} graph={graph} selectedNode={selected} readOnly={!!view?.readOnly} onOpenNode={(id) => { openNode(id); }} onDraw={(id) => { enter(id); setMode("drawing"); }} />
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
              ) : (<>
                <Board
                  heightsRef={cardHeights}
                  revision={desktop.revision}
                  digest={view?.digest}
                  leases={leases}
                  sourceStatuses={sourceStatuses}
                  onRealizeSource={async (nodeId, commit, prUrl) => {
                    await trackSaveWrite(project, workspace, api("/api/desktop-v3/realize-source", { project, workspace, nodeId, digest: view?.digest, commit, prUrl }));
                    reloadCanvas();
                  }}
                  onConfirmProposal={confirmProposalNow}
                  onConfirmSector={async (sectorId, ids) => {
                    desktop.apply(await trackSaveWrite(project, workspace, confirmSector(project, workspace, sectorId, ids, {
                      fetchRevision: async () => (await fetchState(project, workspace)).revision,
                      post: (body) => api<StateResponse>("/api/desktop-v3/confirm-proposals", body),
                    })));
                  }}
                  onAutonomy={async (sectorId, until, grantedBy, note) => {
                    // Revize až těsně před zápisem: stav mezitím mění agenti a stará revize by souhlas tiše odmítla.
                    const fresh = await fetchState(project, workspace);
                    desktop.apply(await trackSaveWrite(project, workspace, api<StateResponse>("/api/desktop-v3/autonomy", { project, workspace, sectorId, until, grantedBy, note, expectedRevision: fresh.revision })));
                  }}
                  onSaveSector={updated => { void run(() => save({ ...graph, nodes: graph.nodes.map(n => n.id === updated.id ? updated : n) })); }}
                  onRuleWrite={(expected, item) => desktop.mutateItem("rule", expected, item)}
                  onRuleReview={desktop.reviewRule}
                  sourceContext={{ project, workspace }}
                  key={project + workspace + parent}
                  scope={project + workspace + parent}
                  graph={graph}
                  settings={settings}
                  parent={parent}
                  selected={selected}
                  multiSelected={multiSelected}
                  onMultiSelect={(ids) => {
                    const plan = selectionPlan(ids);
                    setMultiSelected(plan.multi);
                    setSelection((current) => plan.single ? (current.node === plan.single ? current : selectNode(plan.single)) : clearSelection());
                  }}
                  onDeleteSelection={() => {
                    if (removal) return;
                    const ids = deletableSelection(multiSelected, selected, new Set(visible.map((n) => n.id)));
                    if (ids.length > 1) void requestRemoval("selection", ids.join(","));
                    else if (ids.length === 1) void requestRemoval("node", ids[0]);
                    else if (selectedEdge) void requestRemoval("edge", selectedEdge);
                  }}
                  selectedBlock={selectedBlock}
                  disabled={!editable}
                  selectedEdge={selectedEdge}
                  onSelect={openNode}
                  onCardHistory={(id) => { openNode(id); setActivityRequest((before) => ({ nodeId: id, seq: (before?.seq ?? 0) + 1 })); }}
                  onCardTrail={(id) => { openNode(id); setSelection(selectCardTrail(id)); }}
                  onSelectBlock={(nodeId, blockId) => setSelection(selectBlock(nodeId, blockId))}
                  onClear={() => { setSelection(clearSelection()); setMultiSelected([]); }}
                  onSelectEdge={(id) => setSelection(selectEdge(id))}
                  onEnter={enterOrDetail}
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
                  onPosition={(id, x, y, area) =>
                    // Karta a případně za ní vyrostlá domovská oblast (`area-growth.ts`) jdou jednou změnou.
                    run(() =>
                      save({
                        ...graph,
                        nodes: graph.nodes.map((n) =>
                          n.id === id ? { ...n, x, y }
                            : area && n.id === area.id ? { ...resizeArea(n, area.w, area.h), x: area.x, y: area.y } : n,
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
                    else if (event.type === "decide-port") void desktop.mutate(decideBlockPort(nodeId, event.blockId, event.portId, event.status, event.reason));
                    else void desktop.mutate(updateBlock(nodeId, event.blockId, { title: event.title }));
                  }}
                />
              </>)
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
          {view && project && workspace && (mode === "structure" || mode === "map") && <LiveStrip key={project + ":" + workspace} project={project} workspace={workspace} graph={graph} parent={parent} />}
          {!artifactMapOpen && <footer className="statusline">
            <span>
              {visible.length} uzlů v této vrstvě · {graph.nodes.length} v grafu
            </span>
            <span>
              {view?.readOnly ? "SCHVÁLENÁ VĚTEV · POUZE ČTENÍ" : "NÁVRH / PRACOVNÍ ZMĚNY"} · Agent se automaticky nespouští
            </span>
          </footer>}
        </main>
        {panels.inspector !== null && (
          <aside className="inspector" aria-label="Inspektor">
            {panels.inspector === "node" && node ? (<>
              <NodePanel
                key={project + ":" + workspace + ":" + node.id}
                specRefreshRevision={planAppliedRevision}
                node={node}
                project={project}
                workspace={workspace}
                readOnly={!!view?.readOnly}
                busy={busy}
                onEnter={() => {
                  enter(node.id);
                  if (mode === "map") setMode("structure");
                }}
                onDelete={() => requestRemoval("node", node.id)}
                childCount={node.kind === "sector" ? graph.nodes.filter((child) => child.parentId === node.id && child.kind === "node").length : 0}
                openIdeasInSector={node.kind === "sector" ? graph.nodes.filter((child) => child.parentId === node.id).reduce((sum, child) => sum + openIdeas(desktop.state.nodes[child.id]?.ideas), 0) : 0}
                onAgentTask={() => requestAgentTask(node.id, "", "canvas")}
                onOpenVault={openVault}
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
                host={areaHost(node, graph.nodes)}
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
      {environment === "editor" && (dock.rail || !!keptVault) && (
        <PanelDock
          rail={dock.rail}
          section={dock.section}
          onSelect={dock.select}
          onClose={dock.close}
          kept={keptVault}
        >
          {dock.section === "settings" ? (
            <DockSettings
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
          ) : dock.section === "structure" ? (
            structureSection
          ) : dock.section === "vault" && !view ? (
            <p className="dock-settings__hint">Načítám plátno…</p>
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
      <CardDrawerHost project={project} workspace={workspace} nodes={graph.nodes} editor={{
        readOnly: !view || view.readOnly, busy, workspaces: view?.workspaces ?? [], resultRevision: desktop.revision, specRefreshRevision: planAppliedRevision,
        onSave: (n) => run(() => save({ ...graph, nodes: graph.nodes.map((old) => (old.id === n.id ? n : old)) })),
        onCloseCard: closeCardNow,
        onWorkspace: () => open("workspace"), onOpenNode: openNode, onOpenVault: openVault,
        fragmentRefs: (id) => desktop.state.nodes[id]?.fragmentRefs,
      }} />
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
                      mainu. Worktree patří jedné doméně.
                    </p>
                    {worktreeDomains.length ? (
                      <label className="field">
                        Doména
                        <select aria-label="Doména worktree" data-testid="worktree-domain" value={chosenDomain} onChange={(e) => setWorktreeDomain(e.target.value || null)}>
                          {!chosenDomain && <option value="">Vyberte doménu…</option>}
                          {worktreeDomains.map((d) => {
                            const host = d.site?.kind === "application" ? d.site.environments[0]?.host : "";
                            return <option key={d.id} value={d.id}>{host ? `${host} · ${d.name}` : d.name}</option>;
                          })}
                        </select>
                      </label>
                    ) : (
                      <p role="alert">Projekt zatím nemá žádnou doménu. Založte ji v Mapách architektury (+ Doména).</p>
                    )}
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
                      disabled={busy || !actor.trim() || !chosenDomain}
                      title={chosenDomain ? undefined : "Nejdřív vyberte doménu."}
                      onClick={() =>
                        run(async () => {
                          if (!chosenDomain) throw new Error("Worktree musí patřit doméně.");
                          const w = await api<Workspace>("/api/workspaces", {
                            project,
                            nodeId: chosenDomain,
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
      <AssistantPanel open={assistantOpen} scope={{ projectId: project, workspace }} nodes={graph.nodes} onClose={() => setAssistantOpen(false)} />
    </div></SaveScopeProvider>
  );
}
