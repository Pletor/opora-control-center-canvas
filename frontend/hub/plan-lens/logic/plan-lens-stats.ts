import type { PlanLens, PlanStats } from "./plan-lens-read";

// Slova pro hlavičku Lens plánu: čísla se skloňují (1 oblast, 2 oblasti, 5 oblastí), Graphify řekne,
// zda šedé vazby „kód“ vůbec mohly vzniknout.
export type StatItem = { key: keyof PlanStats; value: number; text: string; title: string };

const FORMS: Record<keyof PlanStats, [string, string, string, string]> = {
  areas: ["oblast", "oblasti", "oblastí", "Oblasti v plánu"],
  cards: ["karta", "karty", "karet", "Karty v plánu"],
  withCode: ["s kódem", "s kódem", "s kódem", "Karty, ke kterým Graphify našel kód"],
  planned: ["v plánu", "v plánu", "v plánu", "Karty jen v plánu, kód zatím není (odznak „plán“)"],
  standalone: ["samostatná", "samostatné", "samostatných", "Karty bez vazeb na jiné karty"],
  unassigned: ["nezařazená", "nezařazené", "nezařazených", "Karty mimo jakoukoli oblast"],
};
const ORDER = Object.keys(FORMS) as (keyof PlanStats)[];

export function czechPlural(value: number, one: string, few: string, many: string) {
  return value === 1 ? one : value >= 2 && value <= 4 ? few : many;
}

/** Řada čísel do hlavičky v pevném pořadí: oblasti, karty, s kódem, v plánu, samostatné, nezařazené. */
export function statItems(stats: PlanStats): StatItem[] {
  return ORDER.map(key => {
    const [one, few, many, title] = FORMS[key];
    return { key, value: stats[key], text: `${stats[key]} ${czechPlural(stats[key], one, few, many)}`, title };
  });
}

/** Stav Graphify: s revizí zdroje, bez ní, nebo nedostupný (pak vazby „kód“ chybí). */
export function graphifyText(graphify: PlanLens["graphify"]): string {
  if (!graphify.available) return "Graphify nedostupný · vazby „kód“ chybí";
  return graphify.sourceRevision ? `Graphify ✓ · revize ${graphify.sourceRevision.slice(0, 7)}` : "Graphify ✓";
}

/** Nadpis okna: celý projekt, nebo jedna oblast. */
export function planLensTitle(area: string | null, areaName = ""): string {
  return area ? `Lens oblasti · ${areaName || area}` : "Lens plánu · celý projekt";
}
