import type { NodeBrief } from "@/shared/desktop-state/logic/types";

export const asRecord = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
export type ResultEnvelope = { project: string; workspace: string; nodeId: string; expectedRevision: number; contextVersion: string; agent: string; output: Record<string, unknown> };
export type AcceptedResult = { id: string; nodeId: string; contextVersion: string | null; binding: string; agent: string; createdAt: string; output: unknown; specification?: unknown };
export type ResultHistory = { items: AcceptedResult[]; hasMore: boolean; assignmentStatus?: Record<string, string> };

export function resultTemplate(brief: NodeBrief): string {
  const request = asRecord(asRecord(brief.outputContract).request);
  return JSON.stringify({ ...request, agent: "", output: { schema: "opora.agent-output/1", blocks: [], reports: [], done: { proposed: false, note: "" }, decisions: [] } }, null, 2);
}

/** A returned result carries its own original version. Reloading a brief never rebinds it. */
export function parseResult(text: string, scope: { project: string; workspace: string; nodeId: string }): ResultEnvelope {
  let value: Record<string, unknown>;
  try { value = asRecord(JSON.parse(text)); } catch { throw new Error("Výsledek není platný JSON."); }
  for (const key of ["project", "workspace", "nodeId"] as const) if (value[key] !== scope[key]) throw new Error("Výsledek patří jinému projektu, prostoru nebo uzlu.");
  if (typeof value.contextVersion !== "string" || !value.contextVersion) throw new Error("Výsledek musí obsahovat původní contextVersion z předaného zadání.");
  if (!Number.isInteger(value.expectedRevision) || (value.expectedRevision as number) < 0) throw new Error("Chybí původní expectedRevision.");
  if (typeof value.agent !== "string" || !value.agent.trim()) throw new Error("Doplňte označení autora do pole agent.");
  if (asRecord(value.output).schema !== "opora.agent-output/1") throw new Error("Chybí output podle kontraktu opora.agent-output/1.");
  return value as ResultEnvelope;
}

export function verifyResult(history: ResultHistory, accepted: AcceptedResult): AcceptedResult {
  const found = history.items.find((item) => item.id === accepted.id);
  if (!found || found.nodeId !== accepted.nodeId || found.contextVersion !== accepted.contextVersion) throw new Error("Uložený výsledek zatím nebyl zpětně ověřen. Zkuste ověření znovu; výsledek znovu neodesílejte.");
  return found;
}
