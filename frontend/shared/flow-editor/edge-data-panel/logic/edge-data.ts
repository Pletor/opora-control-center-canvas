// Co po hraně letí (kontrakt plátna procesů §2): druhy dat s popiskem a zkratkou, popisek hrany `via · kind`, zděděný
// příklad ze zdrojového uzlu a kontrola, že cíl daný druh přijímá. Barvu a styl čáry dodává `edge-data-panel.css`.
import { DATA_KINDS, specOf, type DataKind, type EdgeData, type FlowEdge, type FlowGraph, type NodeTypes } from "../../logic/flow-types";

export const KIND_LABEL: Record<DataKind, string> = { text: "text", number: "číslo", json: "JSON", table: "tabulka", document: "dokument", vector: "vektor", file: "soubor", event: "událost" };
export const KIND_GLYPH: Record<DataKind, string> = { text: "Aa", number: "#", json: "{}", table: "▦", document: "▤", vector: "⇗", file: "▭", event: "⚡" };

/** Platná data hrany; cokoli jiného (starý graf, ruční zásah) se bere jako „bez dat“. */
export function edgeData(edge: Pick<FlowEdge, "data">): EdgeData | undefined {
  const data = edge.data as Partial<EdgeData> | undefined;
  return data && (DATA_KINDS as readonly unknown[]).includes(data.kind) ? data as EdgeData : undefined;
}

/** Popisek hrany: `via · kind`, když je obojí; jinak to, co je. */
export const dataLabel = (edge: Pick<FlowEdge, "via" | "data">) => [edge.via, edgeData(edge)?.kind].filter(Boolean).join(" · ");

/** Ukázková hodnota ze schématu: `example`, `default`, první z `enum`, nebo se složí z `properties` / `items`. */
export function sampleFromSchema(schema: unknown): unknown {
  if (!schema || typeof schema !== "object") return undefined;
  const s = schema as Record<string, unknown>;
  if ("example" in s) return s.example;
  if ("default" in s) return s.default;
  if (Array.isArray(s.enum) && s.enum.length) return s.enum[0];
  if (s.properties && typeof s.properties === "object")
    return Object.fromEntries(Object.entries(s.properties).map(([key, value]) => [key, sampleFromSchema(value) ?? null]));
  if (s.type === "array") { const item = sampleFromSchema(s.items); return item === undefined ? [] : [item]; }
  return { string: "", number: 0, integer: 0, boolean: false }[s.type as string];
}

/** Příklad, který hrana nemá vlastní: `example` zdrojového uzlu, jinak ukázka z jeho `outputSchema`. */
export function inheritedExample(graph: FlowGraph, edge: Pick<FlowEdge, "source_node">): { value: unknown; from: string } | null {
  const node = graph.nodes.find((item) => item.id === edge.source_node);
  if (!node) return null;
  const value = node.example !== undefined ? node.example : sampleFromSchema(node.outputSchema);
  return value === undefined ? null : { value, from: node.id };
}

/** Proč cíl druh nepřijímá; null = přijímá (prázdný `accepts` = cokoli). */
export function kindError(kind: DataKind | undefined, accepts: readonly DataKind[] | undefined, target: string): string | null {
  if (!kind || !accepts?.length || accepts.includes(kind)) return null;
  return `Uzel ${target} nepřijímá data druhu ${KIND_LABEL[kind]} (přijímá: ${accepts.map((item) => KIND_LABEL[item]).join(", ")}).`;
}

/** Kontrola druhu dat na hraně proti cíli: pro nastavení v panelu i pro tažení (druh z `emits` zdroje). */
export function edgeKindError(graph: FlowGraph, types: NodeTypes, edge: Pick<FlowEdge, "source_node" | "target_node" | "data">, kind = edgeData(edge)?.kind): string | null {
  const source = graph.nodes.find((node) => node.id === edge.source_node), target = graph.nodes.find((node) => node.id === edge.target_node);
  return kindError(kind ?? (source && specOf(types, source)?.emits) ?? undefined, target && specOf(types, target)?.accepts, edge.target_node);
}
