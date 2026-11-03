import { useMemo, useState } from "react";
import { connectionError } from "../logic/connection-policy";
import { nodeTypeMap, type FlowGraph, type NodeRun, type NodeTypeSpec, type Point, type PortRef } from "../logic/flow-types";
import { flowEdges, flowNodes } from "../logic/flow-view";
import type { GraphDiff } from "../logic/graph-diff";
import { addConnected, addNode, connect, moveNode, removeEdge, removeNode, setParam } from "../logic/graph-edit";
import { readinessIssues } from "../logic/readiness";
import type { RunOverlay } from "../logic/run-overlay";
import type { PlusRequest } from "../flow-node/logic/port-actions";
import NodePalette from "../node-palette/components/NodePalette";
import NodeInspector from "../node-inspector/components/NodeInspector";
import FlowCanvas from "./FlowCanvas";
import "../styles/flow-editor.css";

type Props = {
  graph: FlowGraph; types: readonly NodeTypeSpec[]; readOnly: boolean;
  overlay?: RunOverlay; diff?: GraphDiff | null; nodeRuns?: readonly NodeRun[];
  selected: string | null; onSelect: (nodeId: string | null) => void;
  /** Každá úprava vrací celý nový graf; uloží ho (jako draft verze) rodič. */
  onChange: (graph: FlowGraph) => void;
};

/** Generický editor grafu verze workflow: plátno, paleta, inspektor a pás „Připraveno ke spuštění“. Neví nic
 * o srdci ani o API; typy uzlů dostává z registru, stav běhu a rozdíl verzí hotové v props a změny hlásí nahoru. */
export default function FlowEditor({ graph, types, readOnly, overlay, diff, nodeRuns = [], selected, onSelect, onChange }: Props) {
  const registry = useMemo(() => nodeTypeMap(types), [types]);
  const [palette, setPalette] = useState<{ port: PlusRequest | null } | null>(null);
  const [edge, setEdge] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const issues = useMemo(() => readinessIssues(graph, registry), [graph, registry]);
  const issueNodes = useMemo(() => new Set(issues.flatMap((issue) => issue.nodeId ? [issue.nodeId] : [])), [issues]);
  const nodes = useMemo(() => flowNodes(graph, registry, { overlay, diff, highlighted: selected, issues: issueNodes, readOnly }), [graph, registry, overlay, diff, selected, issueNodes, readOnly]);
  const edges = useMemo(() => flowEdges(graph, { overlay, diff, readOnly }), [graph, overlay, diff, readOnly]);

  const apply = (edit: () => FlowGraph) => {
    try { onChange(edit()); setMessage(""); } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  };
  const pick = (type: string) => {
    const port = palette?.port;
    apply(() => port ? addConnected(graph, registry, type, port) : addNode(graph, registry, type, freeSpot(graph)).graph);
    setPalette(null);
  };
  const node = graph.nodes.find((item) => item.id === selected) ?? null;
  const run = node ? [...nodeRuns].reverse().find((item) => item.node_id === node.id) ?? null : null;
  const selectedEdge = graph.edges.find((item) => item.id === edge);

  return <div className="flow-editor" data-testid="flow-editor">
    <div className="flow-editor__main">
      {!readOnly && <div className="flow-editor__tools">
        <button type="button" className="flow-editor__tool" onClick={() => setPalette({ port: null })}>+ Uzel</button>
        {selectedEdge && <span className="flow-editor__edge">vazba {selectedEdge.source_node}.{selectedEdge.source_port} → {selectedEdge.target_node}.{selectedEdge.target_port}
          <button type="button" className="flow-editor__tool" onClick={() => { apply(() => removeEdge(graph, selectedEdge.id)); setEdge(null); }}>Odebrat vazbu</button></span>}
        {message && <span className="flow-editor__message" role="alert">{message}</span>}
      </div>}
      <FlowCanvas nodes={nodes} edges={edges} readOnly={readOnly}
        canConnect={(a: PortRef, b: PortRef) => !connectionError(graph, registry, a, b)}
        onSelectNode={onSelect} onSelectEdge={setEdge}
        onMove={(id: string, at: Point) => { if (!readOnly) apply(() => moveNode(graph, id, at)); }}
        onConnect={(a, b) => apply(() => connect(graph, registry, a, b))}
        onDropType={(type, at) => apply(() => addNode(graph, registry, type, at).graph)}
        onPlus={(port) => setPalette({ port })}/>
      {issues.length > 0 && <p className="flow-editor__readiness" data-testid="flow-readiness">Připraveno ke spuštění: {issues.map((issue) => issue.text).join(" · ")}</p>}
      {palette && !readOnly && <NodePalette types={types} port={palette.port} onPick={pick} onClearPort={() => setPalette({ port: null })} onClose={() => setPalette(null)}/>}
    </div>
    {node && <NodeInspector key={node.id} node={node} spec={registry.get(node.type)} run={run} stall={overlay?.get(node.id)?.stall ?? null} readOnly={readOnly}
      onParam={(key, value) => apply(() => setParam(graph, node.id, key, value))}
      onRemove={() => { apply(() => removeNode(graph, node.id)); onSelect(null); }} onClose={() => onSelect(null)}/>}
  </div>;
}

/** Nový uzel bez portu jde pod nejnižší uzel grafu, aby nepřekryl existující. */
function freeSpot(graph: FlowGraph): Point {
  const bottom = Math.max(0, ...graph.nodes.map((node) => node.position?.y ?? 0));
  return { x: 0, y: graph.nodes.length ? bottom + 180 : 0 };
}
