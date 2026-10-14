// Plátno: React Flow nad grafem. Kartu skládá NodeCard z modelu karty (editor/canvas/node-card),
// bloky Akce / Pravidla dodává rodič (App) už spočítané. Board jen mapuje data a bublá události nahoru.
import { useEffect, useMemo, useRef, useState } from "react";
import { useDesktopAppearance } from "@/app/logic/desktop-appearance";
import { resolveFacts } from "@/editor/canvas/node-card/components/CardFacts";
import WorkNow from "@/editor/canvas/node-card/components/WorkNow";
import { useWorkOverview } from "@/editor/canvas/node-card/logic/use-work-overview";
import { useScenarioHistory } from "@/editor/canvas/node-card/logic/use-scenario-history";
import { useAddedPulse } from "@/editor/canvas/node-card/logic/use-added-pulse";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  SelectionMode,
  applyNodeChanges,
  type Node,
  type Edge,
  type Connection,
  type Viewport,
  type ReactFlowInstance,
} from "@xyflow/react";
import { CATALOG_DRAG_TYPE } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { AGENT_DRAG_TYPE } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import type { SurfaceSettings } from "@/shared/surface-settings/logic/workspace-settings";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import { edgeAppearance } from "@/editor/canvas/board/logic/board-model";
import { upstreamRows } from "@/editor/canvas/node-card/logic/upstream";
import { useFrontier } from "@/editor/canvas/node-card/logic/use-frontier";
import { areaSummary, handoffMark, useCardChecklist } from "@/editor/canvas/card-checklist/logic/card-checklist";
import { proposalCount, proposalsIn } from "@/editor/canvas/node-card/logic/completion-proposals";
import ConfirmSectorProposals from "@/editor/canvas/node-card/components/ConfirmSectorProposals";
import { evidenceReadiness } from "@/editor/canvas/node-card/logic/evidence-readiness";
import { releaseLease } from "@/editor/canvas/node-card/logic/release-lease";
import SectorGateEditor from "@/editor/canvas/node-card/components/SectorGateEditor";
import SectorAutonomy from "@/editor/canvas/node-card/components/SectorAutonomy";
import "@/editor/canvas/board/styles/board-bar.css";
import { sectorViews } from "@/editor/canvas/node-card/logic/sector-status";
import { layerFootprints } from "@/editor/canvas/board/logic/layout-model";
import { settleArea, settleCard } from "@/editor/canvas/board/logic/solid-bodies";
import NodeCard, { type NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import { effectiveRules } from "@/editor/canvas/node-card/logic/effective-rules";
import type { UsageSummary } from "@/editor/canvas/node-card/logic/use-usage";
import { cardView, matchesTagFilter } from "@/editor/canvas/node-card/logic/card-model";
import CommentCard, { type CommentCardData } from "@/editor/canvas/comment-card/components/CommentCard";
import { commentView } from "@/editor/canvas/comment-card/logic/comment-model";
import AreaCard, { type AreaCardData } from "@/editor/canvas/area/components/AreaCard";
import { areaColorOf, areaLabel, membersOf } from "@/editor/canvas/area/logic/area-model";
import { blockNodeTypes } from "@/editor/workflow/blocks/components/CanvasBlock";
import { isBlockId, parseBlockId, type BlockPort, type OpenBlocks } from "@/editor/workflow/blocks/logic/block-model";
import { revealNodeCenter } from "../logic/reveal-node";
import { isDeleteKey, reportsSelection, sameSelection, selectionIds } from "../logic/box-selection";
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { changedSinceInsert, indexVault } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";

const nodeTypes = { canvas: NodeCard, comment: CommentCard, area: AreaCard, ...blockNodeTypes };

/** Půlka karty: co uživatel pustí, má přistát pod kurzorem, ne rohem na něm. Stejné míry jako dvojklik. */
const CARD_GRAB = { x: 136, y: 84 };

/**
 * Ze kterého navbaru tažení přišlo: levý katalog knihovny (`CATALOG_DRAG_TYPE`), nebo pravý katalog
 * postupů (`AGENT_DRAG_TYPE`). Cizí tažení (soubor, text) plátno nebere a nechá ho projít beze změny.
 */
const dropTypeOf = (types: readonly string[]): string | null =>
  types.includes(CATALOG_DRAG_TYPE) ? CATALOG_DRAG_TYPE : types.includes(AGENT_DRAG_TYPE) ? AGENT_DRAG_TYPE : null;

/**
 * Karta pod ukazatelem při puštění: id uzlu React Flow, na který se pustilo. Boční blok (Akce /
 * Pravidla / Podklady) patří své kartě, proto se přeloží na její id. Prázdné plátno vrací `null`.
 */
function dropTargetOf(target: EventTarget | null): string | null {
  const id = target instanceof Element ? target.closest(".react-flow__node")?.getAttribute("data-id") ?? null : null;
  if (!id) return null;
  return isBlockId(id) ? parseBlockId(id)?.nodeId ?? null : id;
}

/** Z celé instance React Flow potřebuje drop jedinou schopnost: přepočet obrazovky na souřadnice vrstvy. */
type ScreenToFlow = Pick<ReactFlowInstance, "screenToFlowPosition" | "getNode" | "getZoom" | "setCenter">;

export type CardBlockEvent =
  | { type: "configure-spawn"; blockId: string; portId: string; action: import("@/shared/desktop-state/logic/types").PortSpawn | undefined }
  | { type: "add" }
  | { type: "move"; blockId: string; delta: -1 | 1 }
  | { type: "remove"; blockId: string }
  | { type: "rename"; blockId: string; title: string }
  | { type: "text"; blockId: string; text: string }
  | { type: "add-port"; blockId: string }
  | { type: "rename-port"; blockId: string; portId: string; label: string }
  | { type: "remove-port"; blockId: string; portId: string }
  | { type: "decide-port"; blockId: string; portId: string; status: "chosen" | "rejected" | ""; reason: string };

export default function Board({
  onUrlDownload,
  sourceStatuses,
  onRealizeSource,
  onAutonomy,
  onSaveEvidence,
  onSaveSector,
  onConfirmSector,
  onConfirmProposal,
  confirmError,
  leases,
  assignmentStatuses,
  usage,
  onRuleWrite,
  onRuleReview,
  sourceContext,
  heightsRef,
  graph,
  state,
  settings,
  parent,
  selected,
  multiSelected,
  onMultiSelect,
  onDeleteSelection,
  selectedBlock,
  scope,
  disabled,
  onSelect,
  onSelectBlock,
  onClear,
  selectedEdge,
  onSelectEdge,
  onEnter,
  onPosition,
  onConnect,
  editing,
  onEditing,
  onRename,
  onCreateAt,
  onCommentText,
  onAreaMove,
  onAreaResize,
  blocks,
  openBlocks,
  onTogglePort,
  onBlockMove,
  tagFilter,
  onTagFilter,
  onCardBlock,
  onCatalogDrop,
  onAgentDrop,
  reveal,
  onRevealed,
}: {
  usage?: UsageSummary | null;
  onUrlDownload?: (nodeId: string, enabled: boolean) => Promise<boolean>;
  sourceStatuses?: Record<string, import("@/editor/canvas/node-card/logic/use-source-status").SourceStatus>;
  onRealizeSource?: (nodeId: string, commit: string, prUrl: string) => Promise<void>;
  onConfirmProposal?: (nodeId: string) => Promise<boolean>;
  /** Poslední chyba uložení stavu (text ze serveru); karta ji ukáže, když potvrzení selže. */
  confirmError?: string;
  onConfirmSector?: (sectorId: string, ids: string[]) => Promise<void>;
  onSaveSector?: (node: import("@/shared/types/logic/types").CanvasNode) => void;
  onAutonomy?: (sectorId: string, until: string, grantedBy: string, note: string) => Promise<void>;
  onSaveEvidence?: (nodeId: string, value: import("@/editor/canvas/node-card/components/CardEvidence").CompletionEvidence) => Promise<boolean>;
  leases?: Record<string, import("@/editor/canvas/node-card/logic/use-leases").CardLease>;
  assignmentStatuses?: import("@/editor/canvas/node-card/logic/use-assignment-status").AssignmentStatuses;
  onRuleWrite?: NonNullable<NodeCardData["rules"]>["write"];
  onRuleReview?: NonNullable<NodeCardData["rules"]>["review"];
  sourceContext?: { project: string; workspace: string };
  /** Naměřené výšky karet vrstvy pro „Srovnat“ v App (karta s bloky je vyšší než výchozí otisk). */
  heightsRef?: { current: Record<string, number> };
  graph: Graph;
  /** Stav Desktop v3 (fáze, bloky, akce, pravidla) pro patu a hlavu karty. */
  state: DesktopState;
  settings: SurfaceSettings;
  parent: string | null;
  selected: string | null;
  /** Hromadný výběr (tah obdélníkem, Ctrl+klik): id uzlů vrstvy, drží ho rodič. */
  multiSelected: string[];
  /** Výběr na plátně se změnil (bez bočních bloků); rodič z něj skládá svůj výběr. */
  onMultiSelect: (ids: string[]) => void;
  /** Delete / Backspace mimo psaní: rodič otevře jeden potvrzovací dialog pro celý výběr. */
  onDeleteSelection: () => void;
  /** Id vybraného bloku v kartě vybraného uzlu; zvýrazní jeho rámeček. */
  selectedBlock: string | null;
  scope: string;
  disabled: boolean;
  onSelect: (id: string) => void;
  /** Klik na plochu bloku uvnitř karty (mimo hlavu a porty) vybere ten blok místo celého uzlu. */
  onSelectBlock: (nodeId: string, blockId: string) => void;
  /** Klik na prázdné plátno zruší výběr uzlu, bloku i vazby najednou. */
  onClear: () => void;
  selectedEdge: string | null;
  onSelectEdge: (id: string) => void;
  onEnter: (id: string) => void;
  onPosition: (id: string, x: number, y: number) => void;
  onConnect: (c: Connection) => void;
  /** Uzel právě přejmenovaný přímo na kartě. */
  editing: string | null;
  onEditing: (id: string | null) => void;
  onRename: (id: string, name: string) => void;
  /** Dvojklik na prázdné plátno vytvoří uzel na daném místě vrstvy. */
  onCreateAt: (x: number, y: number) => void;
  /** Text komentáře opuštěný na plátně (blur v textarea lístku); ukládá rodič. */
  onCommentText: (id: string, text: string) => void;
  /** Tažení celého rámečku oblasti: posun (dx, dy) spočítaný proti uložené pozici; bere s sebou i členy. */
  onAreaMove: (id: string, dx: number, dy: number) => void;
  /** Změna velikosti oblasti tahadlem (NodeResizer); ukládá rodič ohraničenou na 120..20000. */
  onAreaResize: (id: string, w: number, h: number) => void;
  /** Bloky Akce/Pravidla vedle karet (nejsou součástí grafu) a jejich šipky. */
  blocks: { nodes: Node[]; edges: Edge[] };
  openBlocks: OpenBlocks;
  onTogglePort: (nodeId: string, port: BlockPort) => void;
  /** Blok odtažený po plátně: posun (dx, dy) proti uložené pozici karty; ukládá rodič do `blockOffsets` uzlu. */
  onBlockMove: (nodeId: string, port: BlockPort, dx: number, dy: number) => void;
  /** Vybraný štítek: karty bez něj jsou ztlumené. */
  tagFilter: string;
  onTagFilter: (tag: string) => void;
  /** Bloky obsahu v kartě; ukládá rodič. */
  onCardBlock: (nodeId: string, event: CardBlockEvent) => void;
  /**
   * Prvek Knihovny puštěný na plátno: id z tažení, místo puštění v souřadnicích vrstvy a id uzlu pod
   * ukazatelem (`null` = prázdné plátno). Co vznikne (blok v kartě, nebo nová karta), rozhoduje rodič.
   */
  onCatalogDrop: (itemId: string, x: number, y: number, targetId: string | null) => void;
  /**
   * Položka Agentů a Postupů puštěná na plátno: stejné místo i cíl. Co z ní vznikne — pravidlo, akce,
   * nebo celý sektor s fázemi — rozhoduje rodič, ne plátno.
   */
  onAgentDrop: (itemId: string, x: number, y: number, targetId: string | null) => void;
  reveal?: { id: string; scope: string; nonce: number } | null;
  onRevealed?: (nonce: number) => void;
}) {
  const [showFrontier, setShowFrontier] = useState(true);
  const frontier = useFrontier(sourceContext, parent, showFrontier, state);
  const checklists = useCardChecklist(sourceContext, parent, state);
  // Strom schránky se obnoví jen při změně odkazů karet a Podnětů do schránky, ne při každé změně stavu.
  const vaultRefs = useMemo(() => JSON.stringify(Object.entries(state.nodes).map(([id, node]) =>
    [id, node.fragmentRefs ?? [], (node.ideas ?? []).map((idea) => idea.fragmentId ?? "")])), [state.nodes]);
  const vault = useBriefVault(sourceContext, vaultRefs);
  const vaultIndex = useMemo(() => indexVault(vault.tree?.roots ?? []), [vault.tree]);
  const isSelected = (id: string) => id === selected || multiSelected.includes(id);
  const sectors = useMemo(() => sectorViews(graph, state), [graph, state]);
  const movedCards = useAddedPulse(graph.nodes.map(n => `${n.id}:${n.parentId}:${n.x}:${n.y}`));
  const workRevision = useMemo(() => ({ graph, state }), [graph, state]);
  const work = useWorkOverview(sourceContext?.project ?? "", sourceContext?.workspace ?? "", workRevision);
  const scenarios = useScenarioHistory(sourceContext?.project ?? "", sourceContext?.workspace ?? "", workRevision);
  const make = (): Node[] =>
    (graph.nodes
      .filter((n) => n.parentId === parent)
      .map((n): Node<NodeCardData> | Node<CommentCardData> | Node<AreaCardData> => {
        if (n.kind === "comment") {
          return {
            id: n.id,
            type: "comment",
            position: { x: n.x, y: n.y },
            selected: isSelected(n.id),
            connectable: false,
            data: {
              view: commentView(n),
              disabled,
              onRename: (title: string) => onRename(n.id, title),
              onText: (text: string) => onCommentText(n.id, text),
            },
          };
        }
        if (n.kind === "area") {
          const size = n.size ?? { w: 720, h: 480 };
          return {
            id: n.id,
            type: "area",
            position: { x: n.x, y: n.y },
            selected: isSelected(n.id),
            // Oblast musí zůstat pod kartami vždy, i vybraná — proto vlastní z-index i mimo CSS.
            zIndex: -1,
            style: { width: size.w, height: size.h },
            data: {
              view: { label: areaLabel(n), unnamed: !n.name.trim(), members: membersOf(n, graph.nodes).length, w: size.w, h: size.h, color: areaColorOf(n),
                summary: checklists ? areaSummary(membersOf(n, graph.nodes).flatMap((m) => checklists[m.id] ? [checklists[m.id]] : [])) : undefined },
              disabled,
              onRename: (name: string) => onRename(n.id, name),
              onResize: (w: number, h: number) => onAreaResize(n.id, w, h),
            },
          };
        }
        const workflow = nodeWorkflowOf(state, n.id);
        const view = { ...cardView(n, workflow, graph.nodes.filter((c) => c.parentId === n.id).length),
          briefChanged: changedSinceInsert(workflow.fragmentRefs, vaultIndex) };
        return {
          id: n.id,
          type: "canvas",
          position: { x: n.x, y: n.y },
          selected: isSelected(n.id),
          data: {
            view,
            checklist: checklists?.[n.id],
            usage: (n.kind === "sector" ? usage?.sectors : usage?.nodes)?.[n.id],
            upstream: { rows: upstreamRows(graph, state, n.id), open: onSelect },
            frontier: frontier.rows?.[n.id],
            sectorProgress: sectors[n.id],
            evidence: state.nodes[n.id]?.evidence,
            facts: resolveFacts(n.factRefs ?? [], state.settings),
            work: work?.data?.nodes[n.id],
            workCounts: work?.data?.sectors[n.id],
            moved: movedCards.includes(`${n.id}:${n.parentId}:${n.x}:${n.y}`),
            inputSecurity: onUrlDownload ? { enabled: !!state.nodes[n.id]?.downloadsUrl, save: (enabled: boolean) => onUrlDownload(n.id, enabled) } : undefined,
            scenario: n.scenario ? { command: n.scenario.command, history: scenarios?.nodes?.[n.id], error: scenarios?.error } : undefined,
            realization: n.sourceRef && onRealizeSource ? { value: n.realization, status: sourceStatuses?.[n.id], disabled,
              save: (commit: string, prUrl: string) => onRealizeSource(n.id, commit, prUrl) } : undefined,
            autonomous: state.nodes[n.id]?.done?.by === "autonomy" && state.nodes[n.id]?.done?.confirmed,
            saveEvidence: onSaveEvidence ? value => onSaveEvidence(n.id, value) : undefined,
            lease: leases?.[n.id],
            releaseLease: leases?.[n.id] && sourceContext ? () => releaseLease(sourceContext.project, sourceContext.workspace, n.id) : undefined,
            completion: onConfirmProposal ? { confirm: () => onConfirmProposal(n.id), note: state.nodes[n.id]?.done?.note,
              readiness: evidenceReadiness(state.nodes[n.id]?.evidence, n), error: confirmError,
              pending: n.kind === "sector" ? proposalCount(graph, state, n.id) : 0 } : undefined,
            assignmentWarning: assignmentStatuses?.[n.id]?.status === "changed" && sourceContext
              ? { ...sourceContext, nodeId: n.id, resultId: assignmentStatuses[n.id].resultId, source: assignmentStatuses[n.id].source } : undefined,
            inheritedRules: effectiveRules(graph, state, n.id).filter((rule) => rule.inherited || rule.origin.storage === "node" || !onRuleWrite),
            rules: onRuleWrite && onRuleReview ? { items: state.rules.filter((rule) => rule.scope === "node" && rule.target === n.id), write: onRuleWrite, review: onRuleReview } : undefined,
            source: n.sourceRef && sourceContext ? { source: n.sourceRef, ...sourceContext } : undefined,
            dimmed: !matchesTagFilter(workflow, tagFilter),
            onTag: onTagFilter,
            // Vybraný blok patří jen kartě svého uzlu; jinou kartu jeho výběr nezvýrazní.
            selectedBlockId: n.id === selected ? (selectedBlock ?? undefined) : undefined,
            ports: {
              open: openBlocks[n.id] ?? [],
              toggle: (port) => { if (!disabled) onTogglePort(n.id, port); },
            },
            blocks: {
              // Uzavřená karta má bloky i porty jen ke čtení; do hloubky se jít dál smí.
              disabled: disabled || view.closed,
              add: () => onCardBlock(n.id, { type: "add" }),
              move: (blockId, delta) => onCardBlock(n.id, { type: "move", blockId, delta }),
              remove: (blockId) => onCardBlock(n.id, { type: "remove", blockId }),
              rename: (blockId, title) => onCardBlock(n.id, { type: "rename", blockId, title }),
              text: (blockId, text) => onCardBlock(n.id, { type: "text", blockId, text }),
              addPort: (blockId) => onCardBlock(n.id, { type: "add-port", blockId }),
              renamePort: (blockId, portId, label) => onCardBlock(n.id, { type: "rename-port", blockId, portId, label }),
              removePort: (blockId, portId) => onCardBlock(n.id, { type: "remove-port", blockId, portId }),
              decidePort: (blockId, portId, status, reason) => onCardBlock(n.id, { type: "decide-port", blockId, portId, status, reason }),
              configureSpawn: (blockId, portId, action) => onCardBlock(n.id, { type: "configure-spawn", blockId, portId, action }),
            },
            rename: {
              editing: editing === n.id,
              start: () => { if (!disabled) onEditing(n.id); },
              cancel: () => onEditing(null),
              commit: (name: string) => {
                onEditing(null);
                if (name.trim() && name.trim() !== n.name) onRename(n.id, name.trim());
              },
            },
          },
        };
      }) as Node[]).concat(blocks.nodes);
  const [nodes, setNodes] = useState<Node[]>(make);
  useEffect(() => {
    if (!heightsRef) return;
    const heights: Record<string, number> = {};
    for (const n of nodes) if (!isBlockId(n.id) && n.measured?.height) heights[n.id] = n.measured.height;
    heightsRef.current = heights;
  }, [nodes, heightsRef]);
  // Nově postavené uzly dostanou změřené rozměry z předchozí verze: React Flow by je jinak do přeměření
  // skryl (visibility: hidden) a rozepsaná textarea v kartě by při každé změně výběru ztratila fokus.
  useEffect(() => {
    setNodes((previous) => {
      const measured = new Map(previous.map((n) => [n.id, n]));
      return make().map((n) => {
        const old = measured.get(n.id);
        return old?.measured ? { ...n, measured: old.measured, width: old.width, height: old.height } : n;
      });
    });
  }, [graph, state, parent, selected, multiSelected, selectedBlock, editing, disabled, blocks, openBlocks, tagFilter, sourceContext?.project, sourceContext?.workspace, usage, assignmentStatuses, frontier.rows, leases, sourceStatuses, work, scenarios, confirmError, movedCards]);
  // Výběr hlášený nahoru: poslední známý výběr na plátně, aby změny během tahu obdélníku nebublaly
  // do App znovu a znovu, když se výběr nezměnil. Uzly samy dál jdou přes updater (tah karty).
  const latestNodes = useRef(nodes);
  latestNodes.current = nodes;
  const onNodesChange = (changes: Parameters<typeof applyNodeChanges>[0]) => {
    setNodes((n) => applyNodeChanges(changes, n));
    if (!reportsSelection(changes)) return;
    const before = selectionIds(latestNodes.current);
    latestNodes.current = applyNodeChanges(changes, latestNodes.current);
    const ids = selectionIds(latestNodes.current);
    if (!sameSelection(ids, before)) onMultiSelect(ids);
  };
  // Delete / Backspace smaže výběr — jen mimo psaní a jen tehdy, když klávesa míří na plátno
  // (nebo nikam, tělo stránky); tlačítko v inspektoru ani dialog ji nedostanou.
  const deleteSelection = useRef(onDeleteSelection);
  deleteSelection.current = onDeleteSelection;
  useEffect(() => {
    if (disabled) return;
    const key = (event: KeyboardEvent) => {
      if (!isDeleteKey(event, event.target)) return;
      const target = event.target;
      const onBoard = target === document.body || target === document.documentElement ||
        (target instanceof Node && !!surface.current?.contains(target));
      if (!onBoard) return;
      event.preventDefault();
      deleteSelection.current();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [disabled]);
  const [viewport, setViewport] = useState<Viewport>(() => {
    try {
      return JSON.parse(localStorage.getItem("viewport:" + scope) ?? "null") ?? { x: 60, y: 90, zoom: 1 };
    } catch {
      return { x: 60, y: 90, zoom: 1 };
    }
  });
  // Puštěná položka knihovny potřebuje souřadnice vrstvy, ne obrazovky; přepočet umí jen živá instance
  // React Flow, a ta se sem dostane jedinou cestou — přes onInit, protože plátno si ReactFlow vykresluje samo.
  const flow = useRef<ScreenToFlow | null>(null);
  const surface = useRef<HTMLDivElement>(null);
  const consumeReveal = useRef(onRevealed);
  consumeReveal.current = onRevealed;
  useEffect(() => {
    if (!reveal || reveal.scope !== scope) return;
    let frame = 0;
    let attempts = 0;
    const focus = () => {
      const instance = flow.current;
      const node = instance?.getNode(reveal.id);
      const rect = surface.current?.getBoundingClientRect();
      if (!instance || !node?.measured?.width || !node.measured.height || !rect?.width) {
        if (++attempts < 90) frame = requestAnimationFrame(focus);
        else consumeReveal.current?.(reveal.nonce);
        return;
      }
      const visible = { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
      const editor = surface.current?.closest(".editor-frame") ?? surface.current?.parentElement?.parentElement;
      const overlays = Array.from(editor?.querySelectorAll(".panel-drawer, .dock-rail, .inspector") ?? [])
        .map((panel) => panel.getBoundingClientRect()).sort((left, right) => left.left - right.left);
      for (const overlay of overlays) {
        if (!overlay.width || overlay.bottom <= rect.top || overlay.top >= rect.bottom) continue;
        if (overlay.left <= rect.left + 1 && overlay.right > visible.left) visible.left = Math.min(rect.right, overlay.right);
        else if (overlay.left < visible.left + 1 && overlay.right > visible.left) visible.left = Math.min(rect.right, overlay.right);
        else if (overlay.right >= rect.right - 1 && overlay.left < visible.right) visible.right = Math.max(rect.left, overlay.left);
      }
      const target = revealNodeCenter(rect, visible, { ...node.position, width: node.measured.width, height: node.measured.height }, instance.getZoom());
      if (target) void instance.setCenter(target.x, target.y, { zoom: target.zoom });
      consumeReveal.current?.(reveal.nonce);
    };
    frame = requestAnimationFrame(focus);
    return () => cancelAnimationFrame(frame);
  }, [reveal, scope]);
  const ids = new Set(nodes.map((n) => n.id));
  // Komentář nemá porty ani úchyty (nekreslí se), ale tah myší z jiné karty by na něj přesto mohl dopadnout.
  const commentIds = new Set(graph.nodes.filter((n) => n.kind === "comment").map((n) => n.id));
  // Oblast má jen úchyt toku (`flow`): smí se propojit jen s jinou oblastí, nikdy s kartou ani komentářem.
  const areaIds = new Set(graph.nodes.filter((n) => n.kind === "area").map((n) => n.id));
  // Vazba z portu `action`/`rule` vede z téhož úchytu jako blok, vazba z tlačítka bloku z úchytu
  // `block:<blockId>:<portId>` uvnitř karty; starší vazba bez portu = `next`. Vzhled řeší board-model.
  const addedEdges = useAddedPulse(graph.edges.map(edge => edge.id));
  const edges: Edge[] = graph.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e): Edge => ({ ...e, ...edgeAppearance(e, state.nodes[e.source]?.blocks?.find(b => b.id === e.sourceBlockId)?.ports?.find(p => p.id === e.sourcePortId)), animated: addedEdges.includes(e.id),
      // Předávka jen barvou: zelená vazba = zpráva je předaná; malá jantarová obálka = hotová karta ji nenechala.
      ...handoffLook(handoffMark(e, state, graph.nodes), edgeAppearance(e).style) }))
    .concat(blocks.edges);
  return (
    <div
      ref={surface}
      className="board-surface"
      data-testid="board-surface"
      /* Capture fáze: d3 zoom zastavuje dvojklik na plátně dřív, než by probublal. */
      onDoubleClickCapture={(event) => {
        // Jen prázdné plátno: dvojklik na kartu zůstává vstupem do vnitřního plátna.
        const target = event.target as HTMLElement;
        if (disabled || !target.classList.contains("react-flow__pane")) return;
        const rect = event.currentTarget.getBoundingClientRect();
        onCreateAt(
          Math.round((event.clientX - rect.left - viewport.x) / viewport.zoom) - 136,
          Math.round((event.clientY - rect.top - viewport.y) / viewport.zoom) - 84,
        );
      }}
      /* Tažení z knihovny: bez preventDefault by prohlížeč drop vůbec nepustil. Kurzor „kopírovat“
         dostane jen náš typ dat — cizí tažení (soubor, text) plátno nebere a projde dál nezměněné. */
      onDragOver={(event) => {
        if (disabled || !dropTypeOf(event.dataTransfer.types)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      }}
      onDrop={(event) => {
        const dragType = disabled ? null : dropTypeOf(event.dataTransfer.types);
        if (!dragType) return;
        event.preventDefault();
        const itemId = event.dataTransfer.getData(dragType);
        if (!itemId) return;
        const rect = event.currentTarget.getBoundingClientRect();
        const at = flow.current?.screenToFlowPosition({ x: event.clientX, y: event.clientY }) ?? {
          x: (event.clientX - rect.left - viewport.x) / viewport.zoom,
          y: (event.clientY - rect.top - viewport.y) / viewport.zoom,
        };
        const drop = dragType === AGENT_DRAG_TYPE ? onAgentDrop : onCatalogDrop;
        drop(itemId, Math.round(at.x) - CARD_GRAB.x, Math.round(at.y) - CARD_GRAB.y, dropTargetOf(event.target));
      }}
    >
      <div className="board-bar nodrag nopan" role="toolbar" aria-label="Stav sektoru">
        <WorkNow overview={work?.data} error={work?.error} sectorId={parent} open={onSelect} />
        {parent && onAutonomy && graph.nodes.find(n => n.id === parent)?.kind === "sector" &&
          <SectorAutonomy key={scope + parent} sectorId={parent} name={graph.nodes.find(n => n.id === parent)!.name}
            grant={state.autonomy?.[parent]} disabled={disabled} save={(until, who, note) => onAutonomy(parent, until, who, note)} />}
        {parent && onSaveSector && graph.nodes.find(n => n.id === parent)?.kind === "sector" &&
          <SectorGateEditor sector={graph.nodes.find(n => n.id === parent)!} graph={graph} disabled={disabled} save={onSaveSector} />}
        {/* Počet ke schválení jen jednou: v sektoru ho nese souhrn hromadného potvrzení. */}
        {parent && graph.nodes.find(n => n.id === parent)?.kind === "sector" && onConfirmSector
          ? <ConfirmSectorProposals key={scope + JSON.stringify(proposalsIn(graph, state, parent))}
            proposals={proposalsIn(graph, state, parent).map(p => ({ ...p, readiness: evidenceReadiness(state.nodes[p.id]?.evidence, graph.nodes.find(n => n.id === p.id)) }))}
            disabled={disabled} confirm={ids => onConfirmSector(parent, ids)} />
          : <span className="board-bar__chip">Ke schválení: {proposalCount(graph, state, parent)}</span>}
        <button type="button" aria-pressed={showFrontier} onClick={() => setShowFrontier(value => !value)}>Frontier · {showFrontier ? "zapnuto" : "vypnuto"}</button>
        {frontier.error && <p role="alert">{frontier.error}</p>}
      </div>
      <ReactFlow
        colorMode={useDesktopAppearance().theme}
        onInit={(instance) => { flow.current = instance; }}
        nodes={nodes}
        edges={edges.map((e) => ({ ...e, selected: e.id === selectedEdge }))}
        nodeTypes={nodeTypes}
        defaultViewport={viewport}
        minZoom={0.15}
        maxZoom={2}
        nodesDraggable={!disabled}
        snapToGrid={settings.snap}
        snapGrid={[settings.gridSize, settings.gridSize]}
        nodesConnectable={!disabled}
        deleteKeyCode={null}
        zoomOnDoubleClick={false}
        // Vybraná oblast se nesmí vyhouplout nad karty: React Flow by ji jinak z výchozí logiky
        // vrstvení vytáhl nahoru bez ohledu na zIndex uzlu.
        elevateNodesOnSelect={false}
        onNodesChange={onNodesChange}
        // Tah levým tlačítkem po prázdném plátně táhne obdélník výběru (stačí zasáhnout kus karty);
        // posun je prostřední / pravé tlačítko nebo mezerník + tah, kolečko dál zoomuje.
        selectionOnDrag
        panOnDrag={[1, 2]}
        selectionMode={SelectionMode.Partial}
        onNodeClick={(event, n) => {
          if (isBlockId(n.id)) return;
          // Komentář nemá bloky ani knihovnu: klik na něj jen vybere lístek, žádné směrování na blok.
          if (n.type === "comment") { onSelect(n.id); return; }
          // Klik dopadl buď na plochu bloku v kartě (nese data-block-id), nebo jinam na kartu.
          const hit = (event.target as HTMLElement).closest<HTMLElement>("[data-block-id]");
          hit?.dataset.blockId ? onSelectBlock(n.id, hit.dataset.blockId) : onSelect(n.id);
        }}
        onEdgeClick={(_, edge) => !isBlockId(edge.target) && onSelectEdge(edge.id)}
        onPaneClick={onClear}
        onNodeDoubleClick={(_, n) => !isBlockId(n.id) && n.type !== "comment" && n.type !== "area" && onEnter(n.id)}
        onNodeDragStop={(_, dragged) => {
          const block = parseBlockId(dragged.id);
          if (block) {
            // Blok se táhne sám za sebe: kartou nehne a magnetismem neprochází (v otisku patří ke své kartě).
            // Ukládá se posun proti uložené pozici karty, aby ho karta při svém tahu vzala s sebou.
            const card = graph.nodes.find((n) => n.id === block.nodeId);
            if (card) onBlockMove(block.nodeId, block.port, dragged.position.x - card.x, dragged.position.y - card.y);
            return;
          }
          // Pevná tělesa: karta i oblast mají pevnou hranu, takže se při dosednutí počítá s plochou celé
          // vrstvy — s otisky karet (i jejich viditelných bloků) a s rámečky oblastí.
          const heights: Record<string, number> = {};
          for (const n of nodes) if (!isBlockId(n.id) && n.measured?.height) heights[n.id] = n.measured.height;
          const footprints = layerFootprints(graph, parent, state, openBlocks, heights);
          const layerAreas = graph.nodes.filter((n) => n.parentId === parent && n.kind === "area" && !!n.size);
          const stored = graph.nodes.find((n) => n.id === dragged.id);
          if (areaIds.has(dragged.id)) {
            // Puštěný rámeček se odsune od jiných oblastí i od cizích karet (těch, které v něm před tahem
            // nebyly — členové jedou s ním). Nahoru jde až ustálený posun; App ho promítne moveWithMembers.
            if (!stored?.size) return;
            const memberIds = new Set(membersOf(stored, graph.nodes).map((n) => n.id));
            const settled = settleArea(
              { id: stored.id, x: dragged.position.x, y: dragged.position.y, w: stored.size.w, h: stored.size.h },
              layerAreas
                .filter((n) => n.id !== stored.id)
                .map((n) => ({ id: n.id, x: n.x, y: n.y, w: n.size!.w, h: n.size!.h })),
              footprints.filter((f) => !memberIds.has(f.id)),
            );
            onAreaMove(dragged.id, settled.x - stored.x, settled.y - stored.y);
            return;
          }
          // Karta: střed rozhodne, jestli patří dovnitř oblasti (pak se vejde celá), nebo ven (pak se celá
          // odsune za hranu), a teprve pak se vytáhne z překryvu s ostatními kartami. Až pak se pozice uloží.
          const moved = footprints.find((f) => f.id === dragged.id);
          const others = footprints.filter((f) => f.id !== dragged.id);
          const resolved =
            moved && stored
              ? settleCard(
                  { ...stored, x: dragged.position.x, y: dragged.position.y },
                  {
                    ...moved,
                    x: moved.x + (dragged.position.x - stored.x),
                    y: moved.y + (dragged.position.y - stored.y),
                  },
                  others,
                  layerAreas,
                )
              : dragged.position;
          onPosition(dragged.id, resolved.x, resolved.y);
        }}
        onConnect={(c) => {
          if (!c.target || isBlockId(c.target)) return;
          if (commentIds.has(c.source ?? "") || commentIds.has(c.target)) return;
          // Tok (`flow`) smí spojit jen dvě oblasti; oblast s kartou nebo naopak se nepropojí nikdy.
          const sourceIsArea = areaIds.has(c.source ?? "");
          const targetIsArea = areaIds.has(c.target);
          if (sourceIsArea !== targetIsArea) return;
          onConnect(c);
        }}
        onMoveEnd={(_, v) => {
          setViewport(v);
          localStorage.setItem("viewport:" + scope, JSON.stringify(v));
        }}
      >
        {settings.showGrid && <Background color="var(--canvas-dot)" gap={settings.gridSize} />}
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) =>
            isBlockId(n.id)
              ? "#c98a1e"
              : n.type === "comment"
                ? "#c9b25a"
                : n.type === "area"
                  ? "#5b6cc9"
                  : (n.data as NodeCardData).view?.kind === "sector"
                    ? "#5f947f"
                    : "#526b89"
          }
          maskColor="rgba(15,19,24,.75)"
        />
      </ReactFlow>
      {!disabled && (
        <p className="board-hint" data-testid="board-hint">
          Tah po plátně = výběr · Delete = smazat vybrané · prostřední tlačítko nebo mezerník + tah = posun · dvojklik na prázdné plátno = nový uzel · dvojklik na kartu = do hloubky · z portu bloku se táhne vazba na jinou kartu
        </p>
      )}
    </div>
  );
}

/** Vzhled vazby podle předávky: bez textu. Předáno = zelená čára, chybí = drobná jantarová obálka;
 *  plánovací vazby (zdroj ještě nehotový) zůstávají beze změny, aby plátno nebylo ukřičené. */
function handoffLook(mark: "sent" | "missing" | null, style: Edge["style"]): Partial<Edge> {
  if (mark === "sent") return { style: { ...style, stroke: "#22c55e", strokeWidth: 2 } };
  if (mark !== "missing") return {};
  return {
    label: "✉",
    labelStyle: { fill: "#f59e0b", fontSize: 12 },
    labelBgStyle: { fill: "#111827", stroke: "#f59e0b" },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 4,
    labelShowBg: true,
  };
}
