// Seznam vrstev pro záložku STRÁNKA: z plochého grafu (`graph.nodes`) udělá tři skupiny — sektory
// i s tím, co v nich leží, uzly, které v žádném sektoru nejsou, a oblasti podle vrstvy, na které
// stojí. Modul je bez Reactu a bez API: dostane uzly, filtr, hledaný text a množinu uzavřených
// karet, vrátí hotové řádky. O plátně, projektu ani o tom, co se stane po kliknutí, neví nic.
import { areaLabel } from "@/editor/canvas/area/logic/area-model";
import { foldDiacritics } from "@/editor/component-library/library-catalog/logic/library-catalog";
import type { CanvasNode } from "@/shared/types/logic/types";

/** Filtr nad seznamem: buď všechny skupiny, nebo jen jedna. Hodnota se ukládá se stavem panelu. */
export type LayerFilter = "all" | "sector" | "node" | "area";
/** Skupina seznamu; zároveň klíč, pod kterým si panel pamatuje, že je sbalená. */
export type LayerGroupId = "sectors" | "nodes" | "areas";

export const LAYER_FILTERS: { id: LayerFilter; label: string }[] = [
  { id: "all", label: "Vše" },
  { id: "sector", label: "Sektory" },
  { id: "node", label: "Uzly" },
  { id: "area", label: "Oblasti" },
];

/** Pořadí skupin v panelu a věta, kterou skupina řekne, když je prázdná. */
export const LAYER_GROUPS: { id: LayerGroupId; label: string; filter: LayerFilter; empty: string }[] = [
  { id: "sectors", label: "Sektory", filter: "sector", empty: "Zatím tu není žádný sektor." },
  { id: "nodes", label: "Uzly mimo sektor", filter: "node", empty: "Každý uzel leží v nějaké vrstvě." },
  { id: "areas", label: "Oblasti", filter: "area", empty: "Plátno zatím nemá žádnou oblast." },
];

/** Uzel bez jména se v seznamu nesmí ztratit; dostane popisek místo prázdna. */
export const UNNAMED_LAYER_LABEL = "Bez názvu";

export type LayerRow = {
  id: string;
  name: string;
  kind: CanvasNode["kind"];
  /** O kolik stupňů je řádek zanořený proti kořeni své skupiny; kreslí odsazení a vodicí linku. */
  depth: number;
  /** Leží přímo v projektu (`parentId === null`) — v panelu to říká domeček. */
  isRoot: boolean;
  /** Karta je uzavřená (`done.confirmed`); v panelu to říká oko se slovem „skryto“. */
  hidden: boolean;
};

export type LayerGroup = { id: LayerGroupId; label: string; rows: LayerRow[] };

/** Komentář ani oblast nejsou vrstva, do které se dá vejít; strom staví jen sektory a uzly. */
const isLayerKind = (node: CanvasNode): boolean => node.kind === "sector" || node.kind === "node";

const labelOf = (node: CanvasNode): string =>
  node.kind === "area" ? areaLabel(node) : node.name.trim() || UNNAMED_LAYER_LABEL;

/** Sourozenci se řadí podle jména, takže seznam vypadá stejně po každém posunu karty na plátně. */
const byLabel = (a: CanvasNode, b: CanvasNode): number =>
  labelOf(a).localeCompare(labelOf(b), "cs") || a.id.localeCompare(b.id);

type Branch = { node: CanvasNode; children: Branch[] };

/**
 * Kořen seznamu: uzel v projektu (`parentId === null`) — a taky sirotek, jehož vrstva už v grafu
 * není. Sirotka je lepší ukázat nahoře než ho zamlčet; kdo ho vidí, může ho na plátně srovnat.
 */
const isRootIn = (node: CanvasNode, byId: Map<string, CanvasNode>): boolean =>
  node.parentId === null || !byId.has(node.parentId);

/**
 * Větve jedné vrstvy: děti daného rodiče a rekurzivně jejich děti. `seen` hlídá kruh v datech
 * (uzel, který je svým vlastním předkem) — takový strom se usekne, panel se kvůli němu nezacyklí.
 */
function branchesOf(nodes: CanvasNode[], parentId: string | null, seen: Set<string>, byId: Map<string, CanvasNode>): Branch[] {
  const belongs = (node: CanvasNode) => (parentId === null ? isRootIn(node, byId) : node.parentId === parentId);
  return nodes
    .filter((node) => belongs(node) && isLayerKind(node) && !seen.has(node.id))
    .sort(byLabel)
    .map((node) => {
      const nested = new Set(seen).add(node.id);
      return { node, children: branchesOf(nodes, node.id, nested, byId) };
    });
}

