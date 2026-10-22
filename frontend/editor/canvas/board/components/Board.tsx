// Plátno: React Flow nad grafem. Kartu skládá NodeCard z modelu karty (editor/canvas/node-card),
// bloky Akce / Pravidla dodává rodič (App) už spočítané. Board jen mapuje data a bublá události nahoru.
// Výkon (docs/navrhy/2026-10-14-vykon-platna.md, opravy 3 až 5): uzly vrstvy staví čistá funkce bez closures
// (`logic/layer-nodes.ts`), nezměněné karty drží starý objekt (`logic/stable-nodes.ts`), akce jdou přes
// kontext (`logic/use-board-actions.ts`). Od 80 uzlů se kreslí jen viditelné (`CULL_VISIBLE`); rozepsané texty
// karet mimo obraz drží `node-card/logic/block-drafts.ts`. Velká vrstva: MiniMap do 500 uzlů, rovné vazby nad
// 1000 vazbami (oprava 10) a čip u stropu grafu (`logic/graph-cap.ts`, oprava 8).
import { useEffect, useMemo, useRef, useState } from "react";
import { useDesktopAppearance } from "@/app/logic/desktop-appearance";
import FaceSummary from "@/editor/canvas/card-face/components/FaceSummary";
import { useWorkOverview } from "@/editor/canvas/node-card/logic/use-work-overview";
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
} from "@xyflow/react";
import type { SurfaceSettings } from "@/shared/surface-settings/logic/workspace-settings";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState, Rule } from "@/shared/desktop-state/logic/types";
import { buildBoardIndex } from "@/editor/canvas/board/logic/board-index";
import { layerEdges, simpleEdges } from "@/editor/canvas/board/logic/board-edges";
import { capWarning } from "@/editor/canvas/board/logic/graph-cap";
import { buildLayerNodes, movedKey, shouldCull } from "@/editor/canvas/board/logic/layer-nodes";
import { reuseNodes } from "@/editor/canvas/board/logic/stable-nodes";
import { useBoardActions } from "@/editor/canvas/board/logic/use-board-actions";
import { CardActionsContext, type CardBlockEvent } from "@/editor/canvas/node-card/logic/card-actions";
import { useFrontier } from "@/editor/canvas/node-card/logic/use-frontier";
import { useCardChecklist } from "@/editor/canvas/card-checklist/logic/card-checklist";
import SectorGateEditor from "@/editor/canvas/node-card/components/SectorGateEditor";
import SectorAutonomy from "@/editor/canvas/node-card/components/SectorAutonomy";
import "@/editor/canvas/board/styles/board-bar.css";
import { useAgentState } from "@/hub/oporahub-agent-state/logic/use-agent-state";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { layerFootprints } from "@/editor/canvas/board/logic/layout-model";
import { settleArea, settleCard } from "@/editor/canvas/board/logic/solid-bodies";
import NodeCard, { type NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { UsageSummary } from "@/editor/canvas/node-card/logic/use-usage";
import CommentCard from "@/editor/canvas/comment-card/components/CommentCard";
import AreaCard from "@/editor/canvas/area/components/AreaCard";
import { membersOf } from "@/editor/canvas/area/logic/area-model";
import { blockNodeTypes } from "@/editor/workflow/blocks/components/CanvasBlock";
import { isBlockId, parseBlockId, type BlockPort, type OpenBlocks } from "@/editor/workflow/blocks/logic/block-model";
import { isDeleteKey, reportsSelection, sameSelection, selectionIds } from "../logic/box-selection";
import { useBriefVault } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { indexVault } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";

const nodeTypes = { canvas: NodeCard, comment: CommentCard, area: AreaCard, ...blockNodeTypes };
/** Nad tolika uzly vrstvy se MiniMap nekreslí: React Flow ji překresluje při každé změně uzlů. */
const MINIMAP_MAX = 500;

export type { CardBlockEvent };

export default function Board({
  sourceStatuses,
  onRealizeSource,
  onAutonomy,
  onSaveSector,
  onConfirmProposal,
  leases,
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
  revision,
  digest,
  overlay,
}: {
  /** Vrstva nad kartami uvnitř React Flow (odznaky etap OporaHubu); skládá ji App. */
  overlay?: import("react").ReactNode;
  usage?: UsageSummary | null;
  sourceStatuses?: Record<string, import("@/editor/canvas/node-card/logic/use-source-status").SourceStatus>;
  onRealizeSource?: (nodeId: string, commit: string, prUrl: string) => Promise<void>;
  onConfirmProposal?: (nodeId: string) => Promise<boolean>;
  onSaveSector?: (node: import("@/shared/types/logic/types").CanvasNode) => void;
  onAutonomy?: (sectorId: string, until: string, grantedBy: string, note: string) => Promise<void>;
  leases?: Record<string, import("@/editor/canvas/node-card/logic/use-leases").CardLease>;
  onRuleWrite?: (expected: Rule, item: Rule) => Promise<boolean>;
  onRuleReview?: (rule: Rule, decision: import("@/shared/desktop-state/logic/agent-rule").RuleReviewDecision) => Promise<boolean>;
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
  /** Revize stavu (`desktop.revision`) a otisk grafu (`view.digest`): klíče pro obnovu overlayů. */
  revision?: number | null;
  digest?: string;
}) {
  // Overlaye se obnovují podle čísel (revize stavu a otisk grafu), ne podle objektů: debounce v pollingu
  // tak sloučí víc změn jedné editace. Když je rodič nepředá, poslouží počítadlo změn grafu a stavu.
  const changes = useChangeCount(graph, state);
  const stateKey = revision ?? `local:${changes}`;
  const workKey = `${digest ?? ""}:${stateKey}`;
  const frontier = useFrontier(sourceContext, parent, true, stateKey);
  const checklists = useCardChecklist(sourceContext, parent, stateKey);
  // Strom schránky se obnoví jen při změně odkazů karet a Podnětů do schránky, ne při každé změně stavu.
  const vaultRefs = useMemo(() => JSON.stringify(Object.entries(state.nodes).map(([id, node]) =>
    [id, node.fragmentRefs ?? [], (node.ideas ?? []).map((idea) => idea.fragmentId ?? "")])), [state.nodes]);
  const vault = useBriefVault(sourceContext, vaultRefs);
  const vaultIndex = useMemo(() => indexVault(vault.tree?.roots ?? []), [vault.tree]);
  // Jeden index grafu a stavu na přestavbu: karty z něj čtou místo procházení všech uzlů pro každou kartu.
  // Závisí jen na grafu a stavu, takže výběr ani polling overlayů ho nepřestaví.
  const index = useMemo(() => buildBoardIndex(graph, state), [graph, state]);
  const multiSet = useMemo(() => new Set(multiSelected), [multiSelected]);
  // Jediný zdroj stavu karet: sdílené čtení agent-state (stejný poller jako OporaHub a Velín).
  const agentState = useAgentState(sourceContext?.project ?? "", sourceContext?.workspace ?? "").state;
  const agent = useMemo(() => ({ cards: new Map((agentState?.cards ?? []).map((card) => [card.nodeId, card])),
    decisions: agentState?.decisions ?? [] }), [agentState]);
  const finished = useMemo(() => new Set((agentState?.cards ?? []).filter((card) =>
    card.reason === "card_closed" || card.reason === "plan_written_back").map((card) => card.nodeId)), [agentState]);
  const movedCards = useAddedPulse(graph.nodes.map(movedKey));
  const movedSet = useMemo(() => new Set(movedCards), [movedCards]);
  const work = useWorkOverview(sourceContext?.project ?? "", sourceContext?.workspace ?? "", workKey);
  const actions = useBoardActions({ disabled, nameOf: (id) => index.byId.get(id)?.name, onSelect, onTagFilter, onEditing, onRename,
    onCommentText, onAreaResize, onTogglePort, onCardBlock, onConfirmProposal, onRealizeSource,
    onRuleWrite, onRuleReview, sourceContext });
  // Schopnosti rodiče jako booleany: nové inline callbacky v App vrstvu nepřestaví, jejich přítomnost ano.
  const can = { realize: !!onRealizeSource, rules: !!onRuleWrite && !!onRuleReview };
  const make = (): Node[] => buildLayerNodes({ graph, state, index, parent, selected, multiSelected: multiSet, selectedBlock, editing,
    disabled, openBlocks, tagFilter, moved: movedSet, vaultIndex, checklists, usage, frontier: frontier.rows, work,
    leases, sourceStatuses, agent, sourceContext, can }).concat(blocks.nodes);
  const [nodes, setNodes] = useState<Node[]>(make);
  // Výšky pro „Srovnat“ v App a pro dosednutí tažené karty: jen změření v plném detailu. Karta z dálky
  // (`data-detail="far"`) je nižší; její míra se nikdy nebere jako plná a do první plné míry platí odhad.
  const measuredAt = useRef(new Map<string, { measured: object; height?: number }>());
  const fullHeights = useRef<Record<string, number>>({});
  useEffect(() => {
    const before = measuredAt.current;
    const changed = nodes.some((n) => !isBlockId(n.id) && n.measured?.height && before.get(n.id)?.measured !== n.measured);
    // Úroveň detailu karet se čte z DOM jednou za změnu měření, ne pro každou kartu zvlášť.
    const detail = new Map<string, string>();
    if (changed) for (const card of Array.from(surface.current?.querySelectorAll<HTMLElement>(".node-card[data-detail]") ?? []))
      detail.set((card.dataset.testid ?? "").slice("node-card-".length), card.dataset.detail ?? "");
    const next = new Map<string, { measured: object; height?: number }>();
    const heights: Record<string, number> = {};
    for (const n of nodes) {
      if (isBlockId(n.id) || !n.measured?.height) continue;
      const kept = before.get(n.id);
      const entry = kept?.measured === n.measured ? kept
        : { measured: n.measured, height: n.type !== "canvas" || detail.get(n.id) === "full" ? n.measured.height : kept?.height };
      next.set(n.id, entry);
      if (entry.height !== undefined) heights[n.id] = entry.height;
    }
    measuredAt.current = next;
    fullHeights.current = heights;
    if (heightsRef) heightsRef.current = heights;
  }, [nodes, heightsRef]);
  // Přestavba vrací starý objekt každé karty, které se data nezměnila (React Flow i memo ji přeskočí), a nově
  // postaveným uzlům přenese změřené rozměry: React Flow by je jinak do přeměření skryl (visibility: hidden)
  // a rozepsaná textarea v kartě by při každé změně výběru ztratila fokus.
  useEffect(() => {
    setNodes((previous) => reuseNodes(previous, make()));
  }, [graph, state, parent, selected, multiSelected, selectedBlock, editing, disabled, blocks, openBlocks, tagFilter, sourceContext?.project,
    sourceContext?.workspace, usage, frontier.rows, leases, sourceStatuses, work, movedCards,
    checklists, vaultIndex, agent, can.realize, can.rules]);
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
  const surface = useRef<HTMLDivElement>(null);
  // Sada vykreslených id se mění jen s přidáním nebo odebráním uzlu, ne v každém snímku tažení; klíč z id
  // drží memo vazeb stabilní, dokud se množina uzlů nezmění.
  const idsKey = nodes.map((n) => n.id).join("\n");
  const ids = useMemo(() => new Set(idsKey ? idsKey.split("\n") : []), [idsKey]);
  // Komentář nemá porty ani úchyty (nekreslí se), ale tah myší z jiné karty by na něj přesto mohl dopadnout.
  const commentIds = useMemo(() => new Set(graph.nodes.filter((n) => n.kind === "comment").map((n) => n.id)), [graph.nodes]);
  // Oblast má jen úchyt toku (`flow`): smí se propojit jen s jinou oblastí, nikdy s kartou ani komentářem.
  const areaIds = useMemo(() => new Set(graph.nodes.filter((n) => n.kind === "area").map((n) => n.id)), [graph.nodes]);
  const addedEdges = useAddedPulse(graph.edges.map(edge => edge.id));
  const addedSet = useMemo(() => new Set(addedEdges), [addedEdges]);
  // Vazby se počítají jen při změně grafu, stavu, vykreslených uzlů, bloků, pulsu nebo výběru vazby.
  const edges: Edge[] = useMemo(() => layerEdges({ graph, state, ids, kinds: index.kinds, added: addedSet, selectedEdge, blockEdges: blocks.edges,
    simple: simpleEdges(graph, ids), finished: agentState?.cards ? finished : undefined }), [graph, state, ids, index, addedSet, selectedEdge, blocks.edges, finished, agentState]);
  const showMiniMap = useMemo(() => ids.size <= MINIMAP_MAX, [ids]);
  const cap = useMemo(() => capWarning(graph, Object.keys(state.nodes).length), [graph, state.nodes]);
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
    >
      <div className="board-bar nodrag nopan" role="toolbar" aria-label="Stav sektoru">
        <FaceSummary title={parent ? index.byId.get(parent)?.name ?? "" : ""}
          faces={nodes.flatMap((n) => n.type === "canvas" && (n.data as NodeCardData).face ? [(n.data as NodeCardData).face!] : [])}
          nextEdges={edges.filter((e) => e.className?.includes("edge-port-next")).length} />
        <span className="board-bar__grow" />
        {parent && onAutonomy && graph.nodes.find(n => n.id === parent)?.kind === "sector" &&
          <SectorAutonomy key={scope + parent} sectorId={parent} name={graph.nodes.find(n => n.id === parent)!.name}
            grant={state.autonomy?.[parent]} disabled={disabled} save={(until, who, note) => onAutonomy(parent, until, who, note)} />}
        {parent && onSaveSector && graph.nodes.find(n => n.id === parent)?.kind === "sector" &&
          <SectorGateEditor sector={graph.nodes.find(n => n.id === parent)!} graph={graph} disabled={disabled} save={onSaveSector} />}
        {frontier.error && <p role="alert">{frontier.error}</p>}
        {cap && <span className="board-bar__chip board-bar__cap" title={cap.title} data-testid="board-cap">{cap.text}</span>}
      </div>
      <JsonMirror id="oh-card-stages" value={agentState?.cards ?? null} />
      <CardActionsContext.Provider value={actions}>
      <ReactFlow
        colorMode={useDesktopAppearance().theme}
        // Jen viditelné uzly od 80 uzlů vrstvy (`CULL_VISIBLE` v logic/layer-nodes.ts, docs/navrhy/2026-10-14-vykon-platna.md):
        // odmontovaná karta si rozepsaný text vezme zpět z `node-card/logic/block-drafts.ts`.
        onlyRenderVisibleElements={shouldCull(nodes.length)}
        nodes={nodes}
        edges={edges}
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
          // Skutečné výšky (ne zjednodušené z oddálení); nezměřená karta mimo obraz dostane odhad.
          const footprints = layerFootprints(graph, parent, state, openBlocks, fullHeights.current, true);
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
        {overlay}
        {showMiniMap && <MiniMap
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
        />}
      </ReactFlow>
      </CardActionsContext.Provider>
      {!disabled && (
        <p className="board-hint" data-testid="board-hint">
          Tah po plátně = výběr · Delete = smazat vybrané · prostřední tlačítko nebo mezerník + tah = posun · dvojklik na prázdné plátno = nový uzel · dvojklik na kartu = do hloubky · z portu bloku se táhne vazba na jinou kartu
        </p>
      )}
    </div>
  );
}

/** Počítadlo změn referencí (náhradní klíč obnovy, když rodič nepředá revizi ani otisk). */
function useChangeCount(...values: unknown[]): number {
  const seen = useRef<{ values: unknown[]; count: number }>({ values, count: 0 });
  if (values.length !== seen.current.values.length || values.some((value, i) => !Object.is(value, seen.current.values[i])))
    seen.current = { values, count: seen.current.count + 1 };
  return seen.current.count;
}
