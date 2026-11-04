// Pruhy podle vrstev: zobrazení (obdélník za uzly vrstvy) a akce „Rozložit do pruhů“. Pruh je jen pohled, v grafu
// zůstává `layer` uzlu; vrstva bez uzlů pruh nemá. Rozložení mění jen `y` (pořadí zleva doprava zůstává) a hlásí ho
// rodiči jako nový graf.
import type { Node } from "@xyflow/react";
import { specOf, type FlowGraph, type Layer, type NodeTypes } from "../../logic/flow-types";
import type { FlowCardNode } from "../../logic/flow-view";
import { nodeRole } from "../../logic/node-role";
import { SIZE } from "../../logic/frame-view";
import { effectiveLayer, LAYER_ORDER } from "./layers";

export type FlowLaneNode = Node<{ layer: Layer }, "flow-lane">;
export const LANE_PREFIX = "lane:";
const PAD_Y = 30, PAD_X = 70, GAP = 70;

/** Pruh pro každou vrstvu s uzly: celá šířka grafu, výška od nejvyššího po nejnižší uzel vrstvy. */
export function laneNodes(cards: readonly FlowCardNode[]): FlowLaneNode[] {
  const live = cards.filter((card) => !card.data.ghost && card.data.layer);
  if (!live.length) return [];
  const left = Math.min(...live.map((card) => card.position.x)) - PAD_X;
  const right = Math.max(...live.map((card) => card.position.x + SIZE[card.data.role][0])) + PAD_X;
  return LAYER_ORDER.flatMap((layer): FlowLaneNode[] => {
    const members = live.filter((card) => card.data.layer === layer);
    if (!members.length) return [];
    const top = Math.min(...members.map((card) => card.position.y)) - PAD_Y;
    const bottom = Math.max(...members.map((card) => card.position.y + SIZE[card.data.role][1])) + PAD_Y;
    return [{ id: LANE_PREFIX + layer, type: "flow-lane", position: { x: left, y: top }, width: right - left, height: bottom - top, zIndex: -3,
      draggable: false, selectable: false, connectable: false, focusable: false, style: { pointerEvents: "none" }, data: { layer } }];
  });
}

/** Uzly bez vrstvy zůstanou, kde jsou. Vrstvy jdou shora dolů v pořadí FE, BE, DB, Infra, AI, ostatní; uvnitř pruhu se
 * zachová svislé rozestoupení uzlů (agent se sub-uzly pod sebou), mění se jen posun pruhu. */
export function arrangeLanes(graph: FlowGraph, types: NodeTypes): FlowGraph {
  const info = graph.nodes.map((node) => {
    const spec = specOf(types, node), y = node.position?.y ?? 0;
    return { node, layer: effectiveLayer(node, spec), y, height: SIZE[nodeRole(spec)][1] };
  });
  const shift = new Map<string, number>();
  let cursor = Math.min(...info.filter((item) => item.layer).map((item) => item.y));
  for (const layer of LAYER_ORDER) {
    const members = info.filter((item) => item.layer === layer);
    if (!members.length) continue;
    const top = Math.min(...members.map((item) => item.y)), bottom = Math.max(...members.map((item) => item.y + item.height));
    for (const item of members) shift.set(item.node.id, cursor - top);
    cursor += bottom - top + GAP;
  }
  return { ...graph, nodes: graph.nodes.map((node) => shift.has(node.id)
    ? { ...node, position: { x: node.position?.x ?? 0, y: Math.round((node.position?.y ?? 0) + shift.get(node.id)!) } } : node) };
}
