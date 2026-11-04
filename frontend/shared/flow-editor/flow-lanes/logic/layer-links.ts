// „Co dál?“ u portu: které vrstvy smějí navázat na vrstvu uzlu, ze kterého se táhlo. Zrcadlí server
// (`backend/flow/layer_check.py`): frontend nesahá do databáze přímo, dvojice s vlastním seznamem `via` ho dostane
// předvyplněný, ai / neutral / stejná vrstva smí kamkoli. Server rozhoduje; tady jen nenabídneme, co by neprošlo.
import { specOf, type EdgeVia, type FlowGraph, type Layer, type NodeTypes, type NodeTypeSpec, type PortDirection } from "../../logic/flow-types";
import { SIZE } from "../../logic/frame-view";
import { nodeRole } from "../../logic/node-role";
import { effectiveLayer, LAYER_ORDER } from "./layers";

const VIA: Partial<Record<`${Layer}>${Layer}`, readonly EdgeVia[]>> = { "fe>be": ["http", "event"], "be>fe": ["http", "event", "render"], "be>db": ["sql", "call"],
  "db>be": ["sql", "call"], "be>infra": ["http", "call", "event"], "infra>be": ["http", "call", "event"], "fe>infra": ["http"] };
const free = (a: Layer, b: Layer) => a === b || a === "ai" || b === "ai" || a === "neutral" || b === "neutral";

/** Smí hrana vést z vrstvy `from` do vrstvy `to`? */
export const layersLinkable = (from: Layer, to: Layer) => free(from, to) || `${from}>${to}` in VIA;
/** `via` předvyplněné na hranu mezi vrstvami s vlastním seznamem (první povolené); jinde bez `via`. */
export const defaultVia = (from: Layer, to: Layer): EdgeVia | undefined => free(from, to) ? undefined : VIA[`${from}>${to}`]?.[0];

/** Typy, na které smí navázat uzel vrstvy `anchor` u portu se směrem `direction` (výstup → nový uzel za ním, vstup → před
 * ním). Typ bez vrstvy (krok na míru) smí vždy, dostane vrstvu uzlu, ze kterého se táhlo. */
export function linkableTypes(types: readonly NodeTypeSpec[], anchor: Layer | undefined, direction: PortDirection): NodeTypeSpec[] {
  if (!anchor) return [...types];
  return types.filter((spec) => !spec.layer || (direction === "out" ? layersLinkable(anchor, spec.layer) : layersLinkable(spec.layer, anchor)));
}

/** Právě přidaný uzel (poslední v grafu) a jeho hrana (poslední): chybějící vrstva se doplní z uzlu, ze kterého se táhlo,
 * hrana mezi vrstvami dostane `via` a uzel jde do pruhu své vrstvy (pod nejnižší dřívější vrstvu, jinak k uzlům vrstvy).
 * Bez `anchorId` (uzel přidaný bez portu) se jen doplní vrstva. */
export function settleAdded(graph: FlowGraph, types: NodeTypes, anchorId?: string): FlowGraph {
  const added = graph.nodes.at(-1);
  if (!added) return graph;
  const anchor = graph.nodes.find((node) => node.id === anchorId);
  const layer = effectiveLayer(added, specOf(types, added)) ?? (anchor && effectiveLayer(anchor, specOf(types, anchor))) ?? "neutral";
  const others = graph.nodes.slice(0, -1).flatMap((node) => {
    const spec = specOf(types, node), own = effectiveLayer(node, spec);
    return own ? [{ layer: own, y: node.position?.y ?? 0, bottom: (node.position?.y ?? 0) + SIZE[nodeRole(spec)][1] }] : [];
  });
  const mates = others.filter((item) => item.layer === layer), before = others.filter((item) => LAYER_ORDER.indexOf(item.layer) < LAYER_ORDER.indexOf(layer));
  const y = !anchor ? undefined : mates.length ? Math.min(...mates.map((item) => item.y)) : before.length ? Math.max(...before.map((item) => item.bottom)) + 70 : undefined;
  const nodes = graph.nodes.map((node) => node === added ? { ...node, ...(effectiveLayer(node, specOf(types, node)) ? {} : { layer }), ...(y !== undefined ? { position: { x: node.position?.x ?? 0, y: Math.round(y) } } : {}) } : node);
  const edge = graph.edges.at(-1);
  const other = edge && (edge.source_node === added.id ? graph.nodes.find((node) => node.id === edge.target_node) : edge.target_node === added.id ? graph.nodes.find((node) => node.id === edge.source_node) : undefined);
  const otherLayer = other && effectiveLayer(other, specOf(types, other));
  const via = edge && otherLayer && !edge.via ? (edge.source_node === added.id ? defaultVia(layer, otherLayer) : defaultVia(otherLayer, layer)) : undefined;
  return { ...graph, nodes, edges: graph.edges.map((item) => item === edge && via ? { ...item, via } : item) };
}