/**
 * Hledání nad stromem: co sedí na dotaz, zůstane i s celým svým obsahem (chci vidět, co v tom
 * sektoru je); co nesedí, přežije jen kvůli potomkovi, který sedí — jinak by se nález nedal
 * ukázat na správném místě stromu.
 */
function pruneBranch(branch: Branch, needle: string): Branch | null {
  if (foldDiacritics(labelOf(branch.node)).includes(needle)) return branch;
  const children = branch.children.map((child) => pruneBranch(child, needle)).filter((child): child is Branch => child !== null);
  return children.length ? { ...branch, children } : null;
}

const rowOf = (node: CanvasNode, depth: number, closed: ReadonlySet<string>): LayerRow => ({
  id: node.id,
  name: labelOf(node),
  kind: node.kind,
  depth,
  isRoot: node.parentId === null,
  hidden: closed.has(node.id),
});

function flatten(branches: Branch[], depth: number, closed: ReadonlySet<string>): LayerRow[] {
  return branches.flatMap((branch) => [rowOf(branch.node, depth, closed), ...flatten(branch.children, depth + 1, closed)]);
}

/** Kolik vrstev je nad uzlem; u oblasti to je odsazení, které ji přiřadí k její vrstvě. */
function layerDepth(node: CanvasNode, byId: Map<string, CanvasNode>): number {
  let depth = 0;
  let current = node.parentId ? byId.get(node.parentId) : undefined;
  const seen = new Set<string>([node.id]);
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    depth += 1;
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }
  return depth;
}

/** Cesta vrstvami od projektu k uzlu; drží oblasti téže vrstvy pohromadě a v pořadí vrstev. */
function layerPath(node: CanvasNode, byId: Map<string, CanvasNode>): string {
  const names: string[] = [];
  let current = node.parentId ? byId.get(node.parentId) : undefined;
  const seen = new Set<string>([node.id]);
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    names.unshift(labelOf(current));
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }
  return names.join(" / ");
}

/** Sektory a jejich obsah: kořen je sektor v projektu, pod ním rekurzivně jeho uzly i podsektory. */
function sectorRows(roots: Branch[], needle: string, closed: ReadonlySet<string>): LayerRow[] {
  return flatten(prune(roots.filter((branch) => branch.node.kind === "sector"), needle), 0, closed);
}

/** Uzly, které nesedí v žádném sektoru — leží rovnou v projektu; i ony si nesou svůj obsah. */
function looseNodeRows(roots: Branch[], needle: string, closed: ReadonlySet<string>): LayerRow[] {
  return flatten(prune(roots.filter((branch) => branch.node.kind === "node"), needle), 0, closed);
}

function prune(branches: Branch[], needle: string): Branch[] {
  if (!needle) return branches;
  return branches.map((branch) => pruneBranch(branch, needle)).filter((branch): branch is Branch => branch !== null);
}

/** Oblasti po vrstvách: odsazení říká, jak hluboko jejich vrstva leží, pořadí drží vrstvy pohromadě. */
function areaRows(nodes: CanvasNode[], byId: Map<string, CanvasNode>, needle: string, closed: ReadonlySet<string>): LayerRow[] {
  return nodes
    .filter((node) => node.kind === "area")
    .filter((node) => !needle || foldDiacritics(labelOf(node)).includes(needle))
    .sort((a, b) => layerPath(a, byId).localeCompare(layerPath(b, byId), "cs") || byLabel(a, b))
    .map((node) => rowOf(node, layerDepth(node, byId), closed));
}

/**
 * Seznam vrstev pro panel: vrátí skupiny, které filtr propouští (`all` všechny tři), každou už
 * s hotovými řádky. Prázdná skupina se nezahazuje — panel o ní řekne vlastní větou, aby bylo
 * poznat rozdíl mezi „nic tu není“ a „filtr to schoval“.
 */
export function buildLayerTree(
  nodes: CanvasNode[],
  filter: LayerFilter = "all",
  query = "",
  closed: ReadonlySet<string> = new Set<string>(),
): LayerGroup[] {
  const needle = foldDiacritics(query.trim());
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const roots = branchesOf(nodes, null, new Set(), byId);
  return LAYER_GROUPS.filter((group) => filter === "all" || filter === group.filter).map((group) => ({
    id: group.id,
    label: group.label,
    rows:
      group.id === "sectors"
        ? sectorRows(roots, needle, closed)
        : group.id === "nodes"
          ? looseNodeRows(roots, needle, closed)
          : areaRows(nodes, byId, needle, closed),
  }));
}

/** Kolik vrstev seznam právě ukazuje; číslo vedle hledání je důkaz, že filtr i dotaz zabraly. */
export const countLayers = (groups: LayerGroup[]): number => groups.reduce((sum, group) => sum + group.rows.length, 0);
