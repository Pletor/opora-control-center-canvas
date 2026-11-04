import { useMemo, useState, type ReactNode } from "react";
import { checkTargets } from "../logic/check-strip";
import { connectionError, portOf } from "../logic/connection-policy";
import { nodeTypeMap, specOf, withNodePorts, type FlowGraph, type NodeRun, type NodeTypeSpec, type Point, type PortRef, type PortSpec } from "../logic/flow-types";
import { flowEdges, flowNodes } from "../logic/flow-view";
import { foldEdges, groupNodes, hiddenNodes, noteNodes } from "../logic/frame-view";
import type { GraphDiff } from "../logic/graph-diff";
import { addConnected, addNode, connect, moveNode, removeEdge, removeNode, setEdgeVia, setNodeField, setParam } from "../logic/graph-edit";
import { addNote, groupFromSelection, setGroup, setNote, ungroup } from "../logic/graph-frames";
import { readinessIssues } from "../logic/readiness";
import type { RunOverlay } from "../logic/run-overlay";
import type { PlusRequest } from "../flow-node/logic/port-actions";
import NodePalette from "../node-palette/components/NodePalette";
import NodeInspector from "../node-inspector/components/NodeInspector";
import GroupInspector from "../flow-frame/components/GroupInspector";
import { arrangeLanes, laneNodes } from "../flow-lanes/logic/lanes";
import { linkableTypes, settleAdded } from "../flow-lanes/logic/layer-links";
import { effectiveLayer } from "../flow-lanes/logic/layers";
import FlowCanvas from "./FlowCanvas";
import FlowToolbar from "./FlowToolbar";
import "../flow-lanes/styles/flow-lanes.css";
import "../styles/flow-editor.css";

type Props = {
  graph: FlowGraph; types: readonly NodeTypeSpec[]; readOnly: boolean;
  overlay?: RunOverlay; diff?: GraphDiff | null; nodeRuns?: readonly NodeRun[];
  selected: string | null; onSelect: (nodeId: string | null) => void;
  /** Každá úprava vrací celý nový graf; uloží ho (jako draft verze) rodič. */
  onChange: (graph: FlowGraph) => void;
  /** Plátno toku (knihovna): poznámky, rámce a inspektor s poli uzlu (Data, Chyby, Poznámka). */
  frames?: boolean;
  /** Porty konkrétních uzlů podle jejich `params` (rodič je zjistí přes `POST /api/flow/node-ports`). */
  nodePorts?: ReadonlyMap<string, PortSpec[]>;
  /** Chyby kontroly grafu (`graph-check`); se seznamem pás „Kontrola grafu“ nahradí „Připraveno ke spuštění“. */
  checkErrors?: readonly string[] | null;
  /** Tlačítka navíc v pásu nástrojů (plátno knihovny: „Zadání“). */
  tools?: ReactNode;
};

/** Generický editor grafu verze workflow: plátno, paleta, inspektor a pás „Připraveno ke spuštění“ (u plátna toku pás
 * kontroly grafu). Neví nic o srdci ani o API; typy uzlů dostává z registru, stav běhu, rozdíl verzí, porty uzlů a chyby
 * kontroly hotové v props a změny hlásí nahoru. Stav sbalení rámců drží jen v prohlížeči (jako n8n). */
