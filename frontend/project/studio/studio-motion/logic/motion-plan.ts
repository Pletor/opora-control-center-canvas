// Co se na úrovni Studia hýbe a jak rychle (docs/studio.md §2, hodnoty z docs/zive-zobrazeni-a-knihovna.md §3).
// Trvale jen vazby, jejichž karta na jednom konci se staví: dvě tečky, cyklus 1,05 s + 70 ms × (pořadí mod 4), aby
// sousední vazby nešly v zákrytu; nejvýš 40 vazeb. Jednorázově trasa nově ověřené cesty: jedna tečka po každé vazbě
// trasy, přechod za přechodem, a pulz karet kroků 0,9 s. Staticky vazba prvního selhání neprošlé cesty. Čistá
// logika bez Reactu; plátno a animátor jen čtou výsledek.
import type { StudioLink } from "../../logic/studio-level";
import type { StudioState } from "../../logic/studio-status";

export const MAX_ANIMATED_LINKS = 40;
export const DOTS_PER_LINK = 2;
export const BASE_CYCLE_MS = 1050;
export const STAGGER_MS = 70;
/** Jedna vazba trasy nově ověřené cesty trvá jeden základní cyklus. */
export const PASS_HOP_MS = BASE_CYCLE_MS;
export const PULSE_MS = 900;
/** Třída uzlu React Flow s jednorázovým pulzem karty (styly v `studio-motion.css`). */
export const PULSE_CLASS = "studio-motion__pulse";

/** Perioda tečky na vazbě podle pořadí vazby. */
export const cycleMs = (ordinal: number) => BASE_CYCLE_MS + STAGGER_MS * (ordinal % 4);

/** Poloha (0–1) tečky `dot` z `dots` v nekonečném cyklu: tečky jsou rovnoměrně rozložené po trase, pohyb lineární. */
export function loopProgress(time: number, cycle: number, dot: number, dots: number): number {
  return ((((time % cycle) + cycle) % cycle) / cycle + dot / dots) % 1;
}

/** Poloha jednorázové tečky; null = ještě nevyjela nebo už dojela (není vidět). */
export function onceProgress(time: number, start: number, delay: number, duration: number): number | null {
  const elapsed = time - start - delay;
  return elapsed < 0 || elapsed > duration ? null : elapsed / duration;
}

export type LinkMotion = {
  /** Pořadí stavěné vazby (určuje periodu); null = vazba se nestaví nebo je nad stropem. */
  building: number | null;
  /** Jednorázový průchod: otisk dokladu (identita události) a zpoždění podle pořadí v trase. */
  pass: { stamp: string; delay: number } | null;
  /** Zastavená tečka selhání s větou do tooltipu. */
  failure: { title: string } | null;
};

/** Vazby, kde se staví (zdroj nebo cíl ve stavu „staví se“), v pořadí úrovně s pořadovým číslem; nejvýš 40. */
export function buildingLinks(links: StudioLink[], states: Map<string, StudioState>): Map<string, number> {
  const building = links.filter((link) => states.get(link.source) === "building" || states.get(link.target) === "building");
  return new Map(building.slice(0, MAX_ANIMATED_LINKS).map((link, ordinal) => [link.id, ordinal]));
}

export type LevelPass = { stamp: string; links: string[] };
export type LevelFailure = { linkId: string; title: string };

/** Pohyb každé vazby úrovně; vazba bez pohybu v mapě není. Víc průchodů na téže vazbě: platí poslední. */
export function levelMotion(input: { links: StudioLink[]; states: Map<string, StudioState>; passes: LevelPass[]; failures: LevelFailure[] }): Map<string, LinkMotion> {
  const motion = new Map<string, LinkMotion>();
  const of = (id: string) => motion.get(id) ?? motion.set(id, { building: null, pass: null, failure: null }).get(id)!;
  for (const [id, ordinal] of buildingLinks(input.links, input.states)) of(id).building = ordinal;
  for (const pass of input.passes) pass.links.forEach((id, index) => { of(id).pass = { stamp: pass.stamp, delay: index * PASS_HOP_MS }; });
  for (const failure of input.failures) {
    const current = of(failure.linkId);
    current.failure = { title: current.failure ? `${current.failure.title}\n${failure.title}` : failure.title };
  }
  return motion;
}

/** Jak dlouho průchod cesty s `hops` přechody trvá, než se pohyb ztiší (tečky i pulz karet). */
export const passDurationMs = (hops: number) => Math.max(PULSE_MS, hops * PASS_HOP_MS);
