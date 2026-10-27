// Cesty zákazníka jako trychtýř stránek na aplikaci; čistá logika bez Reactu. Kontrakt: docs/architektura-pro-agenty.md §3.2.
// Člověk zadává kroky (stránka, role, zážitek, počet lidí, odbočka `after`); vazby mezi kroky po mapě odvodí stroj (§6).
// Prázdné texty a prázdný seznam se neukládají, nic se nedoplňuje výchozí hodnotou.
import type { ApplicationSite, CanvasNode, CustomerJourney, JourneyStep } from "@/shared/types/logic/types";

/** Nejvýš tolik cest na aplikaci a kroků na cestu povolí backend (`site_metadata.py`); kroků musí být aspoň dva. */
export const MAX_JOURNEYS = 20;
export const MIN_STEPS = 2;
export const MAX_STEPS = 30;
/** Vstup z navigace (menu) místo konkrétní stránky; smí ho mít jen první krok. */
export const FROM_NAV = "nav";

function freeId(used: Iterable<string>, prefix: string): string {
  const taken = new Set(used);
  let n = 1;
  while (taken.has(prefix + n)) n += 1;
  return prefix + n;
}

/** Vrátí `site` s novým seznamem cest; prázdný seznam klíč `journeys` vynechá (backend prázdné pole odmítne). */
function withJourneys(site: ApplicationSite, journeys: CustomerJourney[]): ApplicationSite {
  const { journeys: _old, ...rest } = site;
  return journeys.length ? { ...rest, journeys } : rest;
}

/** Nová cesta `cesta-N` z menu na poslední stránku (zatím neuložená); bez stránek nebo na 20 cestách `null`. */
export function newJourney(site: ApplicationSite, pageIds: string[]): CustomerJourney | null {
  const journeys = site.journeys ?? [];
  if (journeys.length >= MAX_JOURNEYS || !pageIds.length) return null;
  return { id: freeId(journeys.map((journey) => journey.id), "cesta-"), name: "Nová cesta",
    steps: [{ id: "krok-1", page: FROM_NAV }, { id: "krok-2", page: pageIds[pageIds.length - 1] }] };
}

/** Uloží upravenou cestu na místo té se stejným id, novou přidá na konec. */
export function replaceJourney(site: ApplicationSite, journey: CustomerJourney): ApplicationSite {
  const journeys = site.journeys ?? [];
  return withJourneys(site, journeys.some((item) => item.id === journey.id)
    ? journeys.map((item) => (item.id === journey.id ? journey : item)) : [...journeys, journey]);
}

/** Odebere cestu; po poslední zmizí i klíč `journeys`. */
export function removeJourney(site: ApplicationSite, id: string): ApplicationSite {
  return site.journeys ? withJourneys(site, site.journeys.filter((journey) => journey.id !== id)) : site;
}

/** Krok smí navazovat jen na dřívější krok a první krok nenavazuje na nic: jinak `after` zmizí (navazuje na předchozí). */
function tidy(steps: JourneyStep[]): JourneyStep[] {
  return steps.map((step, index) => {
    if (step.after === undefined || steps.slice(0, index).some((other) => other.id === step.after)) return step;
    const { after: _drop, ...rest } = step;
    return rest;
  });
}

/** Přidá krok `krok-N` na konec s první stránkou, která v cestě ještě není (jinak první stránkou); nad stropem nic. */
export function addStep(journey: CustomerJourney, pageIds: string[]): CustomerJourney {
  if (journey.steps.length >= MAX_STEPS || !pageIds.length) return journey;
  const used = new Set(journey.steps.map((step) => step.page));
  const page = pageIds.find((id) => !used.has(id)) ?? pageIds[0];
  return { ...journey, steps: [...journey.steps, { id: freeId(journey.steps.map((step) => step.id), "krok-"), page }] };
}

/** Změní krok podle id; `id` se přepsat nedá. Pole s hodnotou `undefined` z kroku zmizí (prázdné se neukládá). */
export function updateStep(journey: CustomerJourney, id: string, patch: Partial<Omit<JourneyStep, "id">>): CustomerJourney {
  return { ...journey, steps: tidy(journey.steps.map((step) => {
    if (step.id !== id) return step;
    const next: Record<string, unknown> = { ...step, ...patch, id };
    for (const key of Object.keys(next)) if (next[key] === undefined) delete next[key];
    return next as JourneyStep;
  })) };
}

