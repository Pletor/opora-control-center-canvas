// Nabídka vazby z výstupního portu (docs/zive-zobrazeni-a-knihovna.md §4): co nabídnout. Existující karty
// jen kompatibilní podle téhož pravidla jako tah vazby (`connectionProblem`), položky Knihovny jen s
// prvním vstupním portem, který přijme druh toku. Bez Reactu; test vedle v port-menu.test.ts.
import type { CanvasNode, EdgeCarries, Graph } from "@/shared/types/logic/types";
import { foldDiacritics, searchItems, type CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { connectionProblem } from "../../../logic/editor-model";

/** Nabídku má jen karta uzlu nebo sektoru; oblast vede jen `flow` do jiné oblasti a komentář vazby nemá. */
export function hasPortMenu(node: Pick<CanvasNode, "kind">): boolean {
  return node.kind === "node" || node.kind === "sector";
}

/** Karty otevřeného rozsahu, do kterých jde vazba ze zdroje stejně jako tahem; v pořadí mapy. */
export function linkTargets(graph: Graph, scopeId: string, sourceId: string): CanvasNode[] {
  return graph.nodes.filter((node) => node.parentId === scopeId && connectionProblem(graph, sourceId, node.id) === null);
}

/** Hledání podle názvu karty bez ohledu na háčky a velikost písmen; prázdný dotaz nechá všechny. */
export function searchTargets(nodes: CanvasNode[], query: string): CanvasNode[] {
  const needle = foldDiacritics(query.trim());
  return needle ? nodes.filter((node) => foldDiacritics(node.name).includes(needle)) : nodes;
}

/** První vstupní port položky: z něj vložení s vazbou (`catalogEdges`) bere `carries`. */
export function firstInPort(item: CatalogItem) {
  return (item.ports ?? []).find((port) => port.direction === "in") ?? null;
}

/**
 * Položky Knihovny, které jde napojit na výstup: mají vstupní port a jeho `carries` je zvolený druh toku
 * (`null` = neurčeno, pak stačí jakýkoli vstup). Hledání jako v panelu Knihovny (`searchItems`).
 */
export function libraryForCarries(items: CatalogItem[], carries: EdgeCarries | null, query = ""): CatalogItem[] {
  return searchItems(items, query).filter((item) => {
    const port = firstInPort(item);
    return !!port && (carries === null || port.carries === carries);
  });
}

/** Šipka po položkách nabídky: dolů / nahoru s přetočením přes okraj; prázdný seznam nemá aktivní položku. */
export function stepIndex(index: number, delta: number, count: number): number {
  if (count <= 0) return -1;
  if (index < 0) return delta > 0 ? 0 : count - 1;
  return (index + delta + count) % count;
}
