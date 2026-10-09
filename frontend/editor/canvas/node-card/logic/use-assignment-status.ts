import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";

export type AssignmentStatuses = Record<string, { status: "current" | "changed" | "unbound"; resultId: string; source?: "handoff" | "result" }>;
export function useAssignmentStatus(project: string, workspace: string, revision: number, textRevision: number) {
  const [value, setValue] = useState<{ scope: string; nodes: AssignmentStatuses } | null>(null);
  const scope = JSON.stringify([project, workspace]);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await api<{ nodes: AssignmentStatuses }>("/api/desktop-v3/assignment-status?" + new URLSearchParams({ project, workspace }));
        if (live) setValue({ scope, nodes: result.nodes });
      } catch { if (live) setValue(null); }
      if (live) timer = setTimeout(refresh, 30000);
    }
    void refresh();
    return () => { live = false; clearTimeout(timer); };
  }, [project, workspace, revision, textRevision, scope]);
  return value?.scope === scope ? value.nodes : undefined;
}
