import { useState } from "react";
import { editableEdges, editableNodes, nodeEdit, type EditDraft, type EdgeEdit, type NodeEdit } from "./graph-edits";
import type { GraphContext } from "./graph-proposals";

/** Draft values belong to one observed context; refresh requires a fresh explicit selection. */
export function useGraphEdits(key: string, context: GraphContext | null) {
  const [stored, setStored] = useState<{ key: string; value: EditDraft }>({ key, value: { nodes: [], edges: [] } });
  const draft = stored.key === key ? stored.value : { nodes: [], edges: [] };
  const set = (value: EditDraft) => setStored({ key, value });
  const nodes = context ? editableNodes(context) : [];
  const edges = context ? editableEdges(context).filter(edge => !edge.port || edge.port === "next") : [];
  return { draft, nodes, edges,
    adoptArchitecture: (checked: boolean) => set({ ...draft, adoptArchitectureContext: checked }),
    addNode: (id: string) => { const node = nodes.find(item => item.id === id); if (node && !draft.nodes.some(item => item.id === id)) set({ ...draft, nodes: [...draft.nodes, nodeEdit(node)] }); },
    addEdge: (id: string) => { const edge = edges.find(item => item.id === id); if (edge && !draft.edges.some(item => item.id === id)) set({ ...draft, edges: [...draft.edges, { id, remove: false, source: edge.source, target: edge.target }] }); },
    editNode: (id: string, patch: Partial<NodeEdit>) => set({ ...draft, nodes: draft.nodes.map(node => node.id === id ? { ...node, ...patch } : node) }),
    editEdge: (id: string, patch: Partial<EdgeEdit>) => set({ ...draft, edges: draft.edges.map(edge => edge.id === id ? { ...edge, ...patch } : edge) }),
    dropNode: (id: string) => set({ ...draft, nodes: draft.nodes.filter(node => node.id !== id) }),
    dropEdge: (id: string) => set({ ...draft, edges: draft.edges.filter(edge => edge.id !== id) }),
    reset: () => set({ nodes: [], edges: [] }) };
}
export type GraphEditView = ReturnType<typeof useGraphEdits>;
