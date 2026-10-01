// Kam prvek katalogu patří: prvek Knihovny i Agentů smí nést `fits` (pro které architektury a pro
// jaké uživatele dává smysl). Bez `fits` je univerzální a patří všem. Profil projektu (`ProjectProfile`
// z project-capabilities) pak rozdělí katalog na to, co k projektu sedí, a to, co je mimo profil.
// Pole profilu `""` znamená nenastaveno: podle něj se nefiltruje. Kontrakt: docs/suplik-a-profil.md.
// Bez Reactu; test vedle v catalog-fit.test.ts.
import type { Architecture, Tenancy } from "@/shared/types/logic/types";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { architectureWord, tenancyWord } from "@/shared/project-capabilities/logic/project-profile";

export type CatalogFit = { architecture?: Architecture[]; tenancy?: Tenancy[] };

/** Cokoli z obou katalogů: stačí volitelné `fits`. */
export type Fittable = { fits?: CatalogFit };

/** Sedí prvek k profilu? Prázdný seznam ve `fits` i nenastavené pole profilu znamená „nefiltrovat“. */
export function fitsProfile(item: Fittable, profile: ProjectProfile): boolean {
  const fits = item.fits;
  if (!fits) return true;
  if (profile.architecture && fits.architecture?.length && !fits.architecture.includes(profile.architecture)) return false;
  if (profile.tenancy && fits.tenancy?.length && !fits.tenancy.includes(profile.tenancy)) return false;
  return true;
}

/** Rozdělení katalogu v jeho pořadí: co k projektu sedí a co je mimo profil. */
export function splitByProfile<T extends Fittable>(items: T[], profile: ProjectProfile): { fitting: T[]; outside: T[] } {
  const fitting: T[] = [];
  const outside: T[] = [];
  for (const item of items) (fitsProfile(item, profile) ? fitting : outside).push(item);
  return { fitting, outside };
}

/**
 * Proč je prvek ve výběru: „kvůli profilu: multitenant“, když ho tam přivedla nastavená hodnota
 * profilu. Univerzální prvek, prvek mimo profil a prvek u nenastaveného profilu důvod nemají (`null`).
 */
export function fitReason(item: Fittable, profile: ProjectProfile): string | null {
  const fits = item.fits;
  if (!fits || !fitsProfile(item, profile)) return null;
  const words: string[] = [];
  if (profile.architecture && fits.architecture?.includes(profile.architecture)) words.push(architectureWord(profile.architecture));
  if (profile.tenancy && fits.tenancy?.includes(profile.tenancy)) words.push(tenancyWord(profile.tenancy));
  return words.length ? "kvůli profilu: " + words.join(", ") : null;
}

/** Komu prvek patří, slovy („mikroslužby“, „multitenant“); univerzální prvek nevrací nic. */
export function fitWords(item: Fittable): string[] {
  return [...(item.fits?.architecture ?? []).map(architectureWord), ...(item.fits?.tenancy ?? []).map(tenancyWord)];
}

const plural = (count: number, forms: [string, string, string]): string =>
  `${count} ${count === 1 ? forms[0] : count >= 2 && count <= 4 ? forms[1] : forms[2]}`;

/** Řádek pod seznamem: „3 prvky (mikroslužby, serverless)“ — kolik je mimo profil a pro koho to je. */
export function outsideSummary(outside: Fittable[], forms: [string, string, string]): string {
  const words = [...new Set(outside.flatMap(fitWords))];
  return plural(outside.length, forms) + (words.length ? ` (${words.join(", ")})` : "");
}
