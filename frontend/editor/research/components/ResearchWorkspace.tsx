import type { WorkScope } from "@/shared/work-scope/logic/work-scope";
import { researchContext } from "../logic/research-context";
import { useEffect, useMemo, useState } from "react";
import { MarkerType, ReactFlowProvider, useNodesInitialized, useNodesState, useReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import FlowSurface, { type SurfaceView } from "@/shared/flow-editor/components/FlowSurface";
import ResearchCard, { type ResearchFlowNode } from "./ResearchCard";
import ResearchInspector from "./ResearchInspector";
import { RELATION_LABELS, researchLayout, topicLabel } from "../logic/research-model";
import { useResearch, useResearchDetail, useResearchEdge } from "../logic/use-research";
import { reviewRoute } from "../logic/review-route";
import "../styles/research.css";
type Props = { workScope: WorkScope; project: string; workspace: string; nodes: { id: string; name: string }[]; readOnly?: boolean; onOpenNode: (id: string) => void; onDraw: (id: string) => void };
const nodeTypes = { research: ResearchCard };
const VIEW: SurfaceView = { minZoom: .15, maxZoom: 1.6, fitPadding: .2, dotGap: 22, dotColor: "var(--canvas-dot)", controls: "top-left", minimapLabel: "Minimapa rešerše", minimapClass: "research-workspace__minimap" };
export default function ResearchWorkspace(props: Props) {
  return <ReactFlowProvider><Workspace {...props} /></ReactFlowProvider>;
}
function Workspace({ workScope, project, workspace, nodes: structureNodes, readOnly = false, onOpenNode, onDraw }: Props) {
  const scope = { project, workspace };
  const [archived, setArchived] = useState(false); const [query, setQuery] = useState(""); const [topic, setTopic] = useState(""); const [platform, setPlatform] = useState("");
  const [selected, setSelected] = useState<{ kind: "card" | "edge"; id: string } | null>(null); const [revision, setRevision] = useState<number>();
  const data = useResearch(scope, archived);
  const { scopedCards, scopedEdges, currentCard, currentEdge } = useMemo(() => researchContext(data.cards, data.edges, workScope, selected), [data.cards, data.edges, workScope.projectId, workScope.nodeId, selected]);
  const effectiveScope = { project, workspace: data.workspace ?? workspace };
  useEffect(() => {
    const target = reviewRoute(window.location.search, { project, workspace });
    const route = new URLSearchParams(window.location.search);
    const source = route.get("project") === project && route.get("workspace") === workspace ? route.get("researchSource") : null;
    setSelected(target ? { kind: "card", id: target.card } : source ? { kind: "card", id: source } : null);
    const pin = Number(route.get("researchRevision"));
    setRevision(source && Number.isSafeInteger(pin) && pin > 0 ? pin : undefined);
    setQuery(""); setTopic(""); setPlatform("");
  }, [project, workspace, workScope.nodeId]);
  const detail = useResearchDetail(effectiveScope, currentCard?.id ?? null, revision, currentCard?.revision);
  const edgeDetail = useResearchEdge(effectiveScope, currentEdge?.id ?? null, revision, currentEdge?.revision);
  const topics = useMemo(() => [...new Map(scopedCards.map(card => [JSON.stringify(card.topicPath), topicLabel(card.topicPath)])).entries()].sort((a,b) => a[1].localeCompare(b[1], "cs")), [scopedCards]);
  const platforms = useMemo(() => [...new Set(scopedCards.flatMap(card => card.platforms))].sort(), [scopedCards]);
  const layout = useMemo(() => researchLayout(scopedCards, scopedEdges, query, topic, platform), [scopedCards, scopedEdges, query, topic, platform]);
  const visible = layout.cards; const positions = layout.positions;
  const nextNodes = useMemo<ResearchFlowNode[]>(() => visible.map(card => ({ id: card.id, type: "research", data: { card }, position: positions.get(card.id)!, selected: selected?.kind === "card" && selected.id === card.id })), [visible, positions, selected]);
  const [nodes, setNodes, onNodesChange] = useNodesState<ResearchFlowNode>(nextNodes);
  useEffect(() => setNodes(previous => nextNodes.map(node => ({ ...node, measured: previous.find(item => item.id === node.id)?.measured }))), [nextNodes, setNodes]);
  const { fitView } = useReactFlow(); const initialized = useNodesInitialized();
  const layoutKey = JSON.stringify([...positions]);
  useEffect(() => {
    if (!initialized) return;
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => { void fitView({ padding: VIEW.fitPadding, maxZoom: 1 }); }); });
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); };
  }, [layoutKey, initialized, fitView]);
  const edges = layout.edges.map(edge => ({ id: edge.id, source: edge.fromId, target: edge.toId, label: RELATION_LABELS[edge.relation], markerEnd: { type: MarkerType.ArrowClosed, color: "var(--ink-muted)" }, selected: selected?.kind === "edge" && selected.id === edge.id, style: { stroke: "var(--ink-muted)", strokeWidth: 1.8, ...(edge.archived ? { strokeDasharray: "5 5", opacity: .5 } : {}) }, labelStyle: { fill: "var(--ink)", fontSize: 12 }, labelBgStyle: { fill: "var(--surface-1, var(--surface))" }, labelBgPadding: [8, 5] as [number, number] }));
  const selectCard = (id: string) => { setRevision(undefined); setSelected({ kind: "card", id }); };
  const nodeNames = useMemo(() => new Map(structureNodes.map(node => [node.id, node.name])), [structureNodes]);
  return <div className="research-workspace">
    <div className="research-workspace__heading"><div><h2>Rešerše</h2><p>Co víme, čím to dokládáme a proč pokračujeme dál.</p></div><span title="Pracovní kontext">{structureNodes.find(node => node.id === workScope.nodeId)?.name ?? "Celý projekt"} · {scopedCards.length} kartiček · {layout.edges.length} vazeb</span></div>
    <div className="research-workspace__toolbar">
      <input type="search" aria-label="Hledat v rešerši" placeholder="Téma, zjištění, otázka nebo ticket…" value={query} onChange={event => setQuery(event.target.value)} />
      <select aria-label="Téma rešerše" value={topic} onChange={event => setTopic(event.target.value)}><option value="">Všechna témata</option>{topics.map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select>
      <select aria-label="Platforma zdroje" value={platform} onChange={event => setPlatform(event.target.value)}><option value="">Všechny zdroje</option>{platforms.map(value => <option key={value}>{value}</option>)}</select>
      <label><input type="checkbox" checked={archived} onChange={event => { setArchived(event.target.checked); setSelected(null); }} />Včetně archivu</label>
      <button type="button" onClick={() => void data.reload()}>Obnovit</button>
    </div>
    {data.error && <div className="research-workspace__error" role="alert">{data.error}</div>}
    <div className="research-workspace__body">
      <FlowSurface nodes={nodes} edges={edges} nodeTypes={nodeTypes} view={VIEW} onNodesChange={onNodesChange}
        rootProps={{ className: "research-workspace__canvas", "data-testid": "research-canvas" }}
        flowProps={{ nodesDraggable: false, nodesConnectable: false, onNodeClick: (_, node) => selectCard(node.id), onEdgeClick: (_, edge) => { setRevision(undefined); setSelected({ kind: "edge", id: edge.id }); }, onPaneClick: () => setSelected(null) }}
        overlay={data.loading ? <div className="research-workspace__empty" role="status"><h3>Načítám rešerši…</h3></div> : !visible.length ? <div className="research-workspace__empty"><h3>{data.error ? "Rešerši se nepodařilo načíst" : scopedCards.length ? "Žádná shoda ve filtrech" : "Zatím žádná zjištění"}</h3><p>{data.error ? "Zkuste obnovit data. Uložené podklady zůstávají zachované." : scopedCards.length ? "Zkuste jiné téma nebo zdroj." : "Srdce sem ukládá podklady k otázkám, důkazy a cestu k řešení. Každá kartička patří ke konkrétní problematice."}</p></div> : undefined} />
      {selected && (currentCard || currentEdge) && <ResearchInspector scope={effectiveScope} edgeDetail={edgeDetail.detail} card={currentCard} edge={edgeDetail.detail?.edge ?? currentEdge} cards={scopedCards} detail={detail.detail} loading={selected.kind === "edge" ? edgeDetail.loading : detail.loading} error={selected.kind === "edge" ? edgeDetail.error : detail.error} revision={revision} writing={data.writing} readOnly={readOnly} nodeNames={nodeNames}
        onRevision={setRevision} onSelect={selectCard} onClose={() => setSelected(null)} onArchive={(entity,id,rev,value) => { void data.archive(entity,id,rev,value).then(ok => { if (ok && !archived) setSelected(null); }); }} onOpenNode={onOpenNode} onDraw={onDraw} />}
    </div>
  </div>;
}
