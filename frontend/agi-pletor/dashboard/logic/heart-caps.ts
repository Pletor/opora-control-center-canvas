import { api } from "@/shared/types/logic/types";
import { rec } from "./view-common";

export type CapKey = "per_hour" | "per_project" | "rate_sleep_seconds";
export type Caps = { values: Record<CapKey, number>; bounds: Record<CapKey, [number, number]> };

export const CAP_FIELDS: { key: CapKey; label: string }[] = [
  { key: "per_hour", label: "Automatických dávek za hodinu" },
  { key: "per_project", label: "Souběžných běhů na projekt" },
  { key: "rate_sleep_seconds", label: "Spánek po limitu předplatného (s)" },
];

const URL = "/api/pletor/heart/caps";

/** Rozumí jen `{per_hour, per_project, rate_sleep_seconds, bounds}`; cokoli jiného je chyba čtení. */
export function parseCaps(raw: unknown): Caps {
  const r = rec(raw);
  const bounds = rec(r.bounds);
  const values = {} as Caps["values"];
  const lims = {} as Caps["bounds"];
  for (const { key } of CAP_FIELDS) {
    const b = Array.isArray(bounds[key]) ? (bounds[key] as unknown[]) : [];
    if (typeof r[key] !== "number") throw new Error(typeof r.error === "string" ? r.error : "Stropy srdce se nepodařilo načíst.");
    values[key] = r[key] as number;
    lims[key] = [typeof b[0] === "number" ? b[0] : 0, typeof b[1] === "number" ? b[1] : Number.MAX_SAFE_INTEGER];
  }
  return { values, bounds: lims };
}

/** Tělo PUT jen ze změněných klíčů. */
export const capsChanges = (saved: Caps, draft: Record<CapKey, number>): Partial<Record<CapKey, number>> =>
  Object.fromEntries(CAP_FIELDS.filter(({ key }) => draft[key] !== saved.values[key]).map(({ key }) => [key, draft[key]]));

/** Mimo meze nebo nečíselné → věta pro člověka, jinak null. */
export function capProblem(caps: Caps, key: CapKey, value: number): string | null {
  const [min, max] = caps.bounds[key];
  return Number.isInteger(value) && value >= min && value <= max ? null : `Povoleno ${min} až ${max}.`;
}

export const fetchHeartCaps = (): Promise<Caps> => api<unknown>(URL).then(parseCaps);
export const putHeartCaps = (changes: Partial<Record<CapKey, number>>): Promise<Caps> => api<unknown>(URL, changes, "PUT").then(parseCaps);
