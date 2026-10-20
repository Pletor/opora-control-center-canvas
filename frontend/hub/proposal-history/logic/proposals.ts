export type ProposalContext = { head: string | null; contextVersion: string; specRevision: number };
export type ProposalRecord = {
  id: string; parent: string | null; subject: string; specRevision: number;
  by: { kind: string; name: string }; createdAt: string; inMain: boolean;
};
export type ProposalChange = { op: "add" | "remove" | "replace"; path: string; before?: unknown; after?: unknown };
export type ProposalDiff = { before: string; after: string; changes: ProposalChange[] };

// A request from an older scope or refresh must never replace the current result.
export class ProposalRequests {
  private generation = 0;
  next() { const ticket = ++this.generation; return () => ticket === this.generation; }
  invalidate() { this.generation++; }
}

export function proposalPayload(project: string, workspace: string, scope: string,
  subject: string, context: ProposalContext) {
  return { project, workspace, scope, subject: subject.trim(),
    expectedHead: context.head, expectedContextVersion: context.contextVersion };
}

export function diffValue(value: unknown): string {
  return value === undefined ? "—" : typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
