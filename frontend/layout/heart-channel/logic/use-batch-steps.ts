// Kroky skončených dávek srdce pro rozbalený řádek dávky: načtou se jednou při prvním rozbalení
// (dávka je hotová, její zápisy se už nemění) ze záznamu činnosti v rozsahu dávky. Volá ho jen HeartChannel.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ActivityEntry } from "@/editor/canvas/activity-log/logic/activity-log";
import { fetchHeartSteps } from "./heart-api";
import { heartStepsQuery, type StepRange } from "./heart-live";

export type BatchSteps = { loading: boolean; error: string; entries: ActivityEntry[] };

export function useBatchSteps(project: string) {
  const [byBatch, setByBatch] = useState<Record<string, BatchSteps>>({});
  const asked = useRef(new Set<string>());
  const projectRef = useRef(project);
  useEffect(() => {
    projectRef.current = project;
    asked.current = new Set();
    setByBatch({});
  }, [project]);

  const load = useCallback((key: string, range: StepRange) => {
    if (asked.current.has(key)) return;
    asked.current.add(key);
    const owner = project;
    const put = (value: BatchSteps) => { if (projectRef.current === owner) setByBatch((all) => ({ ...all, [key]: value })); };
    put({ loading: true, error: "", entries: [] });
    fetchHeartSteps(heartStepsQuery(project, range))
      .then((entries) => put({ loading: false, error: "", entries }))
      .catch((cause) => {
        asked.current.delete(key);  // další rozbalení zkusí znovu
        put({ loading: false, error: cause instanceof Error ? cause.message : String(cause), entries: [] });
      });
  }, [project]);

  return { byBatch, load };
}
