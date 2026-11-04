// Data plátna knihovny: katalog toků dat (s variantami dynamických typů pro paletu), detail plátna s verzemi
// a rodokmenem a detail zdroje, ze kterého plátno vychází (titulek a verze pro „vychází z …“). Plátno se nespouští,
// nic se nepolluje; po vlastním zápisu rodič zavolá `reload`.
import { useCallback, useEffect, useState } from "react";
import type { NodeTypeSpec } from "@/shared/flow-editor/logic/flow-types";
import { loadFlow, loadLibraryTypes, nodePorts, type LibraryFlowDetail } from "./library-api";
import { variantParams } from "./node-ports";

export type LibraryFlowData = { flow: LibraryFlowDetail | null; source: LibraryFlowDetail | null; types: NodeTypeSpec[]; loading: boolean; error: string; reload: () => void };

let catalog: Promise<NodeTypeSpec[]> | null = null;
/** Katalog je stejný pro všechna plátna; varianty se spočtou jednou za načtení stránky. */
function libraryTypes(): Promise<NodeTypeSpec[]> {
  catalog ??= loadLibraryTypes().then((types) => Promise.all(types.map(async (spec) => {
    const sets = variantParams(spec);
    if (!sets.length) return spec;
    // Varianty jen zpřesní filtr palety na port; když je server nespočte, typ zůstane bez nich.
    return Promise.all(sets.map(async (params) => ({ params, ports: await nodePorts(spec.type, params) }))).then((variants) => ({ ...spec, variants }), () => spec);
  }))).catch((error) => { catalog = null; throw error; });
  return catalog;
}

export function useLibraryFlow(flowId: string): LibraryFlowData {
  const [state, setState] = useState<Omit<LibraryFlowData, "reload">>({ flow: null, source: null, types: [], loading: true, error: "" });
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((value) => value + 1), []);
  useEffect(() => {
    let alive = true;
    setState((old) => ({ ...old, loading: true }));
    Promise.all([loadFlow(flowId), libraryTypes()]).then(async ([flow, types]) => {
      const source = flow.derivedFrom ? await loadFlow(flow.derivedFrom.workflowId).catch(() => null) : null;
      if (alive) setState({ flow, source, types, loading: false, error: "" });
    }).catch((reason) => { if (alive) setState((old) => ({ ...old, loading: false, error: reason instanceof Error ? reason.message : String(reason) })); });
    return () => { alive = false; };
  }, [flowId, tick]);
  return { ...state, reload };
}
