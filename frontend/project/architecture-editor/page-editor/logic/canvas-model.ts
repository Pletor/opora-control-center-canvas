// Čistý model Mapy architektury: barva karty podle vrstvy, počty s českým skloňováním,
// náhled potomků na kartě a vzhled vazby. Bez Reactu; test vedle v canvas-model.test.ts.
import type { CanvasNode, EdgeCarries, Graph, GraphEdge } from "@/shared/types/logic/types";
import { carriesLook } from "@/shared/edge-carries/logic/edge-carries";
import { membersOf } from "@/editor/canvas/area/logic/area-model";

export type Tone = "frontend" | "backend" | "database" | "security" | "infrastructure" | "cache" | "area";

/**
 * Literální barvy tónů pro SVG značky šipek React Flow (atribut `fill` neumí `var()`).
 * Musí souhlasit s tokeny `--ae-tone-*` v styles/architecture-editor.css.
 */
export const TONE_COLORS: Record<Tone, string> = {
  frontend: "#30e9b0", backend: "#c18aff", database: "#ffc548", security: "#ff5d6c",
  infrastructure: "#4ea8ff", cache: "#b48cff", area: "#ffc548",
};

/** Barva podle `card.layer`; sektor bez vrstvy je frontend, uzel bez vrstvy a knihovna infrastruktura. */
export function toneOf(node: Pick<CanvasNode, "kind" | "card">): Tone {
  if (node.kind === "area") return "area";
  const layer = node.card?.layer;
  if (layer === "frontend" || layer === "backend" || layer === "database") return layer;
  if (layer === "library") return "infrastructure";
  return node.kind === "sector" ? "frontend" : "infrastructure";
}

/** „1 uzel“, „3 uzly“, „5 uzlů“ – tvary [jeden, 2–4, ostatní]. */
export function czechCount(count: number, forms: [string, string, string]): string {
  const form = count === 1 ? forms[0] : count >= 2 && count <= 4 ? forms[1] : forms[2];
  return `${count} ${form}`;
}
export const NODE_FORMS: [string, string, string] = ["uzel", "uzly", "uzlů"];
export const SECTOR_FORMS: [string, string, string] = ["sektor", "sektory", "sektorů"];

/** `page` = karta je podstránka otevřeného rozsahu: na plátně stojí jako odkaz na svou stránku (cesta, `null` = bez cesty). */
export type CardSummary = { tone: Tone; countLabel: string; preview: CanvasNode[]; more: number; page: { path: string | null } | null };
const PREVIEW = 3;

/** Co karta sektoru / uzlu ukazuje: štítek „N uzlů“, až tři přímé potomky jako řádky a u stránky její cestu. */
export function cardSummary(node: CanvasNode, graph: Graph): CardSummary {
  const children = graph.nodes.filter((child) => child.parentId === node.id && (child.kind === "node" || child.kind === "sector"));
  const nodes = children.filter((child) => child.kind === "node").length;
  return { tone: toneOf(node), countLabel: czechCount(nodes, NODE_FORMS), preview: children.slice(0, PREVIEW), more: Math.max(0, children.length - PREVIEW),
    page: node.site?.kind === "page" ? { path: node.site.path || null } : null };
}

/** Hlavička oblasti: „N sektorů“ podle geometrického členství (oblast není rodič). */
export function areaSectorLabel(area: CanvasNode, graph: Graph): string {
  return czechCount(membersOf(area, graph.nodes).filter((node) => node.kind === "sector").length, SECTOR_FORMS);
}

/**
 * Literální barvy druhů toku pro SVG značku šipky (atribut `fill` neumí `var()`).
 * Musí souhlasit s tokeny `--edge-carries-*` v design-tokens/styles/theme-tokens.css.
 */
export const CARRIES_COLORS: Record<EdgeCarries, string> = {
  navigation: "#4ab8ff", data: "#58d7c1", command: "#b49cff", event: "#f4b94f",
};

/** `color` je literál pro šipku, `stroke` hodnota tahu (může být token), `className` háček pro CSS. */
export type EdgeLook = {
  color: string; stroke: string; dash: string | undefined; width: number;
  label: string | undefined; className: string; title: string | undefined;
};

/** Šířka čáry vazby na mapě; druh toku `command` k ní přidá půl pixelu. */
const MAP_EDGE_WIDTH = 2;

/** Vazba má barvu zdroje; `flow` mezi oblastmi je přerušovaná, `rule` nese popisek. Vazba `next`
 *  s druhem toku (`carries`) má barvu druhu, čáru podle něj a druh v tooltipu, ne na čáře. */
export function edgeLook(edge: GraphEdge, graph: Graph): EdgeLook {
  const carries = (edge.port ?? "next") === "next" && edge.carries ? carriesLook(edge.carries) : null;
  if (carries && edge.carries) return {
    color: CARRIES_COLORS[edge.carries], stroke: carries.stroke, dash: carries.dash, width: MAP_EDGE_WIDTH + carries.extraWidth,
    label: undefined, className: `page-editor__edge ${carries.className}`, title: carries.title,
  };
  const source = graph.nodes.find((node) => node.id === edge.source);
  const color = TONE_COLORS[source ? toneOf(source) : "infrastructure"];
  return {
    color, stroke: color, dash: edge.port === "flow" ? "7 6" : undefined, width: MAP_EDGE_WIDTH,
    label: edge.port === "rule" ? "pravidlo" : undefined, className: "page-editor__edge", title: undefined,
  };
}

/** Ancestry od stránky (bez domény) po otevřený rozsah – drobečky nad mapou. */
export function scopePath(graph: Graph, scopeId: string, domainId: string): CanvasNode[] {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const path: CanvasNode[] = [];
  const seen = new Set<string>();
  for (let cursor: string | null = scopeId; cursor && cursor !== domainId && !seen.has(cursor); ) {
    seen.add(cursor);
    const node = byId.get(cursor);
    if (!node) break;
    path.unshift(node);
    cursor = node.parentId;
  }
  return path;
}

/** Šířka karty na mapě a výška, dokud ji React Flow nezměří. */
export const CARD_WIDTH = 270;
const CARD_HEIGHT_GUESS = 90;

/**
 * Obdélníky karet otevřeného rozsahu (bez oblastí) na uložených místech, se skutečně změřeným rozměrem
 * z React Flow (`measured`); nezměřená karta dostane šířku 270 a odhad výšky. Pro usazení a růst oblasti.
 */
export function cardBodies(graph: Graph, scopeId: string, measured: ReadonlyMap<string, { width?: number; height?: number } | undefined>):
  { id: string; x: number; y: number; w: number; h: number }[] {
  return graph.nodes.filter((node) => node.parentId === scopeId && node.kind !== "area").map((node) => {
    const size = measured.get(node.id);
    return { id: node.id, x: node.x, y: node.y, w: size?.width || CARD_WIDTH, h: size?.height || CARD_HEIGHT_GUESS };
  });
}
