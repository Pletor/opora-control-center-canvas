// Jediné místo, které Studio načítá (vrstva Skutečnost, docs/studio.md §1, jen čtení): graf architektury tímtéž
// `/api/view` jako Architektura projektu (`useArchitectureGraph`), uzavření karet z Desktop stavu, stav práce
// (`useDomainLive`, jen u projektů s worktree podle schopnosti `worktreeLive`), díry mapy a cesty s `lastRun`
// (`useStudioRuns`, čte se i průběžně, protože nový doklad cesty otisk mapy nemění).
// Vrací strom Studia a fakta pro stavy karet; nic nezapisuje.
import { useMemo } from "react";
import type { Graph } from "@/shared/types/logic/types";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import { useArchitectureGraph } from "@/project/architecture-editor/logic/use-architecture-graph";
import { useDomainLive } from "@/project/architecture-editor/logic/use-domain-live";
import { useMapCheck } from "@/project/architecture-editor/logic/use-map-check";
import { buildStudioTree } from "./studio-tree";
import { studioFacts } from "./studio-facts";
import { useStudioRuns } from "./use-studio-runs";

const EMPTY: Graph = { nodes: [], edges: [] };

export function useStudioData(project: string, workspace: string, worktreeLive: boolean) {
  const store = useArchitectureGraph(project, workspace);
  const desktop = useDesktopState(project, workspace);
  const live = useDomainLive(project, null, worktreeLive);
  const digest = store.view?.digest;
  const runs = useStudioRuns(project, digest);
  const derived = runs.journeys;
  const check = useMapCheck(project, digest);
  const graph = store.view?.graph ?? EMPTY;
  const tree = useMemo(() => buildStudioTree(graph), [graph]);
  const nodes = desktop.state.nodes;
  const doneIds = useMemo(() => Object.entries(nodes).filter(([, value]) => value.done?.confirmed).map(([id]) => id), [nodes]);
  const work = live.work.data;
  const facts = useMemo(() => studioFacts({ graph, doneIds, work, check, derived }), [graph, doneIds, work, check, derived]);
  return {
    graph, tree, facts, derived,
    loaded: !!store.view, loading: store.loading, error: store.error ?? desktop.error ?? "",
    reload: () => { void store.reload().catch(() => undefined); desktop.reload(); live.refreshWork(); runs.refresh(); },
  };
}
