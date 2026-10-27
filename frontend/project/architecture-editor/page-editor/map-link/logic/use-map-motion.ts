// Pohyb plátna Editoru stránky pro rodiče (`PageEditor`): ze stavů karet, vazeb rozsahu a cest s `lastRun` složí pohyb
// vazeb a karty k jednorázovému pulzu (`link-motion.ts`). Nový prošlý doklad oproti minulému čtení spustí jeden
// průchod, který po `passDurationMs` sám utichne; první načtení jen zapamatuje otisky (stejně jako `useStudioMotion`).
// Při omezeném pohybu se průchod nespouští, stav nese štítek karty. Nic neukládá.
import { useEffect, useMemo, useRef, useState } from "react";
import type { Graph } from "@/shared/types/logic/types";
import type { StudioJourney } from "@/project/studio/logic/studio-status";
import { freshPasses, journeyKey, runStamps, type RunStamps } from "@/project/studio/studio-motion/logic/run-events";
import { passDurationMs } from "@/project/studio/studio-motion/logic/motion-plan";
import type { CardState } from "../../../card-state/logic/card-state";
import { mapMotion, type MapMotion, type MapPass } from "./link-motion";

const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useMapMotion(input: { graph: Graph; scopeId: string; pageId: string | null; states: ReadonlyMap<string, CardState>; journeys: StudioJourney[] | null }): MapMotion {
  const { graph, scopeId, pageId, states, journeys } = input;
  const stamps = useRef<RunStamps | null>(null);
  const [passes, setPasses] = useState<MapPass[]>([]);

  useEffect(() => {
    if (!journeys) return;
    const fresh = freshPasses(stamps.current, journeys);
    stamps.current = runStamps(journeys);
    if (!fresh.length || reducedMotion()) return;
    setPasses(fresh.map((journey) => ({ stamp: `${journeyKey(journey)}@${journey.derived!.lastRun!.at}`, journey })));
  }, [journeys]);

  useEffect(() => {
    if (!passes.length) return;
    const longest = Math.max(...passes.map((pass) => passDurationMs(pass.journey.derived?.segments.length ?? 0)));
    const timer = setTimeout(() => setPasses([]), longest + 100);
    return () => clearTimeout(timer);
  }, [passes]);

  return useMemo(() => {
    const cards = graph.nodes.filter((node) => node.parentId === scopeId);
    const ids = new Set(cards.map((card) => card.id));
    const edges = graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target));
    const cardStates = new Map(cards.flatMap((card) => (states.has(card.id) ? [[card.id, states.get(card.id)!.state] as const] : [])));
    return mapMotion({ cards, edges, pageId }, cardStates, passes, journeys);
  }, [graph, scopeId, pageId, states, passes, journeys]);
}
