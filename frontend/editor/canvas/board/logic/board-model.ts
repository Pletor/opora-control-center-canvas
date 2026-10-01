// Čistý model plátna: z tahu myší (React Flow Connection) udělá vazbu grafu. Bez Reactu a bez React Flow,
// aby se dal testovat samostatně; Board i App jen předávají, co uživatel natáhl, a ukládá rodič.
import type { EdgePort, GraphEdge } from "@/shared/types/logic/types";
import { blockHandleId, EDGE_PORTS, isBlockEdge } from "@/shared/types/logic/types";

export function newEdgeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `edge-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Tah začal na úchytu; `null` je plátno bez úchytu (starší chování = port `next`). */
export type BoardConnection = { source: string | null; target: string | null; sourceHandle?: string | null };

/** Úchyt portu bloku má tvar `block:<blockId>:<portId>`; cokoli jiného je port hrany karty. */
export function parseBlockHandle(handle: string | null | undefined): { blockId: string; portId: string } | null {
  if (!handle || !handle.startsWith("block:")) return null;
  const parts = handle.split(":");
  if (parts.length !== 3 || !parts[1] || !parts[2]) return null;
  return { blockId: parts[1], portId: parts[2] };
}

/** Port hrany karty podle úchytu; neznámý úchyt znamená `next`. */
export function portOf(handle: string | null | undefined): EdgePort {
  return EDGE_PORTS.find((p) => p === handle) ?? "next";
}

/**
 * Vazba z dokončeného tahu. Z tlačítka bloku vzniká `port: "block"` s identitou bloku i portu,
 * z hrany karty klasický `next / action / rule`. Tah do sebe samého ani neúplný tah vazbu nedá.
 */
export function edgeFromConnection(connection: BoardConnection, id: string = newEdgeId()): GraphEdge | null {
  const { source, target, sourceHandle } = connection;
  if (!source || !target || source === target) return null;
  const block = parseBlockHandle(sourceHandle);
  if (block) return { id, source, target, port: "block", sourceBlockId: block.blockId, sourcePortId: block.portId };
  return { id, source, target, port: portOf(sourceHandle) };
}

/** Jak vazba na plátně vypadá: z kterého úchytu vychází, jakou třídu nese a jakým tahem se kreslí.
 *  Vede vždy pravoúhle (smoothstep), se zaoblenými rohy a odstupem od karty, ne rovnou čárou napříč plátnem. */
export type EdgeAppearance = {
  sourceHandle: string;
  className: string;
  style?: { stroke: string; strokeDasharray?: string };
  type: "smoothstep";
  pathOptions: { borderRadius: number; offset: number };
};

/** Akce jantarově, pravidla červeně čárkovaně, port bloku akcentem drobnou čárkou; tok mezi oblastmi
 *  barvou oblasti čárkovaně; další krok bez barvy. */
const EDGE_STYLE: Record<string, { stroke: string; strokeDasharray?: string }> = {
  block: { stroke: "var(--accent)", strokeDasharray: "2 3" },
  action: { stroke: "#c98a1e" },
  rule: { stroke: "#c4524a", strokeDasharray: "4 3" },
  flow: { stroke: "var(--area-line)", strokeDasharray: "6 4" },
};

/** Pravoúhlé vedení sdílí všechny vazby grafu: zaoblení 12 a odstup 24 od karty, než se lomí. */
const EDGE_PATH_OPTIONS = { borderRadius: 12, offset: 24 };

export function edgeAppearance(edge: GraphEdge): EdgeAppearance {
  const port = edge.port ?? "next";
  return {
    sourceHandle: isBlockEdge(edge) ? blockHandleId(edge.sourceBlockId, edge.sourcePortId) : port,
    // Tok mezi oblastmi nese vlastní třídu (ne "edge-port-*"), ať jde v CSS i mimo ni stylovat
    // samostatně od vazeb mezi kartami.
    className: port === "flow" ? "edge-flow" : "edge-port-" + port,
    style: EDGE_STYLE[port],
    type: "smoothstep",
    pathOptions: EDGE_PATH_OPTIONS,
  };
}

/** Stejná vazba už na plátně je, když sedí odkud, kam, kterým portem a — u bloku — i z kterého tlačítka. */
export function sameEdge(a: GraphEdge, b: GraphEdge): boolean {
  return (
    a.source === b.source &&
    a.target === b.target &&
    (a.port ?? "next") === (b.port ?? "next") &&
    (a.sourceBlockId ?? "") === (b.sourceBlockId ?? "") &&
    (a.sourcePortId ?? "") === (b.sourcePortId ?? "")
  );
}
