import type { SourceStatus } from "@/editor/canvas/node-card/logic/use-source-status";
export type AssignmentStatus = { status: "current" | "changed" | "unbound"; resultId: string; source?: "handoff" | "result" };
/** Stejný doložený poll dostává kompaktní karta i popup, včetně nezměněného zadání. */
export function cardStatusData(nodeId: string, sources?: Record<string, SourceStatus>, assignments?: Record<string, AssignmentStatus>) {
  return { sourceStatus: sources?.[nodeId], assignmentStatus: assignments?.[nodeId] };
}
