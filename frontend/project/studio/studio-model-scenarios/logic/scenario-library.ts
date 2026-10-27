// Knihovna výukových scénářů MODELu (docs/studio.md §4, prototyp `model-panels.mjs` `scenarioLibrary`): hledání,
// kategorie a klíč modelové domény scénáře. Scénář se otevírá jen jako nová pojmenovaná modelová doména
// `scenario:<id>` vedle domén architektury (backend bere jakýkoli klíč domény 1–128 znaků), takže nikdy nepřepíše
// model domény architektury; je-li doména scénáře už uložená, otevře se uložená verze. Čistá logika bez Reactu.
import type { Scenario } from "../../model/simulation/logic";

export const SCENARIO_DOMAIN_PREFIX = "scenario:";
export const ALL_CATEGORIES = "Vše";

/** Klíč modelové domény scénáře; nikdy se nekryje s doménou architektury (ta dvojtečku v id nemá). */
export const scenarioDomain = (scenarioId: string) => SCENARIO_DOMAIN_PREFIX + scenarioId;
export const isScenarioDomain = (domainId: string) => domainId.startsWith(SCENARIO_DOMAIN_PREFIX);
/** Název modelové domény scénáře, jak ho ukazuje lišta. */
export const scenarioDomainName = (scenario: Pick<Scenario, "name">) => `MODEL · ${scenario.name}`;

export function scenarioCategories(list: readonly Scenario[]): string[] {
  return [ALL_CATEGORIES, ...[...new Set(list.map((scenario) => scenario.category))].sort((a, b) => a.localeCompare(b, "cs"))];
}

/** Scénáře podle kategorie a textu (název, popis, princip; bez ohledu na velikost písmen). */
export function filterScenarios(list: readonly Scenario[], query: string, category: string): Scenario[] {
  const needle = query.trim().toLowerCase();
  return list.filter((scenario) => (category === ALL_CATEGORIES || scenario.category === category)
    && (!needle || `${scenario.name} ${scenario.description} ${scenario.principle}`.toLowerCase().includes(needle)));
}
