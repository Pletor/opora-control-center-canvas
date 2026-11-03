// Data plátna záměru stránky: workflow záměru stránky (nebo null, dokud ho první draft nezaloží), jeho verze a katalog
// `page_intent`. Záměr se nespouští, nic se tedy nepolluje; verze se načtou znovu po vlastním zápisu (`reload`).
import { useCallback, useEffect, useState } from "react";
import type { FlowVersion, FlowWorkflow, NodeTypeSpec } from "@/shared/flow-editor/logic/flow-types";
import { loadVersions } from "@/project/heart-canvas/logic/heart-api";
import { loadIntentTypes, loadIntentWorkflow } from "./intent-api";

export type IntentData = { workflow: FlowWorkflow | null; versions: FlowVersion[]; types: NodeTypeSpec[]; loading: boolean; error: string; reload: () => void };

export function useIntentData(project: string, page: string): IntentData {
  const [workflow, setWorkflow] = useState<FlowWorkflow | null>(null);
  const [versions, setVersions] = useState<FlowVersion[]>([]);
  const [types, setTypes] = useState<NodeTypeSpec[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.all([loadIntentWorkflow(project, page), loadIntentTypes()]).then(async ([intent, catalog]) => {
      const list = intent ? await loadVersions(intent.id) : [];
      if (!alive) return;
      setWorkflow(intent); setTypes(catalog); setVersions(list); setError("");
    }).catch((reason) => { if (alive) setError(reason instanceof Error ? reason.message : String(reason)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [project, page, tick]);

  return { workflow, versions, types, loading, error, reload };
}
