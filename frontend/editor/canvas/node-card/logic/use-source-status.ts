import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { usePolling } from "@/shared/hooks/logic/use-polling";
export type SourceStatus = { status: "present" | "missing" | "unavailable"; path: string; origin: "existing" | "planned" };
export function useSourceStatus(project: string, workspace: string, revision: string) {
  const [value, setValue] = useState<{ key: string; nodes: Record<string, SourceStatus> } | null>(null);
  const key = JSON.stringify([project, workspace, revision]);
  usePolling(async () => {
    try {
      const result = await api<{ nodes: Record<string, SourceStatus> }>("/api/desktop-v3/source-status?" + new URLSearchParams({ project, workspace }));
      setValue({ key, nodes: result.nodes });
    } catch { setValue((current) => (current?.key === key ? null : current)); }
  }, { intervalMs: 30000, refreshKeys: [key] });
  return value?.key === key ? value.nodes : undefined;
}
