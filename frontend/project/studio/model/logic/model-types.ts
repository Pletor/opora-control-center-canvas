// Typy technického modelu domény (vrstva MODEL, docs/studio.md §4): definice `opora.studio-model/1`, typ komponenty
// z katalogu a jeho porty. Model je vlastní a verzovaný na doménu, oddělený od grafu práce agentů (`/api/graph`).

export const STUDIO_MODEL_SCHEMA = "opora.studio-model/1";

/** 12 datových typů portu (spec prototypu `project-schema.json`, `$defs.port.type`). */
export const PORT_TYPES = [
  "http-request", "cache-command", "record-command", "health", "sql-query", "event",
  "telemetry", "search-query", "data", "job", "sql-result", "sql-replication",
] as const;
export type PortType = typeof PORT_TYPES[number];
export type PortDirection = "input" | "output";
export type PortSide = "left" | "right" | "top" | "bottom";
export type Port = { id: string; type: PortType; direction: PortDirection };

/** Pole inspektoru pozorované u cloudového typu (`sourceConfiguration` v prototypu). */
export type SourceField = { key: string; label: string; min?: number; max?: number; step?: number; options?: readonly string[] };

export type ComponentType = {
  id: string;
  name: string;
  provider?: string;
  cloudProfile?: string;
  group: string;
  category: string;
  icon: string;
  description: string;
  sourceStatus: string;
  ports: readonly Port[];
  sourceDefaults?: Readonly<Record<string, number | string>>;
  sourceConfiguration?: Readonly<Record<string, readonly SourceField[]>>;
};

export type Point = { x: number; y: number };
export type PortRef = { nodeId: string; portId: string };

/** Komponenta modelu. `binding.nodeId` volitelně váže kartu na kartu OPORY (pak MODEL ukáže i její skutečný stav).
 *  `parentId` nese jen řízený Pod uvnitř Kubernetes Deployment (pravidlo hranice rodiče). */
export type StudioModelNode = {
  id: string;
  type: string;
  name: string;
  position: Point;
  config: Record<string, unknown>;
  binding?: { nodeId: string };
  parentId?: string;
};

export type StudioModelEdge = {
  id: string;
  from: PortRef;
  to: PortRef;
  type: PortType;
  enabled: boolean;
  label?: string;
  condition?: string;
};

export type StudioModel = {
  schema: typeof STUDIO_MODEL_SCHEMA;
  domainId: string;
  /** Revize, ze které definice vychází (optimistická revize úložiště); nový model má 0. */
  revision: number;
  nodes: StudioModelNode[];
  edges: StudioModelEdge[];
};

/** Prázdný model domény: nová doména začíná bez komponent (docs/studio.md §4). */
export function emptyStudioModel(domainId: string): StudioModel {
  return { schema: STUDIO_MODEL_SCHEMA, domainId, revision: 0, nodes: [], edges: [] };
}
