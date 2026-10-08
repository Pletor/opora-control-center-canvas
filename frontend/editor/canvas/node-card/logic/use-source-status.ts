import { useEffect, useState } from "react";
import { watchQuery } from "@/shared/hooks/logic/query-poll";
export type SourceStatus = { status: "present" | "missing" | "unavailable" | "unspecified"; path: string; origin: "existing" | "planned" };
export function useSourceStatus(project: string, workspace: string, revision: string) {
  const [value, setValue] = useState<{ key: string; nodes: Record<string, SourceStatus> } | null>(null);
  const key = JSON.stringify([project, workspace, revision]);
  useEffect(() => {
    return watchQuery<{ nodes: Record<string, SourceStatus> }>(
      "/api/desktop-v3/source-status?" + new URLSearchParams({ project, workspace }), 30000,
      result => setValue({ key, nodes: result.nodes }), () => setValue(null));
  }, [key, project, workspace]);
  return value?.key === key ? value.nodes : undefined;
}
