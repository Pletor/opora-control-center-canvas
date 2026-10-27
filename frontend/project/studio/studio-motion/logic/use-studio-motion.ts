// Pohyb aktuální úrovně Studia pro rodiče (docs/studio.md §2): ze stavů karet, vazeb úrovně a cest s `lastRun`
// složí pohyb vazeb a karty k jednorázovému pulzu. Nový prošlý doklad (změna oproti minulému čtení) spustí jeden
// průchod, který po `passDurationMs` sám utichne; první načtení jen zapamatuje otisky. Při omezeném pohybu se průchod
// nespouští (stav nese štítek karty „ověřeno“). Nic neukládá.
import { useEffect, useMemo, useRef, useState } from "react";
import type { StudioLink } from "../../logic/studio-level";
import type { StudioJourney, StudioState } from "../../logic/studio-status";
import type { StudioTree } from "../../logic/studio-tree";
import { freshPasses, journeyKey, runFailures, runStamps, type RunStamps } from "./run-events";
import { hopLink, routeOnLevel } from "./journey-route";
import { levelMotion, passDurationMs, type LevelFailure, type LevelPass } from "./motion-plan";

type Pass = { stamp: string; journey: StudioJourney };
const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useStudioMotion(input: {
  tree: StudioTree; focus: string | null; links: StudioLink[]; states: Map<string, StudioState>;
  /** Cesty s odvozením; null = odvození ještě není načtené (nic se neporovnává). */
  journeys: StudioJourney[] | null;
}) {
  const { tree, focus, links, states, journeys } = input;
  const stamps = useRef<RunStamps | null>(null);
  const [passes, setPasses] = useState<Pass[]>([]);

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
    const place = { tree, focus, links };
    const pulsing = new Set<string>();
    const levelPasses: LevelPass[] = passes.map(({ stamp, journey }) => {
      const route = routeOnLevel(place, journey, journey.derived?.segments ?? []);
      route.cards.forEach((card) => pulsing.add(card));
      return { stamp, links: route.links };
    });
    const failures: LevelFailure[] = (journeys ? runFailures(journeys) : []).flatMap((failure) => {
      const link = hopLink(place, failure.journey, failure);
      return link ? [{ linkId: link.id, title: failure.title }] : [];
    });
    return { links: levelMotion({ links, states, passes: levelPasses, failures }), pulsing };
  }, [tree, focus, links, states, passes, journeys]);
}
