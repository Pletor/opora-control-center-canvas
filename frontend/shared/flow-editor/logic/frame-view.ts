// Poznámky a rámce grafu → uzly React Flow za kartami (n8n sticky note a Canvas Groups). Rámec obepne své uzly podle
// jejich polohy a odhadnuté velikosti karty (krok 76, agent 220 × 80, sub-uzel 64, plus jméno pod kartou). Sbalený
// rámec schová své uzly a stojí místo nich jako jeden uzel; vazby zvenku se přepojí na něj a vnitřní vazby zmizí.
import type { Edge, Node } from "@xyflow/react";
import type { FlowGraph, FlowGroup, FlowNote } from "./flow-types";
import type { FlowCardNode } from "./flow-view";
import { handleId } from "./flow-view";

export type FlowNoteNode = Node<{ note: FlowNote; readOnly: boolean }, "flow-note">;
export type FlowGroupNode = Node<{ group: FlowGroup; errors: string[]; collapsed: boolean; selected: boolean }, "flow-group">;

export const SIZE = { main: [76, 116], trigger: [76, 116], agent: [220, 120], sub: [64, 104] } as const;
const PAD = 36, HEAD = 56;
export const NOTE_PREFIX = "note:", GROUP_PREFIX = "group:";

export function noteNodes(graph: FlowGraph, readOnly: boolean): FlowNoteNode[] {
  return (graph.notes ?? []).map((note) => ({ id: NOTE_PREFIX + note.id, type: "flow-note", position: { x: note.x, y: note.y },
    width: note.width, height: note.height, zIndex: -2, draggable: !readOnly, connectable: false, data: { note, readOnly } }));
}

/** Obdélník kolem karet rámce (bez karet, které na plátně nejsou). */
export function groupBox(group: FlowGroup, cards: readonly FlowCardNode[]): { x: number; y: number; width: number; height: number } | null {
  const members = cards.filter((card) => group.nodeIds.includes(card.id));
  if (!members.length) return null;
  const left = Math.min(...members.map((card) => card.position.x)), top = Math.min(...members.map((card) => card.position.y));
  const right = Math.max(...members.map((card) => card.position.x + SIZE[card.data.role][0]));
  const bottom = Math.max(...members.map((card) => card.position.y + SIZE[card.data.role][1]));
  return { x: left - PAD, y: top - PAD - HEAD, width: right - left + 2 * PAD, height: bottom - top + 2 * PAD + HEAD };
}

/** Uzly rámců: rozbalený je rám za kartami, sbalený jeden uzel na místě levého horního rohu rámu. */
export function groupNodes(graph: FlowGraph, cards: readonly FlowCardNode[], collapsed: ReadonlySet<string>, errors: ReadonlyMap<string, string[]>, selected: string | null): FlowGroupNode[] {
  return (graph.groups ?? []).flatMap((group): FlowGroupNode[] => {
    const box = groupBox(group, cards);
    if (!box) return [];
    const folded = collapsed.has(group.id);
    const data = { group, errors: errors.get(group.id) ?? [], collapsed: folded, selected: selected === group.id };
    return [folded
      ? { id: GROUP_PREFIX + group.id, type: "flow-group", position: { x: box.x + PAD, y: box.y + PAD + HEAD }, draggable: false, connectable: false, data }
      : { id: GROUP_PREFIX + group.id, type: "flow-group", position: { x: box.x, y: box.y }, width: box.width, height: box.height, zIndex: -1,
        draggable: false, connectable: false, data }];
  });
}

/** Uzly sbalených rámců (schovají se z plátna). */
export const hiddenNodes = (graph: FlowGraph, collapsed: ReadonlySet<string>) =>
  new Set((graph.groups ?? []).filter((group) => collapsed.has(group.id)).flatMap((group) => group.nodeIds));

/** Vazby se sbalenými rámci: konec uvnitř rámce se přepojí na uzel rámce (`main`), vazba uvnitř rámce zmizí. */
export function foldEdges(edges: readonly Edge[], graph: FlowGraph, collapsed: ReadonlySet<string>): Edge[] {
  const owner = new Map((graph.groups ?? []).filter((group) => collapsed.has(group.id)).flatMap((group) => group.nodeIds.map((id) => [id, group.id] as const)));
  if (!owner.size) return [...edges];
  return edges.flatMap((edge): Edge[] => {
    const from = owner.get(edge.source), to = owner.get(edge.target);
    if (from && from === to) return [];
    return [{ ...edge, ...(from ? { source: GROUP_PREFIX + from, sourceHandle: handleId("out", "main") } : {}),
      ...(to ? { target: GROUP_PREFIX + to, targetHandle: handleId("in", "main") } : {}) }];
  });
}
