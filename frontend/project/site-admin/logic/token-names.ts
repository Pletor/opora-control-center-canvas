// Jména tokenů podle gramatiky formátu (`backend/project/site_admin/tokens.py`): jeden sdílený jmenný prostor
// `--jméno` přes barvy, spacing, radius, stíny a vlastní rodiny (typografické styly mají vlastní). Server neplatné
// jméno zahodí s poznámkou; editor to řekne dřív, přímo u pole.
import type { DesignTokens } from "./site-document";

export const TOKEN_NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;

/** Všechna jména sdíleného prostoru (bez typografie). */
export function tokenNames(tokens: DesignTokens): string[] {
  return Object.entries(tokens).flatMap(([key, family]) =>
    key === "type" || !family || !("tokens" in family) ? [] : family.tokens.map((token) => token.name));
}

/** Proč jméno neprojde, nebo `""`. `own` je současné jméno upravovaného tokenu (smí zůstat). */
export function nameProblem(name: string, taken: readonly string[], own = ""): string {
  if (!TOKEN_NAME.test(name)) return "Jméno: písmena, číslice, _ . -, začíná písmenem nebo číslicí, nejvýš 64 znaků.";
  if (name !== own && taken.includes(name)) return `Jméno ${name} už v systému je.`;
  return "";
}

/** Volné jméno `základ`, `základ-2`, `základ-3`… pro nově přidaný token. */
export function freeName(base: string, taken: readonly string[]): string {
  if (!taken.includes(base)) return base;
  for (let index = 2; ; index++) if (!taken.includes(`${base}-${index}`)) return `${base}-${index}`;
}
