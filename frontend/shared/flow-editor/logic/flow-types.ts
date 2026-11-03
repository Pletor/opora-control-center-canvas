// Tvar dat engine toků (`backend/flow/`, kontrakt docs/navrhy/2026-11-03-novy-zaklad.md §3.1) tak, jak ho vrací
// `/api/flow/*`. Editor je generický: o uzlu ví jen to, co řekne registr typů (porty s `kind` a `cardinality`).

export const PORT_KINDS = ["main", "model", "memory", "tool", "subagent", "approval", "data"] as const;
export type PortKind = typeof PORT_KINDS[number];
export type PortDirection = "in" | "out";

export type PortSpec = { name: string; direction: PortDirection; kind: PortKind; cardinality: "one" | "many"; schema?: unknown };
/** `params`: popis parametrů typu (klíč → nápověda), u katalogu záměru stránky; nový uzel je dostane prázdné. */
export type NodeTypeSpec = { type: string; version: number; trigger: boolean; ports: PortSpec[]; params?: Record<string, string> | null };
export type NodeTypes = ReadonlyMap<string, NodeTypeSpec>;

export type Point = { x: number; y: number };
export type FlowNode = {
  id: string; type: string; type_version?: number; params?: Record<string, unknown>; position?: Point; pinned_output?: unknown;
};
export type FlowEdge = {
  id: string; source_node: string; source_port: string; target_node: string; target_port: string; kind: PortKind; label?: string;
};
export type FlowGraph = { nodes: FlowNode[]; edges: FlowEdge[] };

/** Konec vazby: uzel, jméno portu a směr (port `main` bývá vstupní i výstupní zároveň). */
export type PortRef = { nodeId: string; port: string; direction: PortDirection };

export type VersionStatus = "draft" | "candidate" | "active" | "retired";
export type FlowWorkflow = { id: string; kind: string; project_id: string | null; name: string; active_version_id?: string | null; active_n?: number | null;
  /** Vlastník workflow: u záměru stránky `opora:page:<nodeId>`. */
  owner_ref?: string | null };
export type FlowVersion = {
  id: string; workflow_id: string; n: number; graph: FlowGraph; hash: string; parent_version_id: string | null;
  status: VersionStatus; eval_run_id: string | null; created_at: string;
};

export type RunStatus = "queued" | "running" | "waiting" | "succeeded" | "failed" | "cancelled";
export type NodeRunStatus = "queued" | "running" | "waiting" | "succeeded" | "failed";
export type FlowRun = {
  id: string; workflow_version_id: string; trigger: { source?: string; node_id?: string; [key: string]: unknown } | null;
  status: RunStatus; parent_run_id: string | null; cost_usd: number; tokens: number; created_at: string; updated_at: string;
};
export type NodeRun = {
  id: string; run_id: string; node_id: string; attempt: number; status: NodeRunStatus; input_ref?: string | null; output_ref?: string | null;
  output_port?: string | null; error?: string | null; provider?: string | null; model?: string | null; tokens_in?: number | null;
  tokens_out?: number | null; cost_usd?: number | null; started_at?: string | null; ended_at?: string | null;
  last_heartbeat_at?: string | null; waiting_for?: string | null; deadline?: string | null;
};
export type FlowRunDetail = FlowRun & { node_runs: NodeRun[] };
export type LogEvent = { seq: number; run_id: string | null; node_run_id: string | null; ts: string; type: string; payload: unknown; canvas: number };
export type Stall = NodeRun & { workflow_version_id: string; reason: string };

export function nodeTypeMap(types: readonly NodeTypeSpec[]): NodeTypes {
  return new Map(types.map((type) => [type.type, type]));
}
