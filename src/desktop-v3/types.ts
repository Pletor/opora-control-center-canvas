// Typy pro Desktop v3 panely. Přesně dle CONTRACT.md; žádná demo/dummy data.

export type Setting = { id: string; key: string; value: string };

export type RuleKind = "must" | "must_not";
export type RuleScope = "project" | "path" | "node";
export type Rule = { id: string; text: string; kind: RuleKind; scope: RuleScope; target: string };

export type DecisionBy = "human" | "agent";
export type Decision = {
  id: string;
  text: string;
  pinned: boolean;
  path: string;
  nodeId: string;
  createdAt: string;
  by: DecisionBy;
};

export type NodePhase = "discover" | "define" | "build" | "verify" | "live";
export const NODE_PHASES: NodePhase[] = ["discover", "define", "build", "verify", "live"];

export type Criterion = { id: string; text: string; checked: boolean };
export type Step = { id: string; text: string; assignee: string; done: boolean };
export type NodeWorkflowState = { phase: NodePhase; criteria: Criterion[]; steps: Step[] };

export type TicketPriority = "low" | "normal" | "high";
export type TicketStatus = "open" | "doing" | "done";
export type Ticket = {
  id: string;
  title: string;
  priority: TicketPriority;
  status: TicketStatus;
  nodeId: string;
  sessionId: string;
  createdBy: DecisionBy;
};

export type DesktopState = {
  settings: Setting[];
  rules: Rule[];
  decisions: Decision[];
  nodes: Record<string, NodeWorkflowState>;
  tickets: Ticket[];
};

export const emptyDesktopState = (): DesktopState => ({
  settings: [],
  rules: [],
  decisions: [],
  nodes: {},
  tickets: [],
});

export const emptyNodeWorkflow = (): NodeWorkflowState => ({
  phase: "discover",
  criteria: [],
  steps: [],
});

export type StateResponse = { revision: number; state: DesktopState; readOnly: boolean };

export type SourceManifestEntry = {
  kind: string;
  ownerId: string;
  revision: number | null;
  included: boolean;
  reason: string;
};

export type Packet = {
  schema: "opora.packet/1";
  scope: { project: string; workspace: string; nodeId: string; path: string; sessionId: string };
  task: Record<string, unknown>;
  context: Record<string, unknown>;
  sourceManifest: SourceManifestEntry[];
  warnings: string[];
  [key: string]: unknown;
};

export type PacketPreviewResponse = { digest: string; packet: Packet };
export type PacketSnapshotResponse = { id: string; digest: string; packet: Packet };

export type HandoffRunStatus =
  | "prepared"
  | "starting"
  | "running"
  | "stopping"
  | "verifying"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

export type HandoffRun = {
  id: string;
  digest: string;
  scope: { project: string; workspace: string; node: string };
  task: string;
  status: HandoffRunStatus;
  provider?: string | null;
  model?: string | null;
  budgetSeconds?: number | null;
  contextSummary?: unknown;
  events?: { kind: string; observedAt?: string }[];
  error?: string | null;
  verification?: { passed: boolean | null };
  result?: { content: string; sha256: string } | null;
};

export type PlanningRun = {
  id: string;
  project_id: string;
  workspace: string;
  layer: string;
  digest: string;
  status: string;
  message: string;
  output: string;
  provider_billing: number | null;
  created_at: string;
  updated_at: string;
};
