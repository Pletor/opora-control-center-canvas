// Tvar dat engine toků (`backend/flow/`, kontrakt docs/navrhy/2026-11-03-novy-zaklad.md §3.1) tak, jak ho vrací
// `/api/flow/*`. Editor je generický: o uzlu ví jen to, co řekne registr typů (porty s `kind` a `cardinality`).

// outputParser … reranker: sub-porty katalogu toků dat knihovny (`backend/flow/catalogs/data_flow.py`, podle n8n).
export const PORT_KINDS = ["main", "model", "memory", "tool", "subagent", "approval", "data", "outputParser", "embedding",
  "document", "textSplitter", "retriever", "vectorStore", "reranker"] as const;
export type PortKind = typeof PORT_KINDS[number];
export type PortDirection = "in" | "out";

/** `required` a `label` posílá registr (povinný port má v editoru `*`); bez nich je povinný jen sub-port `model`. */
export type PortSpec = { name: string; direction: PortDirection; kind: PortKind; cardinality: "one" | "many"; schema?: unknown; required?: boolean; label?: string };
/** Porty typu pro jinou sadu `params` (režim vektorového úložiště ap.): paleta podle portu podle nich nabídne i typ,
 * jehož výchozí porty nesedí, a nový uzel dostane tyto `params`. */
export type PortVariant = { params: Record<string, unknown>; ports: PortSpec[] };
/** `params`: popis parametrů typu (klíč → nápověda), u katalogu záměru stránky; nový uzel je dostane prázdné.
 * `category`: kategorie palety (katalog toků dat); `dynamicPorts`: porty závisí na `params` (`POST /api/flow/node-ports`). */
export type NodeTypeSpec = { type: string; version: number; trigger: boolean; ports: PortSpec[]; params?: Record<string, string> | null;
  category?: string; dynamicPorts?: boolean; variants?: PortVariant[] };
export type NodeTypes = ReadonlyMap<string, NodeTypeSpec>;

export type Point = { x: number; y: number };
/** Pole uzlu plátna toku (kontrakt knihovny §1): poznámka (`notesInFlow` = podtitulek na kartě), schémata vstupu
 * a výstupu, ukázková data, režim a chování při chybě (`errorOutput` přidá výstup `error`). */
export type FlowNodeDetail = {
  notes?: string; notesInFlow?: boolean; inputSchema?: Record<string, unknown>; outputSchema?: Record<string, unknown>; example?: unknown;
  mode?: "perItem" | "once"; onError?: "stop" | "continue" | "errorOutput"; retry?: { maxTries: number; waitMs: number };
};
export type FlowNode = {
  id: string; type: string; type_version?: number; params?: Record<string, unknown>; position?: Point; pinned_output?: unknown;
} & FlowNodeDetail;
export type FlowEdge = {
  id: string; source_node: string; source_port: string; target_node: string; target_port: string; kind: PortKind; label?: string;
};
/** Sticky poznámka za uzly (markdown, barva 1–7 jako n8n) a rámec skupiny kolem uzlů (n8n Canvas Groups). */
export type FlowNote = { id: string; content: string; x: number; y: number; width: number; height: number; color?: number };
export type FlowGroup = { id: string; name: string; description?: string; nodeIds: string[]; inputSchema?: Record<string, unknown>; outputSchema?: Record<string, unknown> };
export type FlowGraph = { nodes: FlowNode[]; edges: FlowEdge[]; notes?: FlowNote[]; groups?: FlowGroup[] };

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

/** Registr s porty konkrétních uzlů (porty podle `params`, `POST /api/flow/node-ports`) pod klíčem `node:<id>`. */
export function withNodePorts(types: NodeTypes, nodePorts: ReadonlyMap<string, PortSpec[]> | undefined, graph: FlowGraph): NodeTypes {
  if (!nodePorts?.size) return types;
  const next = new Map(types);
  for (const node of graph.nodes) {
    const base = types.get(node.type), ports = nodePorts.get(node.id);
    if (base && ports) next.set(`node:${node.id}`, { ...base, ports });
  }
  return next;
}

/** Typ uzlu včetně jeho vlastních portů, jsou-li v registru (`withNodePorts`). */
export const specOf = (types: NodeTypes, node: Pick<FlowNode, "id" | "type">): NodeTypeSpec | undefined => types.get(`node:${node.id}`) ?? types.get(node.type);
