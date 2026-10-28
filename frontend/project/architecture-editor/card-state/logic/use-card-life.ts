// Stavy karet a cesty pro pohyb, jednou za změnu faktů (graf, uzavření karet, stav práce, díry mapy, cesty s `lastRun`,
// nálezy strážců z `useCardGuards`).
// Volá jen `ArchitectureEditor`; Editor stránky i Mapa domény dostanou hotový výsledek v props. Nic nečte ani neukládá.
import { useMemo } from "react";
import type { Graph } from "@/shared/types/logic/types";
import type { NodeWorkflowState } from "@/shared/desktop-state/logic/types";
import type { WorkStatus } from "../../live-status/logic/live-model";
import type { MapCheck } from "../../domain-map/map-check/logic/map-check";
import type { DerivedJourney } from "../../domain-map/logic/derived-journeys";
import type { GuardTally } from "@/project/studio/studio-guards/logic/guard-tally";
import { cardLife, type CardLife } from "./card-state";

export function useCardLife(input: { graph: Graph; nodes: Record<string, NodeWorkflowState>; work: WorkStatus | null; check: MapCheck | null; derived: DerivedJourney[] | null; guards?: Map<string, GuardTally> }): CardLife {
  const { graph, nodes, work, check, derived, guards } = input;
  const doneKey = Object.entries(nodes).filter(([, value]) => value.done?.confirmed).map(([id]) => id).sort().join("\n");
  return useMemo(() => cardLife({ graph, doneIds: doneKey ? doneKey.split("\n") : [], work, check, derived, guards }), [graph, doneKey, work, check, derived, guards]);
}