/** Odebere krok; kroky, které na něj navazovaly, navážou na předchozí krok v seznamu. */
export function removeStep(journey: CustomerJourney, id: string): CustomerJourney {
  return { ...journey, steps: tidy(journey.steps.filter((step) => step.id !== id)) };
}

/** Posune krok o jedno místo; odbočka, která by mířila dopředu, se zruší. */
export function moveStep(journey: CustomerJourney, id: string, direction: -1 | 1): CustomerJourney {
  const index = journey.steps.findIndex((step) => step.id === id);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= journey.steps.length) return journey;
  const steps = [...journey.steps];
  [steps[index], steps[target]] = [steps[target], steps[index]];
  return { ...journey, steps: tidy(steps) };
}

/** Před uložením oříznuté texty; prázdné texty a neplatný počet se vynechají. */
export function journeyForSave(journey: CustomerJourney): CustomerJourney {
  const purpose = journey.purpose?.trim();
  return { id: journey.id, name: journey.name.trim(), ...(purpose ? { purpose } : {}), steps: journey.steps.map((step) => {
    const label = step.label?.trim(), experience = step.experience?.trim();
    const count = Number.isInteger(step.count) && (step.count ?? -1) >= 0 ? step.count : undefined;
    return { id: step.id, page: step.page, ...(label ? { label } : {}), ...(experience ? { experience } : {}),
      ...(count !== undefined ? { count } : {}), ...(step.after ? { after: step.after } : {}) };
  }) };
}

/** Všechny cesty aplikace připravené k uložení; bez cest klíč zmizí. */
export function journeysForSave(site: ApplicationSite): ApplicationSite {
  return withJourneys(site, (site.journeys ?? []).map(journeyForSave));
}

/** Proč cestu nejde uložit, jinak `null`. Backend odmítne totéž. */
export function journeyProblem(journey: CustomerJourney): string | null {
  if (!journey.name.trim()) return "Cesta potřebuje název.";
  if (journey.steps.length < MIN_STEPS) return "Cesta potřebuje aspoň dvě stránky.";
  if (journey.steps.slice(1).some((step) => step.page === FROM_NAV)) return "Menu smí být jen první krok.";
  if (journey.steps.some((step, index) => step.after !== undefined && !journey.steps.slice(0, index).some((other) => other.id === step.after)))
    return "Krok smí navazovat jen na dřívější krok.";
  return null;
}

/** Id kroku, na který krok `index` navazuje (`after`, jinak předchozí v seznamu); první krok nenavazuje na nic. */
export function previousStepId(journey: CustomerJourney, index: number): string | null {
  if (index <= 0) return null;
  return journey.steps[index].after ?? journey.steps[index - 1].id;
}

/** Konverze kroku proti kroku, na který navazuje (0–1), jen když oba mají počet a předchozí je > 0. */
export function stepRate(journey: CustomerJourney, index: number): number | null {
  const previous = journey.steps.find((step) => step.id === previousStepId(journey, index));
  const before = previous?.count, now = journey.steps[index]?.count;
  return before && now !== undefined ? now / before : null;
}

/** „51,4 %“: konverze s jedním desetinným místem a českou čárkou. */
export function formatRate(rate: number): string {
  return (Math.round(rate * 1000) / 10).toFixed(1).replace(".", ",") + " %";
}

/** „36 879“: počet lidí s mezerou mezi tisíci (nezlomitelnou, aby se číslo nerozdělilo na dva řádky). */
export function formatCount(count: number): string {
  return String(count).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

/** Popisek stránky kroku: „Menu“, název stránky, nebo upozornění na stránku, která v mapě už není. */
export function stepPageLabel(id: string, pages: Pick<CanvasNode, "id" | "name">[]): { label: string; missing: boolean } {
  if (id === FROM_NAV) return { label: "Menu", missing: false };
  const page = pages.find((candidate) => candidate.id === id);
  return page ? { label: page.name, missing: false } : { label: "chybí stránka " + id, missing: true };
}

/** Jméno kroku pro výběr „Navazuje na“ a zprávy: role, jinak pořadí. */
export function stepName(journey: CustomerJourney, id: string): string {
  const index = journey.steps.findIndex((step) => step.id === id);
  return journey.steps[index]?.label ?? `${index + 1}. krok`;
}
