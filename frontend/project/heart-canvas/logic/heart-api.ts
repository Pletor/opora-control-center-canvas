// Plátno srdce nad API engine toků (`backend/api/flow/README.md`). Čte workflow, verze, registr typů, běhy, log a
// prostoje; zapisuje jen nový `draft` a jeho povýšení na `candidate`. `active` se tady nikdy nenastavuje: aktivní
// verzi přepíná až eval (kontrakt §3.5 „Úprava v něm vytvoří kandidáta na eval“).
import { api } from "@/shared/types/logic/types";
import type { FlowGraph, FlowRun, FlowRunDetail, FlowVersion, FlowWorkflow, LogEvent, NodeTypeSpec, Stall } from "@/shared/flow-editor/logic/flow-types";

const BASE = "/api/flow";
const list = <T>(raw: unknown, key: string): T[] => {
  const value = raw && typeof raw === "object" ? (raw as Record<string, unknown>)[key] : null;
  return Array.isArray(value) ? value as T[] : [];
};

export const flowUrls = {
  workflows: (project: string) => `${BASE}/workflows?${new URLSearchParams({ project })}`,
  versions: (workflow: string) => `${BASE}/workflows/${encodeURIComponent(workflow)}/versions`,
  nodeTypes: () => `${BASE}/node-types`,
  runs: (workflow: string, limit = 50) => `${BASE}/runs?${new URLSearchParams({ workflow, limit: String(limit) })}`,
  run: (run: string) => `${BASE}/runs/${encodeURIComponent(run)}`,
  log: (run: string, seq = 0) => `${BASE}/runs/${encodeURIComponent(run)}/log?${new URLSearchParams({ seq: String(seq), limit: "2000" })}`,
  stalls: () => `${BASE}/stalls`,
  candidate: (version: string) => `${BASE}/versions/${encodeURIComponent(version)}/candidate`,
};

/** Srdce projektu: vlastní workflow `kind=heart` projektu má přednost před sdíleným („Srdce v1“, project_id null). */
export function pickHeartWorkflow(workflows: readonly FlowWorkflow[], project: string): FlowWorkflow | null {
  const hearts = workflows.filter((item) => item.kind === "heart");
  return hearts.find((item) => item.project_id === project) ?? hearts.find((item) => item.project_id === null) ?? null;
}

/** Zobrazená verze: vybraná, jinak aktivní, jinak nejnovější. */
export function pickVersion(versions: readonly FlowVersion[], wanted: string | null): FlowVersion | null {
  return versions.find((item) => item.id === wanted) ?? versions.find((item) => item.status === "active") ?? versions.at(-1) ?? null;
}

export const loadWorkflows = (project: string) => api<unknown>(flowUrls.workflows(project)).then((raw) => list<FlowWorkflow>(raw, "workflows"));
export const loadVersions = (workflow: string) => api<unknown>(flowUrls.versions(workflow)).then((raw) => list<FlowVersion>(raw, "versions"));
export const loadNodeTypes = () => api<unknown>(flowUrls.nodeTypes()).then((raw) => list<NodeTypeSpec>(raw, "node_types"));
export const loadRuns = (workflow: string) => api<unknown>(flowUrls.runs(workflow)).then((raw) => list<FlowRun>(raw, "runs"));
export const loadRun = (run: string) => api<FlowRunDetail>(flowUrls.run(run));
export const loadLog = (run: string) => api<unknown>(flowUrls.log(run)).then((raw) => list<LogEvent>(raw, "events"));
export const loadStalls = () => api<unknown>(flowUrls.stalls()).then((raw) => list<Stall>(raw, "stalls"));

/** Úprava grafu = nová neměnná verze `draft` nad zobrazenou verzí (backend graf validuje, 422 = neplatný graf). */
export const saveDraft = (workflow: string, graph: FlowGraph, parent: string | null) =>
  api<FlowVersion>(flowUrls.versions(workflow), { graph, parent_version_id: parent });
export const proposeCandidate = (version: string) => api<FlowVersion>(flowUrls.candidate(version), {});
