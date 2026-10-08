import { useEffect, useState } from "react";
import { watchQuery } from "@/shared/hooks/logic/query-poll";

export type AssignmentStatuses = Record<string, { status: "current" | "changed" | "unbound"; resultId: string; source?: "handoff" | "result" }>;
export function useAssignmentStatus(project: string, workspace: string, revision: number, textRevision: number) {
  const [value, setValue] = useState<{ scope: string; nodes: AssignmentStatuses } | null>(null);
  const scope = JSON.stringify([project, workspace]);
  useEffect(() => {
    return watchQuery<{ nodes: AssignmentStatuses }>(
      "/api/desktop-v3/assignment-status?" + new URLSearchParams({ project, workspace }), 30000,
      result => setValue({ scope, nodes: result.nodes }), () => setValue(null));
  }, [project, workspace, revision, textRevision, scope]);
  return value?.scope === scope ? value.nodes : undefined;
}
