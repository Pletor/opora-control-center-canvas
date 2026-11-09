// Rozvržení módu Storyboard bez Reactu: které karty nabídnout, které vrstvy ukázat a které z nich jsou vidět.
// Viditelnost vrstev je jen pohled editoru (nikam se neukládá); vrstva anotací je vždy poslední.
import type { AnimationDef } from "./animations";

export const ANNOTATION_LAYER = "anotace";
/** Skica momentu (PNG z Excalidraw) leží přes animaci a pod šipkami. */
export const SKETCH_LAYER = "skica";
export type LayerInfo = { id: string; label: string };
export type PickerCard = { id: string; name: string };

/** Karty prostoru (`kind: "node"`) abecedně podle názvu; sektory, komentáře a oblasti storyboard nemají. */
export function cardsForPicker(graph: { nodes: { id: string; kind: string; name: string }[] }): PickerCard[] {
  return graph.nodes
    .filter((node) => node.kind === "node")
    .map(({ id, name }) => ({ id, name: name || id }))
    .sort((a, b) => a.name.localeCompare(b.name, "cs"));
}

/** Vrstvy animace odspodu nahoru, pak „Skica“ a na konci „Šipky a poznámky“. */
export function layersOf(animation: Pick<AnimationDef, "layers">): LayerInfo[] {
  return [...animation.layers.map(({ id, label }) => ({ id, label })), { id: SKETCH_LAYER, label: "Skica" }, { id: ANNOTATION_LAYER, label: "Šipky a poznámky" }];
}

/** Na začátku je vidět všechno. */
export function defaultVisible(animation: Pick<AnimationDef, "layers">): Set<string> {
  return new Set(layersOf(animation).map((layer) => layer.id));
}

/** Nová množina bez/s danou vrstvou; původní se nemění. */
export function toggleLayer(visible: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(visible);
  if (!next.delete(id)) next.add(id);
  return next;
}

/** Zapnuté vrstvy bez vrstvy anotací (skicu kreslí plátno samo, `paint` zná jen vrstvy animace a cizí id ignoruje). */
export function paintLayers(visible: ReadonlySet<string>): Set<string> {
  const next = new Set(visible);
  next.delete(ANNOTATION_LAYER);
  return next;
}

/** A tab follows the entered problem, never the transient selection on its parent canvas. */
export function storyboardScope<T extends { id: string; kind: string }>(nodes: T[], scopeNodeId: string | null): T | null {
  return nodes.find(node => node.id === scopeNodeId && (node.kind === "node" || node.kind === "sector")) ?? null;
}