export default function FlowEditor({ graph, types, readOnly, overlay, diff, nodeRuns = [], selected, onSelect, onChange, frames = false, nodePorts, checkErrors, tools }: Props) {
  const registry = useMemo(() => withNodePorts(nodeTypeMap(types), nodePorts, graph), [types, nodePorts, graph]);
  const [palette, setPalette] = useState<{ port: PlusRequest | null } | null>(null);
  const [edge, setEdge] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [group, setGroupId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const issues = useMemo(() => checkErrors ? [] : readinessIssues(graph, registry), [graph, registry, checkErrors]);
  const targets = useMemo(() => checkTargets(checkErrors ?? [], graph), [checkErrors, graph]);
  const issueNodes = useMemo(() => new Set([...issues.flatMap((issue) => issue.nodeId ? [issue.nodeId] : []), ...targets.nodes]), [issues, targets]);
  const hidden = useMemo(() => hiddenNodes(graph, collapsed), [graph, collapsed]);
  const nodes = useMemo(() => {
    const cards = flowNodes(graph, registry, { overlay, diff, highlighted: selected, issues: issueNodes, readOnly });
    const shown = cards.filter((card) => !hidden.has(card.id));
    return [...laneNodes(shown), ...noteNodes(graph, readOnly), ...groupNodes(graph, cards, collapsed, targets.groups, group), ...shown];
  }, [graph, registry, overlay, diff, selected, issueNodes, readOnly, hidden, collapsed, targets, group]);
  const edges = useMemo(() => foldEdges(flowEdges(graph, { overlay, diff, readOnly }), graph, collapsed), [graph, overlay, diff, readOnly, collapsed]);

  const apply = (edit: () => FlowGraph) => {
    try { onChange(edit()); setMessage(""); } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  };
  const pick = (type: string) => {
    const port = palette?.port;
    apply(() => port ? settleAdded(addConnected(graph, registry, type, port), registry, port.nodeId) : settleAdded(addNode(graph, registry, type, freeSpot(graph)).graph, registry));
    setPalette(null);
  };
  // „Co dál?“: vazba upuštěná do prázdna otevře paletu zúženou na vrstvy, které smějí navázat (jako „+“ u portu).
  const dropEmpty = (from: PortRef) => { const kind = portOf(graph, registry, from)?.kind; if (kind && !readOnly) setPalette({ port: { ...from, kind } }); };
  const anchor = palette?.port && graph.nodes.find((item) => item.id === palette.port!.nodeId);
  const offered = useMemo(() => palette?.port && anchor ? linkableTypes(types, effectiveLayer(anchor, specOf(registry, anchor)), palette.port.direction) : types,
    [types, palette, anchor, registry]);
  const toggle = (id: string) => setCollapsed((old) => { const next = new Set(old); if (!next.delete(id)) next.add(id); return next; });
  const selectNode = (id: string | null) => { setGroupId(null); onSelect(id); };
  const node = graph.nodes.find((item) => item.id === selected) ?? null;
  const frame = graph.groups?.find((item) => item.id === group) ?? null;
  const run = node ? [...nodeRuns].reverse().find((item) => item.node_id === node.id) ?? null : null;
  const selectedEdge = graph.edges.find((item) => item.id === edge);

  return <div className="flow-editor" data-testid="flow-editor">
    <div className="flow-editor__main">
      {!readOnly && <FlowToolbar edge={selectedEdge} message={message} frames={frames} extra={tools} selection={picked.length} onPalette={() => setPalette({ port: null })}
        onRemoveEdge={() => { if (selectedEdge) apply(() => removeEdge(graph, selectedEdge.id)); setEdge(null); }}
        onNote={() => apply(() => addNote(graph, noteSpot(graph)))}
        onLanes={frames ? () => apply(() => arrangeLanes(graph, registry)) : undefined}
        onVia={frames && selectedEdge ? (via) => apply(() => setEdgeVia(graph, selectedEdge.id, via)) : undefined}
        onGroup={() => apply(() => { const made = groupFromSelection(graph, picked); setGroupId(made.group.id); onSelect(null); return made.graph; })}/>}
      <FlowCanvas nodes={nodes} edges={edges} readOnly={readOnly}
        frames={{ onNote: (id, patch) => apply(() => setNote(graph, id, patch)), onToggleGroup: toggle }}
        canConnect={(a: PortRef, b: PortRef) => !connectionError(graph, registry, a, b)}
        onSelectNode={selectNode} onSelectEdge={setEdge} onSelectGroup={frames ? (id) => { onSelect(null); setGroupId(id); } : undefined}
        onSelection={frames ? (ids) => setPicked((old) => old.length === ids.length && old.every((id, i) => id === ids[i]) ? old : ids) : undefined} onMoveNote={(id, at) => { if (!readOnly) apply(() => setNote(graph, id, at)); }}
        onMove={(id: string, at: Point) => { if (!readOnly) apply(() => moveNode(graph, id, at)); }}
        onConnect={(a, b) => apply(() => connect(graph, registry, a, b))}
        onDropType={(type, at) => apply(() => settleAdded(addNode(graph, registry, type, at).graph, registry))} onDropEmpty={dropEmpty}
        onPlus={(port) => setPalette({ port })}/>
      {checkErrors && <p className={`flow-editor__check${checkErrors.length ? "" : " flow-editor__check--ok"}`} data-testid="flow-check">
        Kontrola grafu{checkErrors.length ? `: ${checkErrors.join(" · ")}` : ": v pořádku"} <small className="flow-editor__check-note">plátno se nespouští, popisuje tok</small></p>}
      {issues.length > 0 && <p className="flow-editor__readiness" data-testid="flow-readiness">Připraveno ke spuštění: {issues.map((issue) => issue.text).join(" · ")}</p>}
      {palette && !readOnly && <NodePalette types={offered} port={palette.port} onPick={pick} onClearPort={() => setPalette({ port: null })} onClose={() => setPalette(null)}/>}
    </div>
    {node && <NodeInspector key={node.id} node={node} spec={specOf(registry, node)} run={run} stall={overlay?.get(node.id)?.stall ?? null} readOnly={readOnly}
      onParam={(key, value) => apply(() => setParam(graph, node.id, key, value))}
      onLayer={frames && specOf(registry, node) ? (layer) => apply(() => setNodeField(graph, node.id, "layer", layer)) : undefined}
      onField={frames ? (key, value) => apply(() => setNodeField(graph, node.id, key, value)) : undefined}
      onRemove={() => { apply(() => removeNode(graph, node.id)); onSelect(null); }} onClose={() => onSelect(null)}/>}
    {!node && frame && <GroupInspector key={frame.id} group={frame} errors={targets.groups.get(frame.id) ?? []} collapsed={collapsed.has(frame.id)} readOnly={readOnly}
      onChange={(patch) => apply(() => setGroup(graph, frame.id, patch))} onToggle={() => toggle(frame.id)}
      onUngroup={() => { apply(() => ungroup(graph, frame.id)); setGroupId(null); }} onClose={() => setGroupId(null)}/>}
  </div>;
}

/** Nová poznámka jde nad levý horní roh grafu, aby nezakryla uzly; posune se tahem. */
function noteSpot(graph: FlowGraph): Point {
  const xs = graph.nodes.map((node) => node.position?.x ?? 0), ys = graph.nodes.map((node) => node.position?.y ?? 0);
  return { x: xs.length ? Math.min(...xs) : 0, y: ys.length ? Math.min(...ys) - 240 : 0 };
}

/** Nový uzel bez portu jde pod nejnižší uzel grafu, aby nepřekryl existující. */
function freeSpot(graph: FlowGraph): Point {
  const bottom = Math.max(0, ...graph.nodes.map((node) => node.position?.y ?? 0));
  return { x: 0, y: graph.nodes.length ? bottom + 180 : 0 };
}
