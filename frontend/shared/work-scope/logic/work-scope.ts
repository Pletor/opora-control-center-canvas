/** Identity of a problem, independent of its working revision. */
export type WorkScope = { projectId: string; nodeId: string | null };
/** Explicit references share one record between contexts; root keeps the complete project view. */
export function recordsInScope<T extends { id: string; refs: { nodeIds: string[] } }>(records: T[], scope: WorkScope): T[] {
  const seen = new Set<string>();
  return records.filter(record => {
    if (seen.has(record.id) || (scope.nodeId !== null && !record.refs.nodeIds.includes(scope.nodeId))) return false;
    seen.add(record.id); return true;
  });
}
