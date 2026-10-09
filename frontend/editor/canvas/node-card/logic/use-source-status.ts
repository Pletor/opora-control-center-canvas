import { useEffect, useState } from "react";
import { api } from "@/shared/types/logic/types";
export type SourceStatus = { status: "present" | "missing" | "unavailable"; path: string; origin: "existing" | "planned" };
export function useSourceStatus(project: string, workspace: string, revision: string) {
  const [value, setValue] = useState<{ key: string; nodes: Record<string, SourceStatus> } | null>(null);
  const key = JSON.stringify([project, workspace, revision]);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await api<{ nodes: Record<string, SourceStatus> }>("/api/desktop-v3/source-status?" + new URLSearchParams({ project, workspace }));
        if (live) setValue({ key, nodes: result.nodes });
      } catch { if (live) setValue(null); }
      if (live) timer = setTimeout(refresh, 30000);
    }
    void refresh();
    return () => { live = false; clearTimeout(timer); };
  }, [key, project, workspace]);
  return value?.key === key ? value.nodes : undefined;
}
