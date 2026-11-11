// Stav karty Studia (docs/studio.md §2), odvozený, nikdy zadaný: plán, staví se, hotovo, ověřeno, díra. Čistá logika
// bez Reactu nad hotovými fakty (`studio-facts.ts`): uzavřené karty (`done.confirmed`), karty s aktivním nárokem práce,
// nálezy kontroly mapy po uzlech a cesty zákazníka s posledním ověřením. Rodič agreguje děti („4/7 stojí, 1 se staví“).
import type { DerivedJourney } from "@/project/architecture-editor/domain-site/logic/derived-journeys";
import { studioDescendants, type StudioItem, type StudioTree } from "./studio-tree";
import { sumGuards, type GuardTally } from "../studio-guards/logic/guard-tally";
import { sumWorktrees, type WorktreeMark, type WorktreeTally } from "../studio-worktree/logic/worktree-tally";

export type StudioState = "plan" | "building" | "done" | "verified" | "hole";
/** Cesta zákazníka domény: stránky jejích kroků, stránka podle kroku a odvození backendu s `lastRun` (chybí = nenačteno). */
export type StudioJourney = {
  id: string; name: string; domainId: string; pages: Set<string>;
  /** Stránka každého kroku podle id kroku (včetně menu `nav`): přechody `lastRun` a odvození jsou mezi kroky. */
  stepPages: Map<string, string>;
  derived: DerivedJourney | undefined;
};
export type StudioFacts = {
  done: Set<string>;
  building: Set<string>;
  /** Nálezy kontroly mapy po uzlech grafu (hrana se počítá zdroji, cesta doméně). */
  holes: Map<string, string[]>;
  journeys: StudioJourney[];
  /** Otevřené nálezy strážců po kartách (agent-state `cards[].guardFindings`); chybí = nenačteno. */
  guards?: Map<string, GuardTally>;
  /** Worktree, které na kartě pracují (díra zavřená / otevřená, lease, karta v práci); chybí = nenačteno. */
  worktrees?: Map<string, WorktreeMark[]>;
  /** Díry mainu po uzlech, které některý worktree už zavírá („v práci“); chybí = nenačteno. */
  holesInWork?: Map<string, number>;
};
export type StudioSummary = {
  /** Přímé děti karty ve Studiu. */
  children: number;
  /** Uzly grafu pod kartou (bez sekcí, bez karty samé). */
  total: number; done: number; building: number;
  /** Díry mapy karty a všech jejích potomků. */
  holes: number;
};
export type StudioStatus = {
  state: StudioState; summary: StudioSummary; ownHoles: string[]; journeys: StudioJourney[];
  /** Nálezy strážců karty a všech jejích potomků (součet, nejvážnější závažnost) jako díry; `null` = žádný. */
  guards: GuardTally | null;
  /** Kolik z děr (`summary.holes`) už některý worktree zavírá („3 díry · 1 v práci“). */
  holesInWork: number;
  /** Worktree karty a všech jejích potomků (každý jednou); `null` = na stromě se ve worktree nepracuje. */
  worktree: WorktreeTally | null;
};

/** Cesty, na kterých karta leží: doména = všechny její cesty; jinak cesty, jejichž krok míří na stránku karty. */
export function journeysOf(item: StudioItem, journeys: StudioJourney[]): StudioJourney[] {
  if (item.kind === "domain") return journeys.filter((journey) => journey.domainId === item.id);
  return item.pageId ? journeys.filter((journey) => journey.pages.has(item.pageId!)) : [];
}

/** Ověřená cesta: má doklad, prošel a není zastaralý; rozbitá cesta ověřená není. */
export const journeyVerified = (journey: StudioJourney) => {
  const run = journey.derived?.lastRun;
  return !!run && run.passed && !run.stale && !journey.derived?.broken;
};

export function cardStatus(tree: StudioTree, item: StudioItem, facts: StudioFacts): StudioStatus {
  const below = studioDescendants(tree, item.id);
  const real = below.filter((child) => child.node);
  const children = tree.children.get(item.id)?.length ?? 0;
  const ownHoles = item.node ? facts.holes.get(item.id) ?? [] : [];
  const summary: StudioSummary = {
    children, total: real.length,
    done: real.filter((child) => facts.done.has(child.id)).length,
    building: real.filter((child) => facts.building.has(child.id)).length,
    holes: ownHoles.length + real.reduce((sum, child) => sum + (facts.holes.get(child.id)?.length ?? 0), 0),
  };
  // Sekce nemá vlastní uzavření: stojí, když stojí všechny její komponenty.
  const done = item.node ? facts.done.has(item.id) : summary.total > 0 && summary.done === summary.total;
  const journeys = journeysOf(item, facts.journeys);
  const building = facts.building.has(item.id) || summary.building > 0;
  const state: StudioState = building ? "building" : ownHoles.length ? "hole"
    : done && journeys.length > 0 && journeys.every(journeyVerified) ? "verified" : done ? "done" : "plan";
  const guards = sumGuards([item.node ? facts.guards?.get(item.id) : undefined, ...real.map((child) => facts.guards?.get(child.id))]);
  const own = (map: Map<string, number> | undefined) => (item.node ? map?.get(item.id) ?? 0 : 0);
  const holesInWork = own(facts.holesInWork) + real.reduce((sum, child) => sum + (facts.holesInWork?.get(child.id) ?? 0), 0);
  const worktree = sumWorktrees([item.node ? facts.worktrees?.get(item.id) : undefined, ...real.map((child) => facts.worktrees?.get(child.id))]);
  return { state, summary, ownHoles, journeys, guards, holesInWork, worktree };
}
