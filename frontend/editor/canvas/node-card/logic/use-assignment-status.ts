import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";

export type AssignmentStatuses = Record<string, { status: "current" | "changed" | "unbound"; resultId: string; source?: "handoff" | "result" }>;
export function useAssignmentStatus(project: string, workspace: string, revision: number, textRevision: number) {
  const [value, setValue] = useState<{ scope: string; nodes: AssignmentStatuses } | null>(null);
  const scope = JSON.stringify([project, workspace]);
  usePolling(async () => {
    try {
      const result = await api<{ nodes: AssignmentStatuses }>("/api/desktop-v3/assignment-status?" + new URLSearchParams({ project, workspace }));
      setValue({ scope, nodes: result.nodes });
    } catch { setValue((current) => (current?.scope === scope ? null : current)); }
  }, { intervalMs: 30000, refreshKeys: [scope, revision, textRevision] });
  return value?.scope === scope ? value.nodes : undefined;
}
