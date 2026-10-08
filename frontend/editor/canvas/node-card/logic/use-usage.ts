import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";

export type Usage = { tokens: number | null; durationMs: number | null; attempts: number | null; reports: number };
export type UsageSummary = { nodes: Record<string, Usage>; sectors: Record<string, Usage> };

export function useUsage(project: string, workspace: string, revision: number): UsageSummary | null {
  const [value, setValue] = useState<{ scope: string; summary: UsageSummary } | null>(null);
  const scope = JSON.stringify([project, workspace]);
  useEffect(() => {
    let current = true;
    api<UsageSummary>("/api/desktop-v3/usage-summary?" + new URLSearchParams({ project, workspace }))
      .then((summary) => { if (current) setValue({ scope, summary }); })
      .catch(() => { if (current) setValue(null); });
    return () => { current = false; };
  }, [project, workspace, revision, scope]);
  return value?.scope === scope ? value.summary : null;
}
